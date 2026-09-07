from plugins.base import ReceiptParser


class ExampleParser(ReceiptParser):
    retailer = "Example"
    theme = {
        "accent": "#123456",
        "accent_text": "#ffffff",
        "accent_soft": "#eeeeee",
    }

    def matches(self, text: str) -> bool:
        return "EXAMPLE" in text

    def parse(self, text: str) -> dict:
        return {
            "metadata": {
                "retailer": self.retailer,
            },
            "items": [
                {
                    "kind": "product",
                    "description": "Example product",
                    "article_number": "123",
                    "quantity": "1",
                    "unit": "st",
                    "net": "10.00",
                }
            ],
        }


def test_parser_contract_keeps_application_state_out_of_plugin_output():
    parser = ExampleParser()
    parsed = parser.parse("EXAMPLE")

    assert set(parsed) == {"metadata", "items"}
    assert parsed["metadata"]["retailer"] == "Example"

    item = parsed["items"][0]

    assert item["description"] == "Example product"
    assert item["article_number"] == "123"

    assert "grocy_product_id" not in item
    assert "grocy_product_name" not in item
    assert "status" not in item
    assert "transaction_id" not in item
    assert "match_type" not in item


def test_parser_theme_is_optional_parser_metadata():
    parser = ExampleParser()

    assert parser.retailer == "Example"
    assert parser.theme["accent"] == "#123456"
