import json
from decimal import Decimal

import pytest

from app.receipt_model import _decimal, receipt_from_storage


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12,83", Decimal("12.83")),
        ("12.83", Decimal("12.83")),
        ("1 234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("1.234,56", Decimal("1234.56")),
        ("1.234", Decimal("1234")),
        ("1,234", Decimal("1234")),
        ("12.34", Decimal("12.34")),
        ("12,34", Decimal("12.34")),
        ("1234", Decimal("1234")),
        (1234, Decimal("1234")),
        (12.83, Decimal("12.83")),
        (Decimal("12.83"), Decimal("12.83")),
    ],
)
def test_decimal_normalizes_common_number_formats(value, expected):
    assert _decimal(value) == expected


@pytest.mark.parametrize("value", [None, ""])
def test_decimal_returns_none_for_empty_values(value):
    assert _decimal(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "12,34,56",
        "1.2.3",
    ],
)
def test_decimal_rejects_invalid_numbers(value):
    with pytest.raises((ValueError, ArithmeticError)):
        _decimal(value)


def make_row(items, metadata=None):
    return {
        "metadata_json": json.dumps(metadata or {"store_name": "Coop Hällekis"}),
        "items_json": json.dumps(items),
    }


def test_receipt_from_storage_normalizes_legacy_comma_decimals():
    row = make_row([
        {
            "description": "MER ÄPPLE",
            "article_number": "",
            "unit_price": "",
            "quantity": "1",
            "unit": "st",
            "gross": "17,51",
            "discount": "0,00",
            "net": "17,51",
            "kind": "product",
            "grocy_product_id": None,
            "status": "Imported",
        },
    ])

    receipt = receipt_from_storage(row)
    item = receipt.items[0]

    assert item.unit_price is None
    assert str(item.gross) == "17.51"
    assert str(item.discount) == "0.00"
    assert str(item.net) == "17.51"
    assert item.model_dump()["status"] == "Imported"


def test_receipt_from_storage_handles_already_normalized_items():
    row = make_row([
        {
            "description": "MARSIPANBRÖD ORIG",
            "quantity": "2",
            "unit_price": "15.10",
            "gross": "30.20",
            "discount": "-8.20",
            "net": "22.00",
            "kind": "product",
        },
    ])

    receipt = receipt_from_storage(row)
    item = receipt.items[0]

    assert str(item.net) == "22.00"
