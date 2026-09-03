from abc import ABC, abstractmethod


class ReceiptParser(ABC):
    """Interface for retailer receipt parser plugins."""

    @abstractmethod
    def matches(self, text: str) -> bool:
        """Return True when this parser owns the receipt."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, text: str) -> dict:
        """Translate raw receipt text into the common receipt structure."""
        raise NotImplementedError
