import hashlib
import io
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal

import requests
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pypdf import PdfReader
from plugins.discovery import find_parser

GROCY_BASE_URL = os.environ.get("GROCY_BASE_URL", "http://grocy").rstrip("/")
GROCY_API_KEY = os.environ.get("GROCY_API_KEY", "")
DB_PATH = "/data/receipts.sqlite3"

app = FastAPI(title="Receipt Importer")
templates = Jinja2Templates(directory="templates")


def db():
    os.makedirs("/data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS receipts (
            id TEXT PRIMARY KEY,
            sha256 TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            items_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'review',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mappings (
            store_org TEXT NOT NULL,
            article_number TEXT NOT NULL,
            grocy_product_id INTEGER NOT NULL,
            grocy_product_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(store_org, article_number)
        );
    """)
    con.commit()
    con.close()


init_db()


def money(value):
    return Decimal(value.replace(".", "").replace(",", "."))


def money_str(value):
    return f"{value:.2f}".replace(".", ",")


def quantity(value):
    return Decimal(value.replace(",", "."))


def headers():
    return {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept": "application/json",
    }


def grocy_get(path):
    response = requests.get(
        GROCY_BASE_URL + path,
        headers=headers(),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def grocy_post(path, payload):
    response = requests.post(
        GROCY_BASE_URL + path,
        headers={
            **headers(),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def normalize_unit(value):
    value = value.strip().lower()

    aliases = {
        "piece": "st",
        "pieces": "st",
        "pcs": "st",
        "pc": "st",
    }

    return aliases.get(value, value)


def extract_pdf_text(pdf_data):
    reader = PdfReader(io.BytesIO(pdf_data))

    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


PRODUCT_RE = re.compile(
    r"^(?P<description>.+?)\s+"
    r"(?P<article>\d{7})\s+"
    r"(?P<unit_price>-?\d+,\d{2})\s+"
    r"(?P<quantity>\d+(?:,\d+)?)\s+"
    r"(?P<unit>kg|g|l|ml|st)\s+"
    r"(?P<sum>-?\d+,\d{2})$",
    re.IGNORECASE,
)

DISCOUNT_RE = re.compile(
    r"^(?P<description>.+?)\s+(?P<amount>-\d+,\d{2})$"
)


def load_products():
    return grocy_get("/api/objects/products")


def apply_saved_mappings(metadata, items):
    con = db()

    for item in items:
        article = item.get("article_number")

        if not article:
            continue

        row = con.execute(
            """
            SELECT *
            FROM mappings
            WHERE store_org = ?
              AND article_number = ?
            """,
            (
                metadata.get("store_org", ""),
                article,
            ),
        ).fetchone()

        if row:
            item["grocy_product_id"] = row["grocy_product_id"]
            item["grocy_product_name"] = row["grocy_product_name"]

    con.close()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    con = db()

    recent = con.execute(
        """
        SELECT id, filename, metadata_json, status, created_at
        FROM receipts
        ORDER BY created_at DESC
        LIMIT 20
        """
    ).fetchall()

    con.close()

    receipts = []

    for row in recent:
        metadata = json.loads(row["metadata_json"])

        receipts.append({
            "id": row["id"],
            "filename": row["filename"],
            "date": metadata.get("date", ""),
            "store": metadata.get("store_name", ""),
            "status": row["status"],
        })

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "recent": receipts,
        },
    )


@app.post("/upload")
async def upload(
    pdf: UploadFile = File(...),
):
    data = await pdf.read()

    digest = hashlib.sha256(data).hexdigest()

    con = db()

    existing = con.execute(
        "SELECT id FROM receipts WHERE sha256 = ?",
        (digest,),
    ).fetchone()

    if existing:
        con.close()

        return RedirectResponse(
            f"/receipt/{existing['id']}",
            status_code=303,
        )

    text = extract_pdf_text(data)

    parser = find_parser(text)

    if parser is None:
        con.close()
        return HTMLResponse(
            "No receipt parser recognized this receipt.",
            status_code=400,
        )

    parsed = parser.parse(text)
    metadata = parsed["metadata"]
    items = parsed["items"]

    apply_saved_mappings(metadata, items)

    receipt_id = str(uuid.uuid4())

    con.execute(
        """
        INSERT INTO receipts (
            id,
            sha256,
            filename,
            raw_text,
            metadata_json,
            items_json,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'review', ?)
        """,
        (
            receipt_id,
            digest,
            pdf.filename,
            text,
            json.dumps(metadata, ensure_ascii=False),
            json.dumps(items, ensure_ascii=False),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/receipt/{receipt_id}",
        status_code=303,
    )


@app.get("/receipt/{receipt_id}", response_class=HTMLResponse)
def review(
    request: Request,
    receipt_id: str,
):
    con = db()

    row = con.execute(
        "SELECT * FROM receipts WHERE id = ?",
        (receipt_id,),
    ).fetchone()

    con.close()

    if not row:
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    metadata = json.loads(row["metadata_json"])
    items = json.loads(row["items_json"])

    try:
        products = load_products()
        grocy_error = None
    except Exception as exc:
        products = []
        grocy_error = str(exc)

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "receipt_id": receipt_id,
            "metadata": metadata,
            "items": items,
            "products": products,
            "grocy_error": grocy_error,
        },
    )


@app.post("/receipt/{receipt_id}/mapping")
async def mapping(
    receipt_id: str,
    article_number: str,
    grocy_product_id: int,
):
    con = db()

    row = con.execute(
        "SELECT * FROM receipts WHERE id = ?",
        (receipt_id,),
    ).fetchone()

    if not row:
        con.close()
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    metadata = json.loads(row["metadata_json"])
    items = json.loads(row["items_json"])

    products = load_products()

    product = next(
        (
            p
            for p in products
            if int(p["id"]) == grocy_product_id
        ),
        None,
    )

    if product:
        con.execute(
            """
            INSERT OR REPLACE INTO mappings (
                store_org,
                article_number,
                grocy_product_id,
                grocy_product_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                metadata.get("store_org", ""),
                article_number,
                grocy_product_id,
                product["name"],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        for item in items:
            if item["article_number"] == article_number:
                item["grocy_product_id"] = grocy_product_id
                item["grocy_product_name"] = product["name"]

        con.execute(
            """
            UPDATE receipts
            SET items_json = ?
            WHERE id = ?
            """,
            (
                json.dumps(items, ensure_ascii=False),
                receipt_id,
            ),
        )

        con.commit()

    con.close()

    return RedirectResponse(
        f"/receipt/{receipt_id}",
        status_code=303,
    )


@app.post("/receipt/{receipt_id}/import")
async def import_receipt(
    request: Request,
    receipt_id: str,
):
    con = db()

    row = con.execute(
        "SELECT * FROM receipts WHERE id = ?",
        (receipt_id,),
    ).fetchone()

    con.close()

    if not row:
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    metadata = json.loads(row["metadata_json"])
    items = json.loads(row["items_json"])

    form = await request.form()

    imported = []
    skipped = []
    errors = []

    for index, item in enumerate(items):
        if item["kind"] != "product":
            skipped.append(item["description"])
            continue

        if f"include_{index}" not in form:
            skipped.append(item["description"])
            continue

        product_id = item.get("grocy_product_id")

        if not product_id:
            errors.append(
                f"{item['description']} "
                f"({item['article_number']}): "
                "no Grocy product mapping"
            )
            continue

        amount = quantity(item["quantity"])
        net_price = money(item["net"])
        receipt_unit = item["unit"]

        try:
            details = grocy_get(
                f"/api/stock/products/{product_id}"
            )

            stock_unit = normalize_unit(
                (details.get("quantity_unit_stock") or {}).get(
                    "name", ""
                )
            )

            purchase_unit = normalize_unit(
                (details.get("default_quantity_unit_purchase") or {}).get(
                    "name", ""
                )
            )

            factor = Decimal(
                str(
                    details.get(
                        "qu_conversion_factor_purchase_to_stock",
                        1,
                    )
                )
            )

            if receipt_unit == stock_unit:
                stock_amount = amount

            elif (
                receipt_unit == "st"
                and purchase_unit == stock_unit
                and factor == 1
            ):
                stock_amount = amount

            elif receipt_unit == purchase_unit:
                stock_amount = amount * factor

            else:
                raise ValueError(
                    f"Receipt unit '{receipt_unit}' does not match "
                    f"Grocy stock unit '{stock_unit}' or "
                    f"purchase unit '{purchase_unit}'."
                )

            payload = {
                "amount": float(stock_amount),
                "best_before_date": metadata.get("date") or None,
                "transaction_type": "purchase",
                "purchased_date": metadata.get("date") or None,
                "price": float(net_price),
                "note": (
                    f"Receipt {metadata.get('receipt_no', '')}; "
                    f"article {item['article_number']}"
                ),
            }

            grocy_post(
                f"/api/stock/products/{product_id}/add",
                payload,
            )

            imported.append(
                f"{item['description']} — "
                f"{money_str(net_price)} SEK"
            )

        except Exception as exc:
            errors.append(
                f"{item['description']} "
                f"({item['article_number']}): {exc}"
            )

    status = "imported" if not errors else "partial"

    con = db()

    con.execute(
        "UPDATE receipts SET status = ? WHERE id = ?",
        (status, receipt_id),
    )

    con.commit()
    con.close()

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "metadata": metadata,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        },
    )
