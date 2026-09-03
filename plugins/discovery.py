import importlib
import inspect
from pathlib import Path

from .base import ReceiptParser


def discover_parsers():
    parsers = []

    plugin_dir = Path(__file__).parent

    for path in sorted(plugin_dir.glob("*.py")):
        if path.name in {"__init__.py", "base.py", "discovery.py"}:
            continue

        module_name = f"{__package__}.{path.stem}"
        module = importlib.import_module(module_name)

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, ReceiptParser)
                and cls is not ReceiptParser
                and cls.__module__ == module.__name__
            ):
                parsers.append(cls())

    return parsers


def find_parser(text: str):
    for parser in discover_parsers():
        if parser.matches(text):
            return parser

    return None
