from __future__ import annotations

from app.receipt_model import receipt_from_parser_output
from plugins.base import ReceiptParser
from plugins.discovery import discover_parsers


class ContractParser(ReceiptParser):
    retailer = "ContractTest"

    def matches(self, text: str) -> bool:
        return text == "CONTRACT TEST RECEIPT"

    def parse(self, text: str) -> dict:
        return {
            "metadata": {
                "store_org": "TEST",
                "store_name": "Test Store",
                "receipt_number": "123",
                "date": "2026-09-08",
                "time": "12:00",
            },
            "items": [
                {
                    "kind": "product",
                    "description": "Test product",
                    "article_number": "1234567",
                    "quantity": "1",
                    "unit": "st",
                    "unit_price": "10,00",
                    "gross": "10,00",
                    "discount": "0,00",
                    "net": "10,00",
                }
            ],
        }


def test_parser_contract_produces_common_receipt_model():
    parser = ContractParser()

    assert parser.matches("CONTRACT TEST RECEIPT") is True

    parsed = parser.parse("CONTRACT TEST RECEIPT")
    receipt = receipt_from_parser_output(parsed, parser.retailer)

    assert receipt.retailer == "ContractTest"
    assert receipt.store_org == "TEST"
    assert receipt.store_name == "Test Store"
    assert receipt.receipt_number == "123"
    assert receipt.date.isoformat() == "2026-09-08"
    assert receipt.time.isoformat() == "12:00:00"

    assert len(receipt.items) == 1
    assert receipt.items[0].description == "Test product"
    assert receipt.items[0].article_number == "1234567"


def test_all_discovered_parsers_have_required_interface():
    parsers = discover_parsers()

    assert parsers

    for parser in parsers:
        assert isinstance(parser, ReceiptParser)
        assert parser.retailer
        assert callable(parser.matches)
        assert callable(parser.parse)
