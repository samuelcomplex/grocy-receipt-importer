# Plugin Development

Receipt parsers are implemented as plugins.

The core application does not contain retailer-specific receipt detection or parsing logic. A plugin is responsible only for:

1. Deciding whether it recognizes a receipt.
2. Parsing the receipt text into the common receipt structure.

The core application handles review, product mappings, database storage, and importing stock into Grocy.

## Plugin interface

Every parser inherits from `ReceiptParser`:

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

The plugin interface is defined in `plugins/base.py`.

## `matches()`

`matches(text)` receives the raw text extracted from the uploaded PDF.

Return `True` only when the receipt belongs to your retailer.

Detection should be specific enough to avoid claiming receipts belonging to another plugin.

For example:

```python
def matches(self, text: str) -> bool:
    upper = text.upper()

    return (
        "COOP" in upper
        and "KVITTO" in upper
    )
```

Keep retailer-specific detection inside the plugin.

Do not add retailer checks to `app.py`.

## `parse()`

`parse(text)` converts the retailer's receipt format into the common receipt structure:

```python
{
    "metadata": {...},
    "items": [...]
}
```

A typical item contains information such as:

```python
{
    "article_number": "12345",
    "description": "Milk",
    "quantity": 2,
    "unit": "st",
    "net_price": 29.90,
    "discount": 0.0,
}
```

The parser should translate the retailer's terminology and formatting into these common fields.

The existing ICA parser is the reference implementation.

## What plugins should not do

A parser should not:

- call the Grocy API
- access the SQLite database
- create Grocy products
- import stock
- save product mappings
- modify application state
- contain web routes
- modify templates

The plugin should only translate receipt text into structured data.

This keeps plugins independent from the application and makes them easier to test.

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

Implement a `ReceiptParser` subclass in `coop.py`.

No changes to `app.py` are required.

The application automatically discovers parser classes in the `plugins/` directory.

## Parser discovery

The application scans `plugins/` for Python modules.

Files used by the plugin system itself are excluded:

- `__init__.py`
- `base.py`
- `discovery.py`

Any class that inherits from `ReceiptParser` is automatically registered.

This means contributors do not need to edit a central parser registry.

## Testing

Every new parser should include tests.

Tests should verify at least:

- receipts from the retailer are recognized
- receipts from other retailers are not recognized
- products are parsed correctly
- quantities are parsed correctly
- prices are parsed correctly
- discounts are handled correctly
- unusual or missing fields do not crash the parser

Receipt text fixtures should be sanitized and must not contain personal information.

## Receipt data

Do not commit real receipts containing personal or sensitive information.

When adding test fixtures:

- remove names
- remove addresses
- remove payment card information
- remove loyalty or customer identifiers
- remove transaction identifiers where appropriate

Keep only the receipt information required to test the parser.

## Pull requests

A new retailer parser should normally include:

1. The parser implementation.
2. Tests.
3. Sanitized receipt fixtures where useful.
4. Documentation for retailer-specific assumptions.
5. Any changes to the common receipt format, if genuinely required.

Avoid changing the core application just to support one retailer.

If a retailer requires information that does not fit the existing common structure, explain the requirement in the pull request before changing the shared interface.
