from decimal import Decimal

import pytest

from app.receipt_model import _decimal


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
