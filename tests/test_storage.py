import json

from app.storage import (
    MemoryReceiptStorage,
    NullMappingStorage,
    create_mapping_storage,
    create_receipt_storage,
)


def make_receipt():
    return {
        "id": "receipt-1",
        "sha256": "abc123",
        "filename": "receipt.pdf",
        "raw_text": "receipt text",
        "metadata_json": json.dumps({"store_org": "TEST"}),
        "items_json": "[]",
        "status": "review",
        "created_at": "2026-09-05T17:00:00",
    }


def test_memory_receipt_storage():
    storage = MemoryReceiptStorage()
    receipt = make_receipt()

    storage.save(receipt)

    assert storage.get("receipt-1")["filename"] == "receipt.pdf"
    assert storage.find_by_hash("abc123")["id"] == "receipt-1"

    storage.update("receipt-1", status="imported")

    assert storage.get("receipt-1")["status"] == "imported"

    assert len(storage.list_recent()) == 1

    storage.delete("receipt-1")

    assert storage.get("receipt-1") is None


def test_null_mapping_storage():
    storage = NullMappingStorage()

    assert storage.get("TEST", "123") is None

    storage.save("TEST", "123", 42, "Milk")

    assert storage.get("TEST", "123") is None

    storage.delete("TEST", "123")


def test_sqlite_receipt_storage(tmp_path, monkeypatch):
    import app.storage as storage_module

    monkeypatch.setattr(
        storage_module,
        "DATA_DIR",
        str(tmp_path),
    )
    monkeypatch.setattr(
        storage_module,
        "DB_PATH",
        str(tmp_path / "receipts.sqlite3"),
    )

    storage = create_receipt_storage("sqlite")
    receipt = make_receipt()

    storage.save(receipt)

    row = storage.get("receipt-1")

    assert row["filename"] == "receipt.pdf"
    assert storage.find_by_hash("abc123")["id"] == "receipt-1"

    storage.update("receipt-1", status="imported")

    assert storage.get("receipt-1")["status"] == "imported"

    assert len(storage.list_recent()) == 1

    storage.delete("receipt-1")

    assert storage.get("receipt-1") is None


def test_sqlite_mapping_storage(tmp_path, monkeypatch):
    import app.storage as storage_module

    monkeypatch.setattr(
        storage_module,
        "DATA_DIR",
        str(tmp_path),
    )
    monkeypatch.setattr(
        storage_module,
        "DB_PATH",
        str(tmp_path / "receipts.sqlite3"),
    )

    storage = create_mapping_storage("sqlite")

    assert storage.get("TEST", "123") is None

    storage.save("TEST", "123", 42, "Milk")

    row = storage.get("TEST", "123")

    assert row["grocy_product_id"] == 42
    assert row["grocy_product_name"] == "Milk"

    storage.delete("TEST", "123")

    assert storage.get("TEST", "123") is None


def test_memory_receipt_storage_is_process_local():
    first = MemoryReceiptStorage()

    receipt = make_receipt()
    first.save(receipt)

    assert first.get("receipt-1") is not None

    second = MemoryReceiptStorage()

    assert second.get("receipt-1") is None


def test_sqlite_mapping_storage_persists_with_memory_receipts(
    tmp_path,
    monkeypatch,
):
    import app.storage as storage_module

    monkeypatch.setattr(
        storage_module,
        "DATA_DIR",
        str(tmp_path),
    )
    monkeypatch.setattr(
        storage_module,
        "DB_PATH",
        str(tmp_path / "receipts.sqlite3"),
    )

    receipt_storage = create_receipt_storage("none")
    mapping_storage = create_mapping_storage("sqlite")

    receipt_storage.save(make_receipt())

    mapping_storage.save(
        "TEST",
        "123",
        42,
        "Milk",
    )

    new_receipt_storage = create_receipt_storage("none")
    new_mapping_storage = create_mapping_storage("sqlite")

    assert new_receipt_storage.get("receipt-1") is None

    row = new_mapping_storage.get("TEST", "123")

    assert row["grocy_product_id"] == 42
    assert row["grocy_product_name"] == "Milk"
