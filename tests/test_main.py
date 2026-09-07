import pytest
import json
from decimal import Decimal
import io

import app.main as main
import app.product_service as product_service
from app.product_matching import normalize_product_name, token_match_score


def test_extract_pdf_text(monkeypatch):
    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, stream):
            assert isinstance(stream, io.BytesIO)
            self.pages = [
                FakePage("Page one"),
                FakePage(None),
                FakePage("Page three"),
            ]

    monkeypatch.setattr(main, "PdfReader", FakeReader)

    assert main.extract_pdf_text(b"fake pdf") == "Page one\n\nPage three"


def test_suggest_product_matches_exact():
    items = [
        {
            "kind": "product",
            "description": "Milk",
            "grocy_product_id": None,
        }
    ]

    products = [
        {
            "id": 42,
            "name": "Milk",
        }
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 42
    assert items[0]["suggested_grocy_product_name"] == "Milk"
    assert items[0]["match_score"] == 1.0
    assert items[0]["match_type"] == "exact"


def test_normalize_product_name_handles_case_and_punctuation():
    assert normalize_product_name("Milk 1L!") == "milk 1l"


def test_normalize_product_name_handles_whitespace():
    assert normalize_product_name("  Milk   1L  ") == "milk 1l"


def test_normalize_product_name_handles_swedish_characters():
    assert normalize_product_name("MJÖLK") == "mjölk"


def test_normalize_product_name_keeps_meaningful_swedish_characters():
    assert normalize_product_name("Äpple Ångström Ö") == "äpple ångström ö"



def test_suggest_product_matches_fuzzy_requires_clear_winner():
    items = [
        {
            "kind": "product",
            "description": "Milk 1L",
        }
    ]
    products = [
        {"id": 42, "name": "Milk 1LB"},
        {"id": 99, "name": "Milk 1LT"},
    ]

    main.suggest_product_matches(items, products)

    assert "suggested_grocy_product_id" not in items[0]

def test_suggest_product_matches_token_order():
    items = [
        {
            "kind": "product",
            "description": "Milk 1L",
        }
    ]
    products = [
        {"id": 42, "name": "1L Milk"},
        {"id": 99, "name": "Butter 500g"},
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 42
    assert items[0]["suggested_grocy_product_name"] == "1L Milk"
    assert items[0]["match_type"] == "token"
    assert items[0]["match_score"] == 1.0


def test_suggest_product_matches_token_match_requires_clear_winner():
    items = [
        {
            "kind": "product",
            "description": "Milk",
        }
    ]
    products = [
        {"id": 42, "name": "Milk 1L"},
        {"id": 43, "name": "Milk 1.5L"},
    ]

    main.suggest_product_matches(items, products)

    assert "suggested_grocy_product_id" not in items[0]
    assert "suggested_grocy_product_name" not in items[0]


def test_suggest_product_matches_token_match_handles_extra_product_words():
    items = [
        {
            "kind": "product",
            "description": "ICA Coffee",
        }
    ]
    products = [
        {"id": 42, "name": "ICA Coffee Medium Roast 500g"},
        {"id": 99, "name": "ICA Tea 500g"},
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 42
    assert items[0]["match_type"] == "token"
    assert items[0]["match_score"] == 0.7


def test_suggest_product_matches_token_case_and_order():
    items = [
        {
            "kind": "product",
            "description": "MILK 1L",
        }
    ]
    products = [
        {"id": 42, "name": "1L Milk Premium"},
        {"id": 99, "name": "Butter 500g"},
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 42
    assert items[0]["match_type"] == "token"


def test_suggest_product_matches_token_rejects_generic_overlap():
    items = [
        {
            "kind": "product",
            "description": "Milk",
        }
    ]
    products = [
        {"id": 42, "name": "Milk 1L"},
        {"id": 43, "name": "Chocolate Milk 1L"},
    ]

    main.suggest_product_matches(items, products)

    assert "suggested_grocy_product_id" not in items[0]


def test_suggest_product_matches_token_prefers_more_specific_product():
    items = [
        {
            "kind": "product",
            "description": "Chocolate Milk 1L",
        }
    ]
    products = [
        {"id": 42, "name": "Milk 1L"},
        {"id": 43, "name": "Chocolate Milk 1L"},
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 43
    assert items[0]["match_type"] == "exact"


def test_suggest_product_matches_swedish_product_with_reordered_tokens():
    items = [
        {
            "kind": "product",
            "description": "ARLA MJÖLK 1.5% 1L",
        }
    ]
    products = [
        {"id": 42, "name": "1L Arla Mjölk 1.5%"},
        {"id": 99, "name": "Arla Filmjölk 1L"},
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 42
    assert items[0]["suggested_grocy_product_name"] == "1L Arla Mjölk 1.5%"
    assert items[0]["match_type"] == "token"


def test_token_match_score_values_product_words_more_than_size():
    product_word_score = token_match_score(
        "Arla Mjölk",
        "Arla Mjölk",
    )
    size_only_score = token_match_score(
        "1L",
        "Milk 1L",
    )

    assert product_word_score > size_only_score


def test_token_match_score_rewards_multiple_shared_words():
    one_word_score = token_match_score(
        "Arla",
        "Arla Mjölk 1L",
    )
    two_word_score = token_match_score(
        "Arla Mjölk",
        "Arla Mjölk 1L",
    )

    assert two_word_score > one_word_score


def test_suggest_product_matches_fuzzy():
    items = [
        {
            "kind": "product",
            "description": "Milc",
            "grocy_product_id": None,
        }
    ]

    products = [
        {
            "id": 42,
            "name": "Milk",
        }
    ]

    main.suggest_product_matches(items, products)

    assert items[0]["suggested_grocy_product_id"] == 42
    assert items[0]["suggested_grocy_product_name"] == "Milk"
    assert items[0]["match_type"] == "suggested"
    assert 0.70 <= items[0]["match_score"] <= 1.0


def test_review_persists_product_suggestions(monkeypatch):
    receipt = {
        "id": "receipt-1",
        "sha256": "abc123",
        "filename": "receipt.pdf",
        "raw_text": "receipt text",
        "metadata_json": '{"parser_name": "Test"}',
        "items_json": '[{"kind": "product", "description": "Milk", "grocy_product_id": null}]',
        "status": "review",
        "created_at": "2026-09-05T17:00:00",
    }

    class FakeReceiptStorage:
        def __init__(self):
            self.updated = {}

        def get(self, receipt_id):
            return receipt

        def update(self, receipt_id, **fields):
            self.updated.update(fields)

    storage = FakeReceiptStorage()

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(
        main,
        "load_products",
        lambda: [{"id": 42, "name": "Milk"}],
    )
    monkeypatch.setattr(
        main,
        "load_locations",
        lambda: [{"id": 2, "name": "Fridge"}],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [{"id": 2, "name": "st"}],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [
            {
                "id": 1,
                "from_qu_id": 3,
                "to_qu_id": 2,
                "factor": 12,
                "product_id": 42,
            }
        ],
    )
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = main.review(None, "receipt-1")

    assert result["locations"] == [{"id": 2, "name": "Fridge"}]
    assert result["quantity_units"] == [{"id": 2, "name": "st"}]

    saved_items = main.json.loads(storage.updated["items_json"])

    assert saved_items[0]["suggested_grocy_product_id"] == 42
    assert saved_items[0]["suggested_grocy_product_name"] == "Milk"
    assert result["items"][0]["match_type"] == "exact"


class FakeAliasStorage:
    def __init__(self, saved=None):
        self.saved = saved or []

    def get(self, store_org, normalized_description):
        return None

    def save(
        self,
        store_org,
        normalized_description,
        grocy_product_id,
        grocy_product_name,
    ):
        self.saved.append(
            (
                store_org,
                normalized_description,
                grocy_product_id,
                grocy_product_name,
            )
        )


def test_apply_saved_mappings():
    items = [
        {
            "kind": "product",
            "article_number": "1234567",
            "description": "Milk",
            "grocy_product_id": None,
            "grocy_product_name": "",
        },
        {
            "kind": "product",
            "article_number": "",
            "description": "Bread",
            "grocy_product_id": None,
            "grocy_product_name": "",
        },
    ]

    class FakeMappingStorage:
        def get(self, store_org, article_number):
            assert store_org == "TEST"
            if article_number == "1234567":
                return {
                    "grocy_product_id": 42,
                    "grocy_product_name": "Milk",
                }
            return None

    main.mapping_storage = FakeMappingStorage()
    main.alias_storage = FakeAliasStorage()

    main.apply_saved_mappings(
        {"store_org": "TEST"},
        items,
    )

    assert items[0]["grocy_product_id"] == 42
    assert items[0]["grocy_product_name"] == "Milk"
    assert items[1]["grocy_product_id"] is None


def test_determine_receipt_status():
    assert main.determine_receipt_status(0, 3, 0) == "review"
    assert main.determine_receipt_status(3, 0, 0) == "imported"
    assert main.determine_receipt_status(2, 1, 0) == "partial"
    assert main.determine_receipt_status(0, 2, 1) == "partial"
    assert main.determine_receipt_status(2, 0, 1) == "partial"


def make_import_receipt():
    return {
        "id": "receipt-1",
        "sha256": "abc123",
        "filename": "receipt.pdf",
        "raw_text": "receipt text",
        "metadata_json": json.dumps({
            "store_org": "TEST",
            "date": "2026-09-05",
            "receipt_no": "12345",
            "parser_name": "Test",
        }),
        "items_json": json.dumps([
            {
                "kind": "product",
                "article_number": "123",
                "description": "Milk",
                "quantity": "2",
                "unit": "st",
                "gross": "30.00",
                "discount": "0.00",
                "net": "30.00",
            },
        ]),
        "status": "review",
        "created_at": "2026-09-05T17:00:00",
    }


class FakeImportReceiptStorage:
    def __init__(self, receipt):
        self.receipt = receipt
        self.updates = []

    def get(self, receipt_id):
        return self.receipt

    def update(self, receipt_id, **fields):
        self.updates.append(fields)
        self.receipt.update(fields)


class FakeMappingStorage:
    def __init__(self):
        self.saved = []

    def save(
        self,
        store_org,
        article_number,
        grocy_product_id,
        grocy_product_name,
    ):
        self.saved.append(
            (
                store_org,
                article_number,
                grocy_product_id,
                grocy_product_name,
            )
        )


class FakeFormRequest:
    def __init__(self, values):
        self.values = values

    async def form(self):
        return self.values


@pytest.mark.anyio
async def test_import_receipt_success(monkeypatch):
    storage = FakeImportReceiptStorage(make_import_receipt())
    mappings = FakeMappingStorage()

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(
        main,
        "load_products",
        lambda: [{"id": 42, "name": "Milk"}],
    )

    monkeypatch.setattr(
        main,
        "load_product",
        lambda product_id: {
            "id": 42,
            "name": "Milk",
            "qu_id_purchase": 2,
            "qu_id_stock": 2,
        },
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [
            {"id": 1, "name": "st"},
            {"id": 2, "name": "pkt"},
        ],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [],
    )
    monkeypatch.setattr(
        main,
        "grocy_post",
        lambda path, payload: [
            {"transaction_id": 99},
        ],
    )
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "42",
        }),
        "receipt-1",
    )

    item = result["items"][0]

    assert item["status"] == "Imported"
    assert item["grocy_product_id"] == 42
    assert item["grocy_product_name"] == "Milk"
    assert item["transaction_id"] == "99"

    assert mappings.saved == [
        ("TEST", "123", 42, "Milk"),
    ]

    assert result["import_summary"] == {
        "imported": 1,
        "skipped": 0,
        "failed": 0,
    }

    assert storage.receipt["status"] == "imported"


@pytest.mark.anyio
async def test_import_receipt_failure_does_not_save_mapping(monkeypatch):
    storage = FakeImportReceiptStorage(make_import_receipt())
    mappings = FakeMappingStorage()

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(
        main,
        "load_products",
        lambda: [{"id": 42, "name": "Milk"}],
    )

    monkeypatch.setattr(
        main,
        "load_product",
        lambda product_id: {
            "id": 42,
            "name": "Milk",
            "qu_id_purchase": 2,
            "qu_id_stock": 2,
        },
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [
            {"id": 1, "name": "st"},
            {"id": 2, "name": "pkt"},
        ],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [],
    )

    def fail_import(path, payload):
        raise RuntimeError("Grocy unavailable")

    monkeypatch.setattr(main, "grocy_post", fail_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "42",
        }),
        "receipt-1",
    )

    item = result["items"][0]

    assert item["status"] == "Failed"
    assert item["error"] == "Grocy unavailable"
    assert mappings.saved == []

    assert result["import_summary"] == {
        "imported": 0,
        "skipped": 0,
        "failed": 1,
    }

    assert storage.receipt["status"] == "partial"


@pytest.mark.anyio
async def test_import_receipt_all_skipped_stays_in_review(monkeypatch):
    storage = FakeImportReceiptStorage(make_import_receipt())

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(
        main,
        "load_products",
        lambda: [{"id": 42, "name": "Milk"}],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [
            {"id": 1, "name": "st"},
            {"id": 2, "name": "pkt"},
        ],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [],
    )
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({}),
        "receipt-1",
    )

    assert result["import_summary"] == {
        "imported": 0,
        "skipped": 1,
        "failed": 0,
    }

    assert result["items"][0]["status"] == "Skipped"
    assert storage.receipt["status"] == "review"


@pytest.mark.anyio
async def test_import_receipt_retries_failed_items_without_reimporting_successes(
    monkeypatch,
):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps([
        {
            "kind": "product",
            "article_number": "123",
            "description": "Milk",
            "quantity": "2",
            "unit": "st",
            "gross": "30.00",
            "discount": "0.00",
            "net": "30.00",
            "status": "Imported",
            "grocy_product_id": 42,
            "grocy_product_name": "Milk",
            "transaction_id": "100",
        },
        {
            "kind": "product",
            "article_number": "456",
            "description": "Bread",
            "quantity": "1",
            "unit": "st",
            "gross": "20.00",
            "discount": "0.00",
            "net": "20.00",
            "status": "Failed",
            "error": "Previous failure",
        },
    ])
    receipt["status"] = "partial"

    storage = FakeImportReceiptStorage(receipt)
    mappings = FakeMappingStorage()
    grocy_calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(
        main,
        "load_products",
        lambda: [
            {"id": 42, "name": "Milk"},
            {"id": 84, "name": "Bread"},
        ],
    )

    monkeypatch.setattr(
        main,
        "load_product",
        lambda product_id: {
            "id": int(product_id),
            "name": "Milk" if int(product_id) == 42 else "Bread",
            "qu_id_purchase": 2,
            "qu_id_stock": 2,
        },
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [
            {"id": 1, "name": "st"},
            {"id": 2, "name": "pkt"},
        ],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [],
    )

    def fake_import(path, payload):
        grocy_calls.append((path, payload))
        return [{"transaction_id": 200}]

    monkeypatch.setattr(main, "grocy_post", fake_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "42",
            "include_1": "on",
            "product_1": "84",
        }),
        "receipt-1",
    )

    assert len(grocy_calls) == 1
    assert grocy_calls[0][0] == "/api/stock/products/84/add"

    assert result["items"][0]["transaction_id"] == "100"
    assert result["items"][0]["status"] == "Imported"

    assert result["items"][1]["status"] == "Imported"
    assert result["items"][1]["transaction_id"] == "200"
    assert "error" not in result["items"][1]

    assert result["import_summary"] == {
        "imported": 1,
        "skipped": 0,
        "failed": 0,
    }

    assert storage.receipt["status"] == "imported"

    assert mappings.saved == [
        ("TEST", "456", 84, "Bread"),
    ]


class FakeUndoReceiptStorage:
    def __init__(self, receipt):
        self.receipt = receipt
        self.updates = []

    def get(self, receipt_id):
        return self.receipt

    def update(self, receipt_id, **fields):
        self.updates.append(fields)
        self.receipt.update(fields)


def make_imported_receipt(items):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps(items)
    receipt["status"] = "imported"
    return receipt


@pytest.mark.anyio
async def test_undo_import_success(monkeypatch):
    receipt = make_imported_receipt([
        {
            "kind": "product",
            "article_number": "123",
            "description": "Milk",
            "status": "Imported",
            "transaction_id": "99",
            "grocy_product_id": 42,
            "grocy_product_name": "Milk",
        },
    ])
    storage = FakeUndoReceiptStorage(receipt)
    calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(
        main,
        "grocy_post_no_content",
        lambda path, payload: calls.append((path, payload)),
    )

    result = await main.undo_import(None, "receipt-1", 0)

    assert calls == [
        ("/api/stock/transactions/99/undo", {}),
    ]

    saved_items = json.loads(storage.updates[-1]["items_json"])
    item = saved_items[0]

    assert item["status"] == "Undone"
    assert item["undo_transaction_id"] == "99"
    assert "transaction_id" not in item
    assert "error" not in item
    assert storage.updates[-1]["status"] == "undone"

    assert result.status_code == 303


@pytest.mark.anyio
async def test_undo_import_keeps_partial_receipt_status(monkeypatch):
    receipt = make_imported_receipt([
        {
            "kind": "product",
            "article_number": "123",
            "description": "Milk",
            "status": "Imported",
            "transaction_id": "99",
        },
        {
            "kind": "product",
            "article_number": "456",
            "description": "Bread",
            "status": "Imported",
            "transaction_id": "100",
        },
    ])
    storage = FakeUndoReceiptStorage(receipt)

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(
        main,
        "grocy_post_no_content",
        lambda path, payload: None,
    )

    result = await main.undo_import(None, "receipt-1", 0)

    saved_items = json.loads(storage.updates[-1]["items_json"])

    assert saved_items[0]["status"] == "Undone"
    assert saved_items[1]["status"] == "Imported"
    assert storage.updates[-1]["status"] == "partial"
    assert result.status_code == 303


@pytest.mark.anyio
async def test_undo_import_rejects_non_imported_item(monkeypatch):
    receipt = make_imported_receipt([
        {
            "kind": "product",
            "article_number": "123",
            "description": "Milk",
            "status": "Failed",
        },
    ])
    storage = FakeUndoReceiptStorage(receipt)
    calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(
        main,
        "grocy_post_no_content",
        lambda path, payload: calls.append(path),
    )

    result = await main.undo_import(None, "receipt-1", 0)

    assert result.status_code == 400
    assert calls == []
    assert storage.updates == []


@pytest.mark.anyio
async def test_undo_import_failure_preserves_imported_state(monkeypatch):
    receipt = make_imported_receipt([
        {
            "kind": "product",
            "article_number": "123",
            "description": "Milk",
            "status": "Imported",
            "transaction_id": "99",
        },
    ])
    storage = FakeUndoReceiptStorage(receipt)

    def fail_undo(path, payload):
        raise RuntimeError("Grocy undo unavailable")

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "grocy_post_no_content", fail_undo)

    result = await main.undo_import(None, "receipt-1", 0)

    saved_items = json.loads(storage.updates[-1]["items_json"])
    item = saved_items[0]

    assert result.status_code == 502
    assert item["status"] == "Imported"
    assert item["transaction_id"] == "99"
    assert item["error"] == "Undo failed: Grocy undo unavailable"
    assert "status" not in storage.updates[-1]


@pytest.mark.anyio
async def test_undo_import_missing_receipt():
    class EmptyReceiptStorage:
        def get(self, receipt_id):
            return None

    original = main.receipt_storage
    main.receipt_storage = EmptyReceiptStorage()

    try:
        result = await main.undo_import(None, "missing", 0)
    finally:
        main.receipt_storage = original

    assert result.status_code == 404


@pytest.mark.anyio
async def test_import_saved_mapping_fails_when_grocy_product_list_unavailable(
    monkeypatch,
):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps([
        {
            "kind": "product",
            "article_number": "123",
            "description": "Milk",
            "quantity": "2",
            "unit": "st",
            "gross": "30.00",
            "discount": "0.00",
            "net": "30.00",
            "grocy_product_id": 42,
            "grocy_product_name": "Milk",
            "match_type": "saved",
        },
    ])

    storage = FakeImportReceiptStorage(receipt)
    mappings = FakeMappingStorage()
    calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)

    def fail_load_products():
        raise RuntimeError("Grocy product list unavailable")

    monkeypatch.setattr(main, "load_products", fail_load_products)

    monkeypatch.setattr(
        main,
        "load_product",
        lambda product_id: {
            "id": 42,
            "name": "Milk",
            "qu_id_purchase": 2,
            "qu_id_stock": 2,
        },
    )

    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [],
    )

    def fake_import(path, payload):
        calls.append((path, payload))
        return [{"transaction_id": 123}]

    monkeypatch.setattr(main, "grocy_post", fake_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "42",
        }),
        "receipt-1",
    )

    item = result["items"][0]

    assert result["grocy_error"] == "Grocy product list unavailable"
    assert item.get("status") is None
    assert item.get("transaction_id") is None
    assert calls == []
    assert mappings.saved == []


@pytest.mark.anyio
async def test_import_receipt_creates_new_product_with_conversion(monkeypatch):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps([
        {
            **json.loads(receipt["items_json"])[0],
            "new_product_config": {
                "name": "Coffee",
                "location_id": "3",
                "location_name": "Kitchen",
                "purchase_unit_id": "3",
                "purchase_unit_name": "pack",
                "stock_unit_id": "5",
                "stock_unit_name": "piece",
                "conversion_factor": "2",
            },
            "new_product_status": "ready",
            "new_product_error": "",
        },
    ])
    storage = FakeImportReceiptStorage(receipt)
    mappings = FakeMappingStorage()
    aliases = FakeAliasStorage()

    created_product_calls = []
    created_conversion_calls = []
    stock_calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(main, "alias_storage", aliases)

    monkeypatch.setattr(
        main,
        "load_products",
        lambda: [],
    )
    monkeypatch.setattr(
        main,
        "load_locations",
        lambda: [{"id": 3, "name": "Kitchen"}],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [
            {"id": 3, "name": "pack"},
            {"id": 5, "name": "piece"},
        ],
    )
    conversion_list = [
        {
            "id": 123,
            "from_qu_id": 3,
            "to_qu_id": 5,
            "factor": 1,
            "product_id": 99,
        }
    ]

    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: conversion_list,
    )
    monkeypatch.setattr(
        product_service,
        "load_quantity_unit_conversions",
        lambda: conversion_list,
    )

    updated_conversion_calls = []

    def fake_update_conversion(conversion_id, payload):
        updated_conversion_calls.append((conversion_id, payload))
        return {"id": conversion_id, **payload}

    monkeypatch.setattr(
        product_service,
        "update_quantity_unit_conversion",
        fake_update_conversion,
    )

    def fake_create_product(payload):
        created_product_calls.append(payload)
        return {
            "created_object_id": 99,
            "name": payload["name"],
        }

    def fake_import(path, payload):
        stock_calls.append((path, payload))
        return [{"transaction_id": 555}]

    monkeypatch.setattr(product_service, "create_product", fake_create_product)
    monkeypatch.setattr(main, "grocy_post", fake_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "new",
        }),
        "receipt-1",
    )

    item = result["items"][0]

    assert item["status"] == "Imported"
    assert item["grocy_product_id"] == 99
    assert item["grocy_product_name"] == "Coffee"
    assert item["transaction_id"] == "555"

    assert created_product_calls == [
        {
            "name": "Coffee",
            "location_id": 3,
            "qu_id_purchase": 3,
            "qu_id_stock": 5,
            "qu_id_consume": 5,
            "qu_id_price": 3,
            "min_stock_amount": 0,
        },
    ]

    assert created_conversion_calls == []

    assert updated_conversion_calls == [
        (
            123,
            {
                "from_qu_id": 3,
                "to_qu_id": 5,
                "factor": 2.0,
                "product_id": 99,
            },
        ),
    ]

    assert stock_calls == [
        (
            "/api/stock/products/99/add",
            {
                "amount": 4.0,
                "best_before_date": "2026-09-05",
                "transaction_type": "purchase",
                "purchased_date": "2026-09-05",
                "price": 7.5,
                "note": "Receipt 12345; article 123",
            },
        ),
    ]

    assert mappings.saved == [
        ("TEST", "123", 99, "Coffee"),
    ]

    assert aliases.saved == [
        ("TEST", "milk", 99, "Coffee"),
    ]


@pytest.mark.anyio
async def test_import_preserves_decimal_net_price(monkeypatch):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps([
        {
            **json.loads(receipt["items_json"])[0],
            "net": "211.76",
        },
    ])

    storage = FakeImportReceiptStorage(receipt)
    mappings = FakeMappingStorage()
    aliases = FakeAliasStorage()
    stock_calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(main, "alias_storage", aliases)

    monkeypatch.setattr(main, "load_products", lambda: [
        {
            "id": 42,
            "name": "Blandfärs Storpack",
            "qu_id_purchase": 5,
            "qu_id_stock": 5,
        },
    ])
    monkeypatch.setattr(main, "load_quantity_units", lambda: [
        {"id": 5, "name": "kg"},
    ])
    monkeypatch.setattr(main, "load_quantity_unit_conversions", lambda: [])

    def fake_import(path, payload):
        stock_calls.append((path, payload))
        return [{"transaction_id": 777}]

    monkeypatch.setattr(main, "grocy_post", fake_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "42",
        }),
        "receipt-1",
    )

    assert result["items"][0]["status"] == "Imported"
    assert stock_calls[0][1]["amount"] == 2.0
    assert stock_calls[0][1]["price"] == pytest.approx(211.76 / 2.0)


@pytest.mark.anyio
async def test_import_new_product_same_unit_does_not_create_conversion(monkeypatch):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps([
        {
            **json.loads(receipt["items_json"])[0],
            "new_product_config": {
                "name": "Milk",
                "location_id": "2",
                "location_name": "Pantry",
                "purchase_unit_id": "2",
                "purchase_unit_name": "piece",
                "stock_unit_id": "2",
                "stock_unit_name": "piece",
                "conversion_factor": "1",
            },
            "new_product_status": "ready",
            "new_product_error": "",
        },
    ])
    storage = FakeImportReceiptStorage(receipt)
    mappings = FakeMappingStorage()
    aliases = FakeAliasStorage()

    created_product_calls = []
    created_conversion_calls = []
    stock_calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(main, "alias_storage", aliases)

    monkeypatch.setattr(main, "load_products", lambda: [])
    monkeypatch.setattr(
        main,
        "load_locations",
        lambda: [{"id": 2, "name": "Pantry"}],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [{"id": 2, "name": "piece"}],
    )
    monkeypatch.setattr(main, "load_quantity_unit_conversions", lambda: [])
    monkeypatch.setattr(product_service, "load_quantity_unit_conversions", lambda: [])

    monkeypatch.setattr(
        product_service,
        "create_product",
        lambda payload: (
            created_product_calls.append(payload)
            or {"created_object_id": 100, "name": payload["name"]}
        ),
    )


    def fake_import(path, payload):
        stock_calls.append((path, payload))
        return [{"transaction_id": 556}]

    monkeypatch.setattr(main, "grocy_post", fake_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "new",
        }),
        "receipt-1",
    )

    assert result["items"][0]["status"] == "Imported"
    assert created_product_calls
    assert created_conversion_calls == []

    assert stock_calls[0][1]["amount"] == 2.0


@pytest.mark.anyio
async def test_import_new_product_failure_does_not_save_mapping_or_alias(monkeypatch):
    receipt = make_import_receipt()
    receipt["items_json"] = json.dumps([
        {
            **json.loads(receipt["items_json"])[0],
            "new_product_config": {
                "name": "Coffee",
                "location_id": "3",
                "location_name": "Kitchen",
                "purchase_unit_id": "3",
                "purchase_unit_name": "pack",
                "stock_unit_id": "5",
                "stock_unit_name": "piece",
                "conversion_factor": "2",
            },
            "new_product_status": "ready",
            "new_product_error": "",
        },
    ])
    storage = FakeImportReceiptStorage(receipt)
    mappings = FakeMappingStorage()
    aliases = FakeAliasStorage()

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(main, "alias_storage", aliases)

    monkeypatch.setattr(main, "load_products", lambda: [])
    monkeypatch.setattr(
        main,
        "load_locations",
        lambda: [{"id": 3, "name": "Kitchen"}],
    )
    monkeypatch.setattr(
        main,
        "load_quantity_units",
        lambda: [
            {"id": 3, "name": "pack"},
            {"id": 5, "name": "piece"},
        ],
    )
    conversion_list = [
        {
            "id": 123,
            "from_qu_id": 3,
            "to_qu_id": 5,
            "factor": 1,
            "product_id": 101,
        }
    ]

    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: conversion_list,
    )
    monkeypatch.setattr(
        product_service,
        "load_quantity_unit_conversions",
        lambda: conversion_list,
    )

    monkeypatch.setattr(
        product_service,
        "update_quantity_unit_conversion",
        lambda conversion_id, payload: {"id": conversion_id, **payload},
    )

    monkeypatch.setattr(
        product_service,
        "create_product",
        lambda payload: {
            "created_object_id": 101,
            "name": payload["name"],
        },
    )

    def fail_import(path, payload):
        raise RuntimeError("Grocy unavailable")

    monkeypatch.setattr(main, "grocy_post", fail_import)
    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "new",
        }),
        "receipt-1",
    )

    item = result["items"][0]

    assert item["status"] == "Failed"
    assert item["error"] == "Grocy unavailable"
    assert mappings.saved == []
    assert aliases.saved == []


@pytest.mark.anyio
async def test_import_aborts_when_grocy_product_list_cannot_be_loaded(monkeypatch):
    storage = FakeImportReceiptStorage(make_import_receipt())
    mappings = FakeMappingStorage()
    aliases = FakeAliasStorage()

    created_product_calls = []
    stock_calls = []

    monkeypatch.setattr(main, "receipt_storage", storage)
    monkeypatch.setattr(main, "mapping_storage", mappings)
    monkeypatch.setattr(main, "alias_storage", aliases)

    def fail_load_products():
        raise RuntimeError("Grocy product list unavailable")

    monkeypatch.setattr(main, "load_products", fail_load_products)

    monkeypatch.setattr(
        main,
        "load_quantity_unit_conversions",
        lambda: [],
    )

    monkeypatch.setattr(
        product_service,
        "create_product",
        lambda payload: (
            created_product_calls.append(payload)
            or {"created_object_id": 999, "name": payload["name"]}
        ),
    )

    def fake_import(path, payload):
        stock_calls.append((path, payload))
        return [{"transaction_id": 999}]

    monkeypatch.setattr(main, "grocy_post", fake_import)

    monkeypatch.setattr(
        main,
        "render_template",
        lambda request, template, context: context,
    )

    result = await main.import_receipt(
        FakeFormRequest({
            "include_0": "on",
            "product_0": "new",
            "new_product_name_0": "Coffee",
            "new_product_location_0": "3",
            "new_product_purchase_unit_0": "3",
            "new_product_stock_unit_0": "5",
            "new_product_conversion_factor_0": "2",
        }),
        "receipt-1",
    )

    assert result["grocy_error"] == "Grocy product list unavailable"
    assert result["items"][0].get("status") is None
    assert created_product_calls == []
    assert stock_calls == []
    assert mappings.saved == []
    assert aliases.saved == []
