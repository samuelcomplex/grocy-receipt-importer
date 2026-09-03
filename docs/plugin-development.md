# Plugin Development

Receipt parsers are implemented as plugins under the `plugins/` directory.

The core application handles receipt storage, product mapping, review, and Grocy imports. A plugin is responsible only for recognizing and parsing its retailer's receipt format.

## Plugin interface

Every retailer parser inherits from `ReceiptParser`.

A minimal plugin looks like this:

```python
from .base import ReceiptParser


class CoopParser(ReceiptParser):
    retailer = "Coop"

    def matches(self, text: str) -> bool:
        return "COOP" in text.upper()

    def parse(self, text: str) -> dict:
        return {
            "metadata": {
                "store_name": "Coop",
            },
            "items": [],
        }
```

The base class is defined in:

```text
plugins/base.py
```

## `matches()`

The `matches()` method receives the text extracted from the uploaded PDF.

Return `True` only when the receipt belongs to the retailer handled by the plugin.

Keep recognition specific enough to avoid false matches.

For example:

```python
def matches(self, text: str) -> bool:
    upper = text.upper()

    return (
        "COOP" in upper
        and "KVITTO" in upper
    )
```

Do not add retailer-specific checks to `app.py`.

## `parse()`

The `parse()` method converts retailer-specific receipt text into the common receipt structure:

```python
{
    "metadata": {...},
    "items": [...]
}
```

Receipt items may contain fields such as:

```python
{
    "article_number": "12345",
    "description": "Milk",
    "quantity": 2,
    "unit": "st",
    "gross": 29.90,
    "discount": 0.0,
    "net": 29.90,
}
```

Use the existing parser implementation as the reference for the fields currently expected by the application.

The parser should normalize retailer-specific terminology and formatting into the common structure.

## What plugins should not do

Plugins should not:

- call the Grocy API
- access the SQLite database
- create Grocy products
- import stock
- save product mappings
- contain web routes
- modify templates
- manage application translations

Those responsibilities belong to the core application.

## Adding a new retailer

Create a new Python file in `plugins/`.

For example:

```text
plugins/
├── __init__.py
├── base.py
├── discovery.py
├── ica.py
└── coop.py
```

Implement a `ReceiptParser` subclass in the new file.

The application discovers parser classes automatically, so normally no changes to `app.py` or a central registry are required.

## Parser discovery

The plugin discovery system scans the `plugins/` directory for Python modules and identifies classes inheriting from `ReceiptParser`.

Framework modules such as `base.py` and `discovery.py` are not treated as retailer parsers.

This means a new retailer can normally be added by creating one new plugin file.

## Testing

New parsers should have tests covering:

- positive retailer recognition
- negative recognition cases
- product parsing
- article numbers
- quantities
- units
- prices
- discounts
- unusual or missing fields

Tests should be placed under:

```text
tests/plugins/
```

Receipt fixtures are useful for parser tests, but they must be sanitized before being committed.

## Receipt fixtures and privacy

Never commit an unredacted real receipt.

Remove or anonymize:

- names
- addresses
- payment information
- loyalty/customer identifiers
- personal identifiers
- unnecessary transaction identifiers

Keep only the information required to test the parser.

## Common receipt structure

The parser returns:

```python
{
    "metadata": {...},
    "items": [...]
}
```

Avoid adding retailer-specific fields unless there is a strong reason.

If a new retailer requires a change to the shared structure, document the requirement and consider whether the field is genuinely common enough to belong in the core model.

## Parser development checklist

Before submitting a new parser:

- [ ] `matches()` recognizes the intended retailer.
- [ ] `matches()` rejects unrelated receipts.
- [ ] `parse()` returns the common receipt structure.
- [ ] Article numbers are preserved where available.
- [ ] Product descriptions are parsed correctly.
- [ ] Quantities and units are handled correctly.
- [ ] Prices and discounts are handled correctly.
- [ ] Missing or unusual fields are handled safely.
- [ ] Tests cover positive and negative recognition.
- [ ] Test fixtures contain no personal information.
- [ ] The plugin contains no Grocy API logic.
- [ ] The plugin contains no database access.
- [ ] No core application changes are made unless genuinely necessary.
