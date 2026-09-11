from __future__ import annotations

import json
from datetime import date, time
from decimal import Decimal

from app.models import Receipt, ReceiptItem


def _decimal(value):
    if value in (None, ""):
        return None

    if isinstance(value, Decimal):
        return value

    text = str(value).strip().replace(" ", "")

    if "," in text and "." in text:
        decimal_separator = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        text = text.replace(thousands_separator, "")
        text = text.replace(decimal_separator, ".")
    elif "," in text:
        if text.count(",") > 1:
            parts = text.split(",")
            if not all(len(part) == 3 for part in parts[1:]):
                raise ValueError(f"Invalid numeric value: {value!r}")
            text = "".join(parts)
        elif len(text.rsplit(",", 1)[1]) == 3:
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
    elif "." in text:
        if text.count(".") > 1:
            parts = text.split(".")
            if not all(len(part) == 3 for part in parts[1:]):
                raise ValueError(f"Invalid numeric value: {value!r}")
            text = "".join(parts)
        elif len(text.rsplit(".", 1)[1]) == 3:
            text = text.replace(".", "")

    return Decimal(text)


def _parse_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_time(value):
    if not value:
        return None

    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def receipt_from_parser_output(data, retailer):
    metadata = data.get("metadata", {})
    items = data.get("items", [])

    return Receipt(
        retailer=retailer,
        store_name=metadata.get("store_name") or None,
        store_org=metadata.get("store_org") or None,
        store_address=metadata.get("store_address") or metadata.get("address") or None,
        date=_parse_date(metadata.get("date")),
        time=_parse_time(metadata.get("time")),
        receipt_number=metadata.get("receipt_number") or metadata.get("receipt_no") or None,
        cashier=metadata.get("cashier") or None,
        items=[
            ReceiptItem(
                description=item.get("description", ""),
                article_number=item.get("article_number") or None,
                quantity=_decimal(item.get("quantity")),
                unit=item.get("unit") or None,
                unit_price=_decimal(item.get("unit_price")),
                gross=_decimal(item.get("gross")),
                discount=_decimal(item.get("discount")),
                net=_decimal(item.get("net")),
                kind=item.get("kind", "product"),
            )
            for item in items
        ],
    )


def receipt_from_storage(row):
    metadata = json.loads(row["metadata_json"])
    items = json.loads(row["items_json"])

    return Receipt(
        retailer=metadata.get("retailer") or metadata.get("parser_name", ""),
        store_name=metadata.get("store_name"),
        store_org=metadata.get("store_org"),
        store_address=metadata.get("store_address"),
        date=_parse_date(metadata.get("date")),
        time=_parse_time(metadata.get("time")),
        receipt_number=metadata.get("receipt_number") or metadata.get("receipt_no"),
        cashier=metadata.get("cashier"),
        items=[ReceiptItem.model_validate(item) for item in items],
    )
