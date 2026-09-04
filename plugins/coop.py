import re

from .base import ReceiptParser
from common import money, money_str, quantity


HEADER_FIELD_RE = re.compile(
    r"^(Kvitto|Datum|Kassör|Org\.Nr)\s+(.+)$"
)

ITEM_RE = re.compile(
    r"^(?P<description>.+?)\s+(?P<amount>-?[\d.]*\d,\d{2})$"
)

QTY_RE = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>STK|st|kg)\s*[xX]\s*"
    r"(?P<unit_price>[\d.]*\d,\d{2})$",
    re.IGNORECASE,
)

TOTAL_RE = re.compile(r"^Total SEK\s+([\d.]*\d,\d{2})$")

DEPOSIT_PREFIXES = ("PANT",)


class CoopParser(ReceiptParser):
    retailer = "Coop"

    theme = {
        "accent": "#00643c",
        "accent_text": "#ffffff",
        "accent_soft": "#e2f1e8",
    }

    def matches(self, text: str) -> bool:
        upper = text.upper()

        return (
            "COOP" in upper
            and "ELEKTRONISKT KASSAKVITTO" in upper
        )

    def parse(self, text: str) -> dict:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        metadata = {
            "store_name": "",
            "address": "",
            "store_org": "",
            "date": "",
            "time": "",
            "receipt_no": "",
            "register": "",
            "cashier": "",
        }

        header_fields = {}
        header_done_idx = None

        for idx, line in enumerate(lines):
            match = HEADER_FIELD_RE.match(line)

            if match:
                header_fields[match.group(1)] = match.group(2).strip()
                header_done_idx = idx

        # The lines before "Elektroniskt kassakvitto" (or before the first
        # header field, as a fallback) are the store name/address block.
        try:
            preamble_end = next(
                i for i, line in enumerate(lines)
                if line.startswith("Elektroniskt")
            )
        except StopIteration:
            preamble_end = header_done_idx or 0

        preamble = lines[:preamble_end]

        if len(preamble) > 0:
            metadata["store_name"] = preamble[0]

        if len(preamble) > 1:
            metadata["address"] = preamble[1]

        metadata["receipt_no"] = header_fields.get("Kvitto", "")
        metadata["cashier"] = header_fields.get("Kassör", "")
        metadata["store_org"] = header_fields.get("Org.Nr", "")

        datum = header_fields.get("Datum", "")

        if " " in datum:
            date_part, time_part = datum.split(" ", 1)
        else:
            date_part, time_part = datum, ""

        metadata["date"] = date_part
        metadata["time"] = time_part

        if header_done_idx is None:
            return {"metadata": metadata, "items": []}

        total_idx = None

        for idx in range(header_done_idx + 1, len(lines)):
            if TOTAL_RE.match(lines[idx]):
                total_idx = idx
                break

        item_lines = lines[
            header_done_idx + 1:
            total_idx if total_idx is not None else len(lines)
        ]

        items = []

        for line in item_lines:
            qty_match = QTY_RE.match(line)

            if qty_match and items:
                unit_price = money(qty_match.group("unit_price"))

                items[-1]["quantity"] = str(quantity(qty_match.group("quantity")))
                items[-1]["unit"] = qty_match.group("unit").lower()
                items[-1]["unit_price"] = money_str(unit_price)

                continue

            match = ITEM_RE.match(line)

            if not match:
                continue

            description = match.group("description").strip()
            amount = money(match.group("amount"))

            if amount < 0 and items:
                # A discount line applies to the item immediately preceding it.
                current_discount = money(items[-1]["discount"])
                new_discount = current_discount + amount

                items[-1]["discount"] = money_str(new_discount)
                items[-1]["net"] = money_str(
                    money(items[-1]["gross"]) + new_discount
                )

                continue

            kind = (
                "deposit"
                if description.upper().startswith(DEPOSIT_PREFIXES)
                else "product"
            )

            items.append({
                "description": description,
                "article_number": "",
                "unit_price": "",
                "quantity": "1",
                "unit": "st",
                "gross": money_str(amount),
                "discount": "0,00",
                "net": money_str(amount),
                "kind": kind,
                "grocy_product_id": None,
                "grocy_product_name": "",
            })

        return {
            "metadata": metadata,
            "items": items,
        }
