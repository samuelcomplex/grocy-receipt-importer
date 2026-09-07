from abc import ABC, abstractmethod
from typing import ClassVar, TypedDict


class ReceiptMetadata(TypedDict, total=False):
    retailer: str
    store_org: str
    store_name: str
    store_address: str
    receipt_number: str
    date: str
    cashier: str


class ReceiptItem(TypedDict, total=False):
    kind: str
    description: str
    article_number: str
    quantity: str
    unit: str
    unit_price: str
    gross: str
    discount: str
    net: str


class ParsedReceipt(TypedDict):
    metadata: ReceiptMetadata
    items: list[ReceiptItem]


class ReceiptParser(ABC):
    """Interface for retailer receipt parser plugins."""

    retailer: ClassVar[str]
    theme: ClassVar[dict[str, str] | None] = None

    @abstractmethod
    def matches(self, text: str) -> bool:
        """Return True when this parser owns the receipt."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, text: str) -> ParsedReceipt:
        """Translate raw receipt text into the common receipt structure."""
        raise NotImplementedError
