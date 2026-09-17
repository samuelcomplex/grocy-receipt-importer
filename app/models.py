from __future__ import annotations

from datetime import date as Date, time as Time
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ItemKind(StrEnum):
    PRODUCT = "product"
    DEPOSIT = "deposit"
    DISCOUNT = "discount"
    OTHER = "other"


class ReceiptItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str
    article_number: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    gross: Decimal | None = None
    discount: Decimal | None = None
    net: Decimal | None = None
    kind: ItemKind = ItemKind.PRODUCT
    ignored: bool = False


class Receipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    retailer: str
    store_name: str | None = None
    store_org: str | None = None
    store_address: str | None = None
    date: Date | None = None
    time: Time | None = None
    receipt_no: str | None = None
    cashier: str | None = None
    items: list[ReceiptItem]
