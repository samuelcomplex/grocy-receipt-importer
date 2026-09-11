import hashlib
import io
import json
import uuid
from datetime import datetime

from app.config import (
    MAPPING_STORAGE,
    RECEIPT_STORAGE,
)
from app.grocy import (
    grocy_post,
    grocy_post_no_content,
    load_locations,
    load_product,
    load_products,
    load_product_groups,
    load_shopping_locations,
    grocy_delete,
    load_quantity_unit_conversions,
    load_quantity_units,
    create_quantity_unit,
    create_location,
    create_product_group,
)
from app.product_matching import normalize_product_name, suggest_product_matches
from app.product_service import (
    calculate_price_per_stock_unit,
    calculate_stock_amount,
    create_new_grocy_product,
    validate_new_product_configuration,
)
from app.receipt_model import receipt_from_parser_output, receipt_from_storage
from app.storage import create_alias_storage, create_mapping_storage, create_receipt_storage
from app.web import render_template
from common import money
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pypdf import PdfReader
from plugins.discovery import find_parser


def create_storages():
    return (
        create_receipt_storage(RECEIPT_STORAGE),
        create_mapping_storage(MAPPING_STORAGE),
        create_alias_storage(MAPPING_STORAGE),
    )


receipt_storage, mapping_storage, alias_storage = create_storages()


def get_receipt(receipt_id):
    return receipt_storage.get(receipt_id)


def json_response(payload, status_code=200):
    return HTMLResponse(
        json.dumps(payload),
        status_code=status_code,
        media_type="application/json",
    )


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

        if article:
            row = mapping_storage.get(store_org, article)

            if row:
                item["grocy_product_id"] = row["grocy_product_id"]
                item["grocy_product_name"] = row["grocy_product_name"]
                item["match_type"] = "saved"
                continue

        description = item.get("description", "")
        normalized_description = normalize_product_name(description)

        if not normalized_description:
            continue

        row = alias_storage.get(store_org, normalized_description)

        if row:
            item["grocy_product_id"] = row["grocy_product_id"]
            item["grocy_product_name"] = row["grocy_product_name"]
            item["match_type"] = "alias"


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


@app.post("/receipt/{receipt_id}/new-product/{item_index}/undo")
async def undo_new_product(
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
    product_id = item.get("grocy_product_id")

    if item.get("match_type") != "new" or not product_id:
        return HTMLResponse(
            "This new product cannot be safely undone.",
            status_code=400,
        )

    affected_indexes = [
        index
        for index, candidate in enumerate(items)
        if (
            candidate.get("match_type") == "new"
            and candidate.get("grocy_product_id") == product_id
        )
    ]

    if any(
        items[index].get("status") == "Imported"
        or items[index].get("transaction_id")
        for index in affected_indexes
    ):
        return HTMLResponse(
            "This new product cannot be safely undone.",
            status_code=400,
        )

    form = await request.form()
    force = form.get("force") == "1"

    selected_item_indexes = set()
    raw_selected_indexes = (
        form.getlist("selected_item_indexes")
        if hasattr(form, "getlist")
        else form.get("selected_item_indexes", [])
    )
    if isinstance(raw_selected_indexes, str):
        raw_selected_indexes = [raw_selected_indexes]

    for raw_index in raw_selected_indexes:
        try:
            selected_index = int(raw_index)
        except (TypeError, ValueError):
            continue

        if 0 <= selected_index < len(items):
            selected_item_indexes.add(selected_index)

    affected_indexes = sorted(
        set(affected_indexes) | selected_item_indexes
    )

    if len(affected_indexes) > 1 and not force:
        return json_response(
            {
                "ok": False,
                "requires_confirmation": True,
                "warning": (
                    f"This product is assigned to {len(affected_indexes)} "
                    "receipt lines. Undoing it will remove the product "
                    "from all of them."
                ),
                "affected_item_indexes": affected_indexes,
            },
            status_code=409,
        )

    try:
        grocy_delete(f"/api/objects/products/{int(product_id)}")

        for index in affected_indexes:
            affected_item = items[index]
            affected_item["grocy_product_id"] = None
            affected_item["grocy_product_name"] = ""
            affected_item["match_type"] = None

        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(items, ensure_ascii=False),
        )

        return json_response(
            {
                "ok": True,
                "product_id": int(product_id),
                "affected_item_indexes": affected_indexes,
            }
        )

    except Exception as exc:
        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(items, ensure_ascii=False),
        )

        return json_response(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


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
        return json_response(
            {"ok": False, "error": "Receipt not found"},
            status_code=404,
        )

    metadata = json.loads(row["metadata_json"])
    items = json.loads(row["items_json"])

    if item_index < 0 or item_index >= len(items):
        return json_response(
            {"ok": False, "error": "Item not found"},
            status_code=404,
        )

    item = items[item_index]
    article_number = item.get("article_number")

    if not article_number or not item.get("grocy_product_id"):
        return json_response(
            {
                "ok": False,
                "error": "This item does not have a saved mapping.",
            },
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

    return json_response({
        "ok": True,
        "item_index": item_index,
    })


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
        locations = load_locations()
        quantity_units = load_quantity_units()
        product_groups = load_product_groups()
        shopping_locations = load_shopping_locations()
        suggest_product_matches(items, products)
        grocy_error = None
    except Exception as exc:
        products = []
        locations = []
        quantity_units = []
        product_groups = []
        shopping_locations = []
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
            "locations": locations,
            "quantity_units": quantity_units,
            "product_groups": product_groups,
            "shopping_locations": shopping_locations,
            "parser_name": parser_name,
            "parser_theme": parser_theme,
            "grocy_error": grocy_error,
        },
    )





@app.post("/receipt/{receipt_id}/new-product/quantity-unit")
async def create_new_product_quantity_unit(
    request: Request,
    receipt_id: str,
):
    form = await request.form()
    name = str(form.get("name") or "").strip()

    if not name:
        return json_response(
            {
                "ok": False,
                "error": "Quantity unit name is required.",
            },
            status_code=400,
        )

    try:
        created = create_quantity_unit({"name": name})
        unit_id = int(created.get("id") or created.get("created_object_id"))

        return json_response(
            {
                "ok": True,
                "id": unit_id,
                "name": name,
            }
        )
    except Exception as exc:
        return json_response(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


@app.post("/receipt/{receipt_id}/new-product/product-group")
async def create_new_product_group(
    request: Request,
    receipt_id: str,
):
    form = await request.form()
    name = str(form.get("name") or "").strip()

    if not name:
        return json_response(
            {
                "ok": False,
                "error": "Product group name is required.",
            },
            status_code=400,
        )

    try:
        created = create_product_group({"name": name})
        group_id = int(
            created.get("id") or created.get("created_object_id")
        )

        return json_response(
            {
                "ok": True,
                "id": group_id,
                "name": name,
            }
        )
    except Exception as exc:
        return json_response(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


@app.post("/receipt/{receipt_id}/new-product/location")
async def create_new_product_location(
    request: Request,
    receipt_id: str,
):
    form = await request.form()
    name = str(form.get("name") or "").strip()
    is_freezer = str(form.get("is_freezer") or "").lower() in {
        "1",
        "true",
        "on",
        "yes",
    }

    if not name:
        return json_response(
            {
                "ok": False,
                "error": "Storage location name is required.",
            },
            status_code=400,
        )

    try:
        created = create_location({
            "name": name,
            "is_freezer": is_freezer,
        })
        location_id = int(
            created.get("id") or created.get("created_object_id")
        )

        return json_response(
            {
                "ok": True,
                "id": location_id,
                "name": name,
            }
        )
    except Exception as exc:
        return json_response(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


@app.post("/receipt/{receipt_id}/stage-new-product")
async def stage_new_product(
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
    items = [
        item.model_dump(mode="json")
        for item in receipt.items
    ]

    form = await request.form()

    try:
        item_index = int(form.get("item_index", ""))
    except (TypeError, ValueError):
        return json_response(
            {
                "ok": False,
                "error": "Invalid receipt item.",
            },
            status_code=400,
        )

    if item_index < 0 or item_index >= len(items):
        return json_response(
            {
                "ok": False,
                "error": "Receipt item not found.",
            },
            status_code=404,
        )

    item = items[item_index]

    if item.get("kind") != "product":
        return json_response(
            {
                "ok": False,
                "error": "Only product items can create a new Grocy product.",
            },
            status_code=400,
        )

    name = form.get("name")
    location_id = form.get("location_id")
    purchase_unit_id = form.get("purchase_unit_id")
    stock_unit_id = form.get("stock_unit_id")
    conversion_factor = form.get("conversion_factor") or "1"
    parent_product_id = form.get("parent_product_id") or None
    product_group_id = form.get("product_group_id") or None
    shopping_location_id = form.get("shopping_location_id") or None
    min_stock_amount = form.get("min_stock_amount") or "0"
    quick_consume_amount = form.get("quick_consume_amount") or "0"
    treat_opened_as_out_of_stock = (
        form.get("treat_opened_as_out_of_stock") == "true"
    )
    default_best_before_days = (
        form.get("default_best_before_days") or "0"
    )
    default_best_before_days_after_open = (
        form.get("default_best_before_days_after_open") or "0"
    )

    try:
        # These are deliberately loaded live. The modal must not rely
        # only on the data that was present when the review page loaded.
        products = load_products()
        locations = load_locations()
        quantity_units = load_quantity_units()
        product_groups = load_product_groups()
        shopping_locations = load_shopping_locations()

        product_payload = validate_new_product_configuration(
            name=name,
            location_id=location_id,
            purchase_unit_id=purchase_unit_id,
            stock_unit_id=stock_unit_id,
            conversion_factor=conversion_factor,
            products=products,
            locations=locations,
            quantity_units=quantity_units,
            product_groups=product_groups,
            shopping_locations=shopping_locations,
            parent_product_id=parent_product_id,
            product_group_id=product_group_id,
            shopping_location_id=shopping_location_id,
            min_stock_amount=min_stock_amount,
            quick_consume_amount=quick_consume_amount,
            treat_opened_as_out_of_stock=treat_opened_as_out_of_stock,
            default_best_before_days=default_best_before_days,
            default_best_before_days_after_open=(
                default_best_before_days_after_open
            ),
        )

        location_names = {
            str(location.get("id")): location.get("name", "")
            for location in locations
        }

        unit_names = {
            str(unit.get("id")): unit.get("name", "")
            for unit in quantity_units
        }

        created = create_new_grocy_product(
            product_payload=product_payload,
            purchase_unit_id=purchase_unit_id,
            stock_unit_id=stock_unit_id,
            conversion_factor=conversion_factor,
        )
        product_id = int(created["product_id"])

        item["grocy_product_id"] = product_id
        item["grocy_product_name"] = product_payload["name"]
        item["match_type"] = "new"

        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(
                items,
                ensure_ascii=False,
            ),
        )

        return json_response(
            {
                "ok": True,
                "product_id": product_id,
                "name": product_payload["name"],
                "location_name": location_names[str(location_id)],
                "purchase_unit_name": unit_names[str(purchase_unit_id)],
                "stock_unit_name": unit_names[str(stock_unit_id)],
                "conversion_factor": str(conversion_factor),
            }
        )

    except Exception as exc:
        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(
                items,
                ensure_ascii=False,
            ),
        )

        return json_response(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
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
        quantity_units = load_quantity_units()
        quantity_unit_conversions = load_quantity_unit_conversions()
        product_names = {
            str(product["id"]): product["name"]
            for product in products
        }
        grocy_error = None
    except Exception as exc:
        products = []
        quantity_units = []
        quantity_unit_conversions = []
        grocy_error = str(exc)

        receipt_storage.update(
            receipt_id,
            items_json=json.dumps(items, ensure_ascii=False),
            status=determine_receipt_status(0, 0, len(items)),
        )

        return render_template(
            request,
            "review.html",
            {
                "receipt_id": receipt_id,
                "metadata": metadata,
                "items": items,
                "products": [],
                "locations": [],
                "quantity_units": [],
                "quantity_unit_conversions": [],
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
                    "imported": 0,
                    "skipped": 0,
                    "failed": 0,
                },
            },
        )

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
        article_number = item.get("article_number")

        try:
            conversion_factor = None

            if selected_product_id == "new":
                existing_product_id = item.get("grocy_product_id")

                if existing_product_id is None:
                    raise ValueError(
                        "New product has not been created. "
                        "Use 'Configure new product' first."
                    )

                selected_product_id = str(existing_product_id)

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
                raise ValueError(
                    "Selected Grocy product could not be resolved."
                )

            product = next(
                (
                    product
                    for product in products
                    if str(product.get("id")) == selected_product_id
                ),
                None,
            )

            if not product:
                existing_product_id = item.get("grocy_product_id")

                if (
                    existing_product_id is not None
                    and str(existing_product_id) == selected_product_id
                ):
                    product = {
                        "id": int(selected_product_id),
                        "name": product_name,
                    }

            if not product:
                raise ValueError(
                    "Selected Grocy product could not be loaded."
                )

            purchase_unit_id = product.get("qu_id_purchase")
            stock_unit_id = product.get("qu_id_stock")

            if not purchase_unit_id or not stock_unit_id:
                product = load_product(selected_product_id)

                purchase_unit_id = product.get("qu_id_purchase")
                stock_unit_id = product.get("qu_id_stock")

            if not purchase_unit_id:
                raise ValueError(
                    "Selected Grocy product has no purchase quantity unit."
                )

            if not stock_unit_id:
                raise ValueError(
                    "Selected Grocy product has no stock quantity unit."
                )

            import_unit_id = form.get(f"import_unit_{index}")

            if import_unit_id:
                import_unit_id = int(import_unit_id)

                if import_unit_id == int(stock_unit_id):
                    conversion_factor = "1"
                    purchase_unit_id = stock_unit_id
                elif import_unit_id == int(purchase_unit_id):
                    conversion_factor = None
                else:
                    raise ValueError(
                        "Selected import unit is not configured for this Grocy product."
                    )

            amount = calculate_stock_amount(
                purchase_amount=item["quantity"],
                purchase_unit_id=purchase_unit_id,
                stock_unit_id=stock_unit_id,
                conversions=quantity_unit_conversions,
                product_id=None if selected_product_id == "new" else int(selected_product_id),
                conversion_factor=conversion_factor,
            )

            net_price = calculate_price_per_stock_unit(
                item["net"],
                amount,
            )
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

            # Only persist mappings when the receipt identifies the retailer.
            # A missing store_org must never result in a NULL store key.
            # Persist the alias before the article mapping so a failed alias
            # save cannot leave behind a new article mapping.
            store_org = metadata.get("store_org")

            normalized_description = normalize_product_name(
                item.get("description", "")
            )

            if store_org and normalized_description:
                alias_storage.save(
                    store_org,
                    normalized_description,
                    int(selected_product_id),
                    product_name,
                )

            if store_org and article_number:
                mapping_storage.save(
                    store_org,
                    article_number,
                    int(selected_product_id),
                    product_name,
                )

            item["status"] = "Imported"
            item["grocy_product_id"] = int(selected_product_id)
            item["grocy_product_name"] = product_name
            item["transaction_id"] = str(transaction_id)
            item.pop("error", None)

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
            "quantity_units": quantity_units,
            "quantity_unit_conversions": quantity_unit_conversions,
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










