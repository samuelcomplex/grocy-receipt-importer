import re

from .base import ReceiptParser
from common import money, money_str, quantity


PRODUCT_RE = re.compile(
    r"^(?P<description>.+?)\s+"
    r"(?P<article>\d{7})\s+"
    r"(?P<unit_price>-?\d+,\d{2})\s+"
    r"(?P<quantity>\d+(?:,\d+)?)\s+"
    r"(?P<unit>kg|g|l|ml|st)\s+"
    r"(?P<sum>-?\d+,\d{2})$",
    re.IGNORECASE,
)


DISCOUNT_RE = re.compile(
    r"^(?P<description>.+?)\s+(?P<amount>-\d+,\d{2})$"
)


class ICAParser(ReceiptParser):
    retailer = "ICA"

    theme = {
        "accent": "#e30613",
        "accent_text": "#ffffff",
        "accent_soft": "#ffe5e7",
    }

    def matches(self, text: str) -> bool:
        upper = text.upper()
        return (
            "ICA" in upper
            and (
                "KVITTOKOPIA" in upper
                or "ORGANISATIONSNR" in upper
            )
        )

    def parse(self, text):
            layout_lines = [
                line.rstrip()
                for line in text.splitlines()
                if line.strip()
            ]

            lines = [
                re.sub(r"\s+", " ", line).strip()
                for line in layout_lines
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

            # Store name
            for line in lines:
                if "MAXI ICA" in line.upper():
                    metadata["store_name"] = line
                    break

            # Address
            street = ""
            city = ""

            for line in layout_lines:
                street_match = re.match(
                    r"^\s*(.*?)\s{2,}Datum\s+\d{4}-\d{2}-\d{2}\s*$",
                    line,
                    re.IGNORECASE,
                )
                if street_match:
                    street = street_match.group(1).strip()

                city_match = re.match(
                    r"^\s*(\d{5}\s+[^\s]+(?:\s+[^\s]+)*)\s{2,}Tid\s+\d{2}:\d{2}\s*$",
                    line,
                    re.IGNORECASE,
                )
                if city_match:
                    city = city_match.group(1).strip()

            if street and city:
                metadata["address"] = f"{street} {city}"
            else:
                for i, line in enumerate(lines):
                    if re.match(r"^\d{5}\s+", line):
                        metadata["address"] = " ".join(
                            lines[max(0, i - 1):i + 1]
                        )
                        break

            # Metadata in layout extraction is kept in the right-hand column.
            metadata_fields = {
                "Datum": "date",
                "Tid": "time",
                "Org nr": "store_org",
                "Kvitto nr": "receipt_no",
                "Kassa": "register",
                "Kassör": "cashier",
            }

            for line in layout_lines:
                for label, field in metadata_fields.items():
                    match = re.search(
                        rf"{re.escape(label)}\s+(.+?)\s*$",
                        line,
                        re.IGNORECASE,
                    )
                    if match:
                        metadata[field] = match.group(1).strip()
                        break

            # Fall back to the original six-label/six-value representation.
            metadata_labels = list(metadata_fields)
            for i in range(len(lines) - len(metadata_labels)):
                if lines[i:i + len(metadata_labels)] == metadata_labels:
                    values_start = i + len(metadata_labels)
                    values = lines[
                        values_start:values_start + len(metadata_labels)
                    ]

                    for field, value in zip(metadata_fields.values(), values):
                        metadata[field] = value

                    break

            items = []

            for line in lines:
                # Product
                match = PRODUCT_RE.match(line)

                if match:
                    unit_price = money(match.group("unit_price"))
                    qty = quantity(match.group("quantity"))

                    gross = unit_price * qty

                    items.append({
                        "description": match.group("description").lstrip("*").strip(),
                        "article_number": match.group("article"),
                        "unit_price": money_str(unit_price),
                        "quantity": str(qty),
                        "unit": match.group("unit").strip().lower(),
                        "gross": money_str(gross),
                        "discount": "0,00",
                        "net": money_str(gross),
                        "kind": "product",
                    })

                    continue

                # Pant/deposit
                if line.lower().startswith("pant "):
                    parts = line.split()

                    amount = money(parts[-1])

                    items.append({
                        "description": "Pant/deposit",
                        "article_number": "",
                        "unit_price": "",
                        "quantity": "",
                        "unit": "",
                        "gross": "0,00",
                        "discount": "0,00",
                        "net": money_str(amount),
                        "kind": "deposit",
                    })

                    continue

                # Discount immediately following a product
                match = DISCOUNT_RE.match(line)

                if (
                    match
                    and items
                    and items[-1]["kind"] == "product"
                    and not line.lower().startswith("erhållen rabatt")
                ):
                    discount = money(match.group("amount"))

                    current_discount = money(items[-1]["discount"])

                    items[-1]["discount"] = money_str(
                        current_discount + discount
                    )

                    items[-1]["net"] = money_str(
                        money(items[-1]["gross"])
                        + current_discount
                        + discount
                    )

            return {
                "metadata": metadata,
                "items": items,
            }

