from plugins.coop import CoopParser

# Sanitized fixtures based on real Coop electronic receipts. Trailing
# loyalty-card, payment and VAT-breakdown lines (which the parser does not
# use) have been removed.

SAMPLE_RECEIPT = """
Coop Änghagen Lidköping
53140 Lidköping
010-7417770
Coop Väst AB
Elektroniskt kassakvitto
Kvitto 156000-008-64020
Datum 2026-07-06 14:04
Kassör 1015
Org.Nr 5569813172
MER ÄPPLE 16,04
PANT PET 1X2KR 2,00
ÄGG FRIG M/L 20P 63,36
SAREK 8P 24,56
GLASS ALMOND 28,00
TRANBÄR OCH LINGON 28,35
GRILLKORV 75,00
PLASTKASSE 25L 3,95
Total SEK 241,26
Antal artiklar 8
"""

SAMPLE_RECEIPT_WITH_DISCOUNT = """
Coop Hällekis
53374 Hällekis
010-7416050
Coop Väst AB
Elektroniskt kassakvitto
Kvitto 156029-002-00947
Datum 2026-08-31 17:27
Kassör 101
Org.Nr 5569813172
MER ÄPPLE 17,51
PANT PET 1X2KR 2,00
MARSIPANBRÖD ORIG 30,20
2 STK x 15,10
Marsipanbröd 2 för 22kr -8,20
Total SEK 41,51
Antal artiklar 4
Erhållna rabatter 8,20
"""

ICA_RECEIPT = """
MAXI ICA Stormarknad Exempel
12345 Exempelstad
Org nr
Kvittokopia
"""


def test_matches_coop_receipt():
    assert CoopParser().matches(SAMPLE_RECEIPT) is True


def test_matches_rejects_other_retailers():
    assert CoopParser().matches(ICA_RECEIPT) is False


def test_matches_rejects_unrelated_text():
    assert CoopParser().matches("Just some unrelated text") is False


def test_parse_metadata():
    parsed = CoopParser().parse(SAMPLE_RECEIPT)
    metadata = parsed["metadata"]

    assert metadata["store_name"] == "Coop Änghagen Lidköping"
    assert metadata["address"] == "53140 Lidköping"
    assert metadata["store_org"] == "5569813172"
    assert metadata["date"] == "2026-07-06"
    assert metadata["time"] == "14:04"
    assert metadata["receipt_no"] == "156000-008-64020"
    assert metadata["cashier"] == "1015"
    assert metadata["register"] == ""


def test_parse_items_basic():
    items = CoopParser().parse(SAMPLE_RECEIPT)["items"]

    assert len(items) == 8

    descriptions = [item["description"] for item in items]
    assert descriptions == [
        "MER ÄPPLE",
        "PANT PET 1X2KR",
        "ÄGG FRIG M/L 20P",
        "SAREK 8P",
        "GLASS ALMOND",
        "TRANBÄR OCH LINGON",
        "GRILLKORV",
        "PLASTKASSE 25L",
    ]

    for item in items:
        assert item["article_number"] == ""
        assert item["grocy_product_id"] is None
        assert item["grocy_product_name"] == ""

    pant = items[1]
    assert pant["kind"] == "deposit"
    assert pant["net"] == "2,00"

    egg = items[2]
    assert egg["kind"] == "product"
    assert egg["quantity"] == "1"
    assert egg["unit"] == "st"
    assert egg["gross"] == "63,36"
    assert egg["discount"] == "0,00"
    assert egg["net"] == "63,36"


def test_parse_item_with_quantity_and_discount():
    items = CoopParser().parse(SAMPLE_RECEIPT_WITH_DISCOUNT)["items"]

    descriptions = [item["description"] for item in items]
    assert descriptions == ["MER ÄPPLE", "PANT PET 1X2KR", "MARSIPANBRÖD ORIG"]

    marsipan = items[2]
    assert marsipan["kind"] == "product"
    assert marsipan["quantity"] == "2"
    assert marsipan["unit"] == "stk"
    assert marsipan["unit_price"] == "15,10"
    assert marsipan["gross"] == "30,20"
    assert marsipan["discount"] == "-8,20"
    assert marsipan["net"] == "22,00"


def test_parse_handles_missing_header_gracefully():
    parsed = CoopParser().parse("Not a real receipt at all")

    assert parsed["items"] == []
    assert parsed["metadata"]["store_name"] == ""
