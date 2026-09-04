from decimal import Decimal

import app


def test_normalize_unit_name():
    assert app.normalize_unit_name(" KG ") == "kg"
    assert app.normalize_unit_name("pkts") == "pkts"
    assert app.normalize_unit_name(None) == ""


def test_resolve_receipt_unit_id():
    units = {
        "st": 2,
        "pkt": 3,
        "kg": 5,
    }

    assert app.resolve_receipt_unit_id("PKT", units) == 3
    assert app.resolve_receipt_unit_id("kg", units) == 5
    assert app.resolve_receipt_unit_id("unknown", units) is None


def test_convert_pkt_to_kg(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_product_stock_quantity_unit",
        lambda product_id: (5, "kg"),
    )

    quantity_units = {
        "st": 2,
        "pkt": 3,
        "kg": 5,
    }

    conversions = [
        {
            "product_id": 12,
            "from_qu_id": 3,
            "to_qu_id": 3,
            "factor": 1,
        },
        {
            "product_id": 12,
            "from_qu_id": 3,
            "to_qu_id": 5,
            "factor": 2,
        },
    ]

    amount, unit, factor = app.convert_receipt_quantity_to_stock(
        12,
        Decimal("2"),
        "pkt",
        quantity_units,
        conversions,
    )

    assert amount == Decimal("4")
    assert unit == "kg"
    assert factor == Decimal("2")


def test_convert_pkt_to_l_is_product_specific(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_product_stock_quantity_unit",
        lambda product_id: (4, "l"),
    )

    quantity_units = {
        "pkt": 3,
        "l": 4,
        "kg": 5,
    }

    conversions = [
        {
            "product_id": 11,
            "from_qu_id": 3,
            "to_qu_id": 4,
            "factor": 2,
        },
    ]

    amount, unit, factor = app.convert_receipt_quantity_to_stock(
        11,
        Decimal("2"),
        "pkt",
        quantity_units,
        conversions,
    )

    assert amount == Decimal("4")
    assert unit == "l"
    assert factor == Decimal("2")


def test_same_unit_requires_no_conversion(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_product_stock_quantity_unit",
        lambda product_id: (5, "kg"),
    )

    amount, unit, factor = app.convert_receipt_quantity_to_stock(
        12,
        Decimal("2.5"),
        "kg",
        {"kg": 5},
        [],
    )

    assert amount == Decimal("2.5")
    assert unit == "kg"
    assert factor == Decimal("1")


def test_missing_conversion_fails(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_product_stock_quantity_unit",
        lambda product_id: (5, "kg"),
    )

    try:
        app.convert_receipt_quantity_to_stock(
            12,
            Decimal("2"),
            "pkt",
            {"pkt": 3, "kg": 5},
            [],
        )
    except ValueError as exc:
        assert "No conversion" in str(exc)
    else:
        raise AssertionError("Expected missing conversion to fail")


def test_unknown_receipt_unit_fails(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_product_stock_quantity_unit",
        lambda product_id: (5, "kg"),
    )

    try:
        app.convert_receipt_quantity_to_stock(
            12,
            Decimal("2"),
            "mystery",
            {"kg": 5},
            [],
        )
    except ValueError as exc:
        assert "not configured in Grocy" in str(exc)
    else:
        raise AssertionError("Expected unknown unit to fail")


def test_stk_alias_uses_existing_grocy_st_unit():
    units = {
        "st": 2,
        "pkt": 3,
    }

    app_units = dict(units)
    if "stk" not in app_units and "st" in app_units:
        app_units["stk"] = app_units["st"]

    assert app.resolve_receipt_unit_id("stk", app_units) == 2
    assert app.resolve_receipt_unit_id("st", app_units) == 2
