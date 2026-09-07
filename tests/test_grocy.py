import app.grocy as grocy


def test_load_locations_uses_locations_endpoint(monkeypatch):
    calls = []

    monkeypatch.setattr(
        grocy,
        "grocy_get",
        lambda path: calls.append(path) or [{"id": 2, "name": "Fridge"}],
    )

    result = grocy.load_locations()

    assert result == [{"id": 2, "name": "Fridge"}]
    assert calls == ["/api/objects/locations"]


def test_load_quantity_units_uses_quantity_units_endpoint(monkeypatch):
    calls = []

    monkeypatch.setattr(
        grocy,
        "grocy_get",
        lambda path: calls.append(path) or [{"id": 2, "name": "st"}],
    )

    result = grocy.load_quantity_units()

    assert result == [{"id": 2, "name": "st"}]
    assert calls == ["/api/objects/quantity_units"]


def test_load_quantity_unit_conversions_uses_conversions_endpoint(monkeypatch):
    calls = []

    monkeypatch.setattr(
        grocy,
        "grocy_get",
        lambda path: calls.append(path)
        or [{"from_qu_id": 3, "to_qu_id": 2, "factor": 12, "product_id": 42}],
    )

    result = grocy.load_quantity_unit_conversions()

    assert result == [
        {
            "from_qu_id": 3,
            "to_qu_id": 2,
            "factor": 12,
            "product_id": 42,
        }
    ]
    assert calls == ["/api/objects/quantity_unit_conversions"]


def test_create_product_uses_products_endpoint(monkeypatch):
    calls = []

    monkeypatch.setattr(
        grocy,
        "grocy_post",
        lambda path, payload: calls.append((path, payload))
        or {"created_object_id": 42},
    )

    payload = {
        "name": "Test Milk",
        "location_id": 2,
        "qu_id_purchase": 2,
        "qu_id_stock": 2,
    }

    result = grocy.create_product(payload)

    assert result == {"created_object_id": 42}
    assert calls == [
        ("/api/objects/products", payload),
    ]


def test_create_quantity_unit_conversion(monkeypatch):
    import app.grocy as grocy

    calls = []

    def fake_post(path, payload):
        calls.append((path, payload))
        return {"id": 7}

    monkeypatch.setattr(grocy, "grocy_post", fake_post)

    payload = {
        "from_qu_id": 3,
        "to_qu_id": 5,
        "factor": 12,
        "product_id": 99,
    }

    result = grocy.create_quantity_unit_conversion(payload)

    assert result == {"id": 7}
    assert calls == [
        ("/api/objects/quantity_unit_conversions", payload)
    ]
