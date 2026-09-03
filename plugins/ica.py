from .base import ReceiptParser


class ICAParser(ReceiptParser):
    retailer = "ICA"

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
            lines = [
                re.sub(r"\s+", " ", line).strip()
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

            # Store name
            for line in lines:
                if "MAXI ICA" in line.upper():
                    metadata["store_name"] = line
                    break

            # Address
            for i, line in enumerate(lines):
                if re.match(r"^\d{5}\s+", line):
                    metadata["address"] = " ".join(lines[max(0, i - 1):i + 1])
                    break

            # Metadata block used by the ICA PDF
            for i, line in enumerate(lines):
                if line == "Datum" and i + 6 < len(lines):
                    values = lines[i + 1:i + 7]

                    if re.match(r"^\d{4}-\d{2}-\d{2}$", values[0]):
                        metadata["date"] = values[0]

                    if len(values) > 1:
                        metadata["time"] = values[1]

                    if len(values) > 2:
                        metadata["store_org"] = values[2]

                    if len(values) > 3:
                        metadata["receipt_no"] = values[3]

                    if len(values) > 4:
                        metadata["register"] = values[4]

                    if len(values) > 5:
                        metadata["cashier"] = values[5]

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
                        "unit": normalize_unit(match.group("unit")),
                        "gross": money_str(gross),
                        "discount": "0,00",
                        "net": money_str(gross),
                        "kind": "product",
                        "grocy_product_id": None,
                        "grocy_product_name": "",
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
                        "grocy_product_id": None,
                        "grocy_product_name": "",
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

            return metadata, items

