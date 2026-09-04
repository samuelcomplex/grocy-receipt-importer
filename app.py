import hashlib
import difflib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal

import requests

from common import money, money_str, quantity
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pypdf import PdfReader
from plugins.discovery import find_parser

GROCY_BASE_URL = os.environ.get("GROCY_BASE_URL", "http://grocy").rstrip("/")
GROCY_API_KEY = os.environ.get("GROCY_API_KEY", "")
DB_PATH = "/data/receipts.sqlite3"

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
DEFAULT_LANGUAGE = "en"


def load_translations():
    translations = {}

    for path in TRANSLATIONS_DIR.glob("*.json"):
        try:
            translations[path.stem] = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

    if DEFAULT_LANGUAGE not in translations:
        translations[DEFAULT_LANGUAGE] = {}

    return translations


TRANSLATIONS = load_translations()


def translate(key, language=DEFAULT_LANGUAGE):
    language_data = TRANSLATIONS.get(language, {})
    default_data = TRANSLATIONS.get(DEFAULT_LANGUAGE, {})

    return language_data.get(
        key,
        default_data.get(key, key),
    )

app = FastAPI(title="Receipt Importer")
templates = Jinja2Templates(directory="templates")
def get_language(request):
    language = request.cookies.get("language", DEFAULT_LANGUAGE)

    if language not in TRANSLATIONS:
        return DEFAULT_LANGUAGE

    return language


def render_template(request, template_name, context=None):
    context = dict(context or {})
    language = get_language(request)

    context["language"] = language
    context["available_languages"] = sorted(TRANSLATIONS)

    def request_translate(key):
        return translate(key, language)

    context["t"] = request_translate

    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )


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


def normalize_product_name(value):
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9åäöéèüæø]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def suggest_product_matches(items, products):
    normalized_products = [
        (
            product,
            normalize_product_name(product.get("name", "")),
        )
        for product in products
        if product.get("name")
    ]

    for item in items:
        if item.get("kind") != "product":
            continue

        if item.get("grocy_product_id"):
            item["match_type"] = "saved"
            continue

        description = normalize_product_name(
            item.get("description", "")
        )

        if not description:
            continue

        exact = next(
            (
                product
                for product, normalized_name
                in normalized_products
                if normalized_name == description
            ),
            None,
        )

        if exact:
            item["suggested_grocy_product_id"] = exact["id"]
            item["suggested_grocy_product_name"] = exact["name"]
            item["match_score"] = 1.0
            item["match_type"] = "exact"
            continue

        candidates = difflib.get_close_matches(
            description,
            [name for _, name in normalized_products],
            n=1,
            cutoff=0.70,
        )

        if candidates:
            best_name = candidates[0]

            product = next(
                product
                for product, normalized_name
                in normalized_products
                if normalized_name == best_name
            )

            score = difflib.SequenceMatcher(
                None,
                description,
                best_name,
            ).ratio()

            item["suggested_grocy_product_id"] = product["id"]
            item["suggested_grocy_product_name"] = product["name"]
            item["match_score"] = round(score, 2)
            item["match_type"] = "suggested"


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

    return render_template(
        request,
        "index.html",
        {
            "recent": receipts,
        },
    )


@app.post("/language")
async def set_language(request: Request, language: str = Form(...)):
    if language not in TRANSLATIONS:
        language = DEFAULT_LANGUAGE

    response = RedirectResponse(
        url=request.headers.get("referer", "/"),
        status_code=303,
    )
    response.set_cookie(
        key="language",
        value=language,
        max_age=31536000,
        samesite="lax",
    )

    return response


@app.post("/receipt/{receipt_id}/delete")
async def delete_receipt(
    request: Request,
    receipt_id: str,
):
    con = db()

    row = con.execute(
        "SELECT id FROM receipts WHERE id = ?",
        (receipt_id,),
    ).fetchone()

    if not row:
        con.close()
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    con.execute(
        "DELETE FROM receipts WHERE id = ?",
        (receipt_id,),
    )
    con.commit()
    con.close()

    return RedirectResponse(
        url="/",
        status_code=303,
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

    metadata["parser_name"] = getattr(
        parser,
        "retailer",
        parser.__class__.__name__,
    )

    metadata["parser_theme"] = getattr(
        parser,
        "theme",
        {},
    )

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

    parser_name = metadata.get("parser_name")
    parser_theme = metadata.get("parser_theme")

    if not parser_name:
        parser = find_parser(row["raw_text"])

        if parser:
            parser_name = getattr(
                parser,
                "retailer",
                parser.__class__.__name__,
            )
            parser_theme = getattr(
                parser,
                "theme",
                {},
            )

            metadata["parser_name"] = parser_name
            metadata["parser_theme"] = parser_theme

            con = db()
            con.execute(
                """
                UPDATE receipts
                SET metadata_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(metadata, ensure_ascii=False),
                    receipt_id,
                ),
            )
            con.commit()
            con.close()

    parser_name = parser_name or "Unknown"
    parser_theme = parser_theme or {}

    try:
        products = load_products()
        suggest_product_matches(items, products)
        grocy_error = None
    except Exception as exc:
        products = []
        grocy_error = str(exc)

    return render_template(
        request,
        "review.html",
        {
            "receipt_id": receipt_id,
            "metadata": metadata,
            "items": items,
            "products": products,
            "parser_name": parser_name,
            "parser_theme": parser_theme,
            "grocy_error": grocy_error,
        },
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

    imported = 0
    skipped = 0
    failed = 0

    try:
        products = load_products()
        product_names = {
            str(product["id"]): product["name"]
            for product in products
        }
        grocy_error = None
    except Exception as exc:
        products = []
        product_names = {}
        grocy_error = str(exc)

    con = db()

    for index, item in enumerate(items):
        if item["kind"] != "product":
            item["status"] = "Skipped"
            skipped += 1
            continue

        if item.get("status") == "Imported":
            continue

        include = f"include_{index}" in form
        selected_product_id = form.get(f"product_{index}")

        if not include or not selected_product_id:
            item["status"] = "Skipped"
            skipped += 1
            continue

        selected_product_id = str(selected_product_id)
        product_name = product_names.get(selected_product_id)

        if not product_name:
            item["status"] = "Failed"
            failed += 1
            continue

        article_number = item.get("article_number")

        if article_number:
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
                    int(selected_product_id),
                    product_name,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

            item["grocy_product_id"] = int(selected_product_id)
            item["grocy_product_name"] = product_name

        try:
            amount = quantity(item["quantity"])
            net_price = money(item["net"])
            receipt_unit = item["unit"]

            details = grocy_get(
                f"/api/stock/products/{selected_product_id}"
            )

            stock_unit = (
                details.get("quantity_unit_stock") or {}
            ).get("name", "").strip().lower()

            purchase_unit = (
                details.get("default_quantity_unit_purchase") or {}
            ).get("name", "").strip().lower()

            receipt_unit = receipt_unit.strip().lower()

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
                f"/api/stock/products/{selected_product_id}/add",
                payload,
            )

            item["status"] = "Imported"
            imported += 1

        except Exception:
            item["status"] = "Failed"
            failed += 1

    con.execute(
        """
        UPDATE receipts
        SET items_json = ?,
            status = ?
        WHERE id = ?
        """,
        (
            json.dumps(items, ensure_ascii=False),
            "partial" if failed else "imported",
            receipt_id,
        ),
    )

    con.commit()
    con.close()

    return render_template(
        request,
        "review.html",
        {
            "receipt_id": receipt_id,
            "metadata": metadata,
            "items": items,
            "products": products,
            "parser_name": metadata.get(
                "parser_name",
                "Unknown",
            ),
            "parser_theme": metadata.get(
                "parser_theme",
                {},
            ),
            "grocy_error": grocy_error,
            "import_summary": {
                "imported": imported,
                "skipped": skipped,
                "failed": failed,
            },
        },
    )
