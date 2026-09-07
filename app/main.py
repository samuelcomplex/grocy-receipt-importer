import hashlib
import difflib
import io
import json

from app.config import (
    MAPPING_STORAGE,
    RECEIPT_STORAGE,
)
import re
import uuid
from datetime import datetime
from decimal import Decimal

import requests

from common import money, money_str, quantity
from app.product_matching import suggest_product_matches
from app.receipt_model import receipt_from_parser_output, receipt_from_storage
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pypdf import PdfReader
from plugins.discovery import find_parser
from app.grocy import grocy_get, grocy_post, grocy_post_no_content, load_products
from app.storage import create_mapping_storage, create_receipt_storage
from app.web import render_template

def create_storages():
    return (
        create_receipt_storage(RECEIPT_STORAGE),
        create_mapping_storage(MAPPING_STORAGE),
    )


receipt_storage, mapping_storage = create_storages()


def get_receipt(receipt_id):
    return receipt_storage.get(receipt_id)


def initialize_item_state(items):
    for item in items:
        item.setdefault("grocy_product_id", None)
        item.setdefault("grocy_product_name", "")
        item.setdefault("status", "Pending")
        item.setdefault("match_type", None)





app = FastAPI(title="Receipt Importer")


def extract_pdf_text(pdf_data):
    reader = PdfReader(io.BytesIO(pdf_data))

    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


def apply_saved_mappings(metadata, items):
    store_org = metadata.get("store_org", "")

    for item in items:
        article = item.get("article_number")

        if not article:
            continue

        row = mapping_storage.get(store_org, article)

        if row:
            item["grocy_product_id"] = row["grocy_product_id"]
            item["grocy_product_name"] = row["grocy_product_name"]


def determine_receipt_status(imported, skipped, failed):
    if failed:
        return "partial"

    if imported and skipped:
        return "partial"

    if imported:
        return "imported"

    return "review"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    recent = receipt_storage.list_recent()

    receipts = []

    for row in recent:
        receipt = receipt_from_storage(row)

        receipts.append({
            "id": row["id"],
            "filename": row["filename"],
            "date": receipt.date.isoformat() if receipt.date else "",
            "store": receipt.store_name or "",
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


@app.post("/receipt/{receipt_id}/item/{item_index}/undo")
async def undo_import(
    request: Request,
    receipt_id: str,
    item_index: int,
):
    row = get_receipt(receipt_id)

    if not row:
        return HTMLResponse("Receipt not found", status_code=404)

    items = json.loads(row["items_json"])

    if item_index < 0 or item_index >= len(items):
        return HTMLResponse("Item not found", status_code=404)

    item = items[item_index]
    transaction_id = item.get("transaction_id")

    if item.get("status") != "Imported" or not transaction_id:
        return HTMLResponse(
            "This import cannot be safely undone.",
            status_code=400,
        )

    try:
        grocy_post_no_content(
            f"/api/stock/transactions/{transaction_id}/undo",
            {},
        )

        item["status"] = "Undone"
        item["undo_transaction_id"] = transaction_id
        item.pop("transaction_id", None)
        item.pop("error", None)

        remaining_statuses = {item.get("status") for item in items}

        if remaining_statuses and remaining_statuses <= {"Undone"}:
            receipt_status = "undone"
        elif "Imported" in remaining_statuses:
            receipt_status = "partial"
        else:
            receipt_status = "partial"

        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(items, ensure_ascii=False),
            status=receipt_status,
        )

    except Exception as exc:
        item["error"] = f"Undo failed: {exc}"

        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(items, ensure_ascii=False),
        )

        return HTMLResponse(
            f"Undo failed: {exc}",
            status_code=502,
        )

    return RedirectResponse(
        f"/receipt/{receipt_id}",
        status_code=303,
    )


@app.post("/receipt/{receipt_id}/item/{item_index}/unlink")
async def unlink_mapping(
    request: Request,
    receipt_id: str,
    item_index: int,
):
    row = get_receipt(receipt_id)

    if not row:
        return HTMLResponse("Receipt not found", status_code=404)

    metadata = json.loads(row["metadata_json"])
    items = json.loads(row["items_json"])

    if item_index < 0 or item_index >= len(items):
        return HTMLResponse("Item not found", status_code=404)

    item = items[item_index]
    article_number = item.get("article_number")

    if not article_number or not item.get("grocy_product_id"):
        return HTMLResponse(
            "This item does not have a saved mapping.",
            status_code=400,
        )

    mapping_storage.delete(
        metadata.get("store_org", ""),
        article_number,
    )

    item.pop("grocy_product_id", None)
    item.pop("grocy_product_name", None)
    item.pop("match_type", None)
    item.pop("match_score", None)

    receipt_storage.update(
        receipt_id,
        items_json=json.dumps(items, ensure_ascii=False),
    )

    return RedirectResponse(
        f"/receipt/{receipt_id}",
        status_code=303,
    )


@app.post("/receipt/{receipt_id}/delete")
async def delete_receipt(
    request: Request,
    receipt_id: str,
):
    row = get_receipt(receipt_id)

    if not row:
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    receipt_storage.delete(receipt_id)

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

    existing = receipt_storage.find_by_hash(digest)

    if existing:
        return RedirectResponse(
            f"/receipt/{existing['id']}",
            status_code=303,
        )

    text = extract_pdf_text(data)

    parser = find_parser(text)

    if parser is None:
        return HTMLResponse(
            "No receipt parser recognized this receipt.",
            status_code=400,
        )

    parsed = parser.parse(text)
    receipt = receipt_from_parser_output(
        parsed,
        getattr(parser, "retailer", parser.__class__.__name__),
    )

    metadata = receipt.model_dump(mode="json", exclude={"items"})
    items = [
        item.model_dump(mode="json")
        for item in receipt.items
    ]

    initialize_item_state(items)

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

    receipt_storage.save({
        "id": receipt_id,
        "sha256": digest,
        "filename": pdf.filename,
        "raw_text": text,
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "items_json": json.dumps(items, ensure_ascii=False),
        "status": "review",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })

    return RedirectResponse(
        f"/receipt/{receipt_id}",
        status_code=303,
    )


@app.get("/receipt/{receipt_id}", response_class=HTMLResponse)
def review(
    request: Request,
    receipt_id: str,
):
    row = get_receipt(receipt_id)

    if not row:
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    receipt = receipt_from_storage(row)
    metadata = json.loads(row["metadata_json"])
    items = [
        item.model_dump(mode="json")
        for item in receipt.items
    ]

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

            receipt_storage.update(
                receipt_id,
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )

    parser_name = parser_name or "Unknown"
    parser_theme = parser_theme or {}

    try:
        products = load_products()
        suggest_product_matches(items, products)
        grocy_error = None
    except Exception as exc:
        products = []
        grocy_error = str(exc)

    receipt_storage.update(
        receipt_id,
        items_json=json.dumps(items, ensure_ascii=False),
    )


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
    row = get_receipt(receipt_id)

    if not row:
        return HTMLResponse(
            "Receipt not found",
            status_code=404,
        )

    receipt = receipt_from_storage(row)
    metadata = json.loads(row["metadata_json"])
    items = [
        item.model_dump(mode="json")
        for item in receipt.items
    ]

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
            existing_product_id = item.get("grocy_product_id")
            existing_product_name = item.get("grocy_product_name")

            if (
                existing_product_id is not None
                and str(existing_product_id) == selected_product_id
                and existing_product_name
            ):
                product_name = existing_product_name

        if not product_name:
            item["status"] = "Failed"
            item["error"] = "Selected Grocy product could not be resolved."
            failed += 1
            continue

        article_number = item.get("article_number")

        try:
            amount = quantity(item["quantity"])
            net_price = money(item["net"])
            payload = {
                "amount": float(amount),
                "best_before_date": metadata.get("date") or None,
                "transaction_type": "purchase",
                "purchased_date": metadata.get("date") or None,
                "price": float(net_price),
                "note": (
                    f"Receipt {metadata.get('receipt_no', '')}; "
                    f"article {item['article_number']}"
                ),
            }

            stock_entries = grocy_post(
                f"/api/stock/products/{selected_product_id}/add",
                payload,
            )

            # Grocy 4.x returns an array of StockLogEntry objects.
            # Every entry belonging to this purchase has the transaction_id
            # that can later be passed to the transaction undo endpoint.
            transaction_ids = {
                str(entry["transaction_id"])
                for entry in stock_entries
                if entry.get("transaction_id")
            }

            if len(transaction_ids) != 1:
                raise RuntimeError(
                    "Grocy imported the item but returned an unexpected "
                    "number of transaction IDs; undo is unavailable."
                )

            transaction_id = transaction_ids.pop()

            item["status"] = "Imported"
            item["grocy_product_id"] = int(selected_product_id)
            item["grocy_product_name"] = product_name
            item["transaction_id"] = str(transaction_id)
            item.pop("error", None)

            # Only persist the article mapping after the stock transaction
            # succeeded. A failed import must never create a saved mapping.
            if article_number:
                mapping_storage.save(
                    metadata.get("store_org", ""),
                    article_number,
                    int(selected_product_id),
                    product_name,
                )

            imported += 1

        except Exception as exc:
            item["status"] = "Failed"
            item["error"] = str(exc)
            failed += 1

    receipt_storage.update(
        receipt_id,
        items_json=json.dumps(items, ensure_ascii=False),
        status=determine_receipt_status(imported, skipped, failed),
    )

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
