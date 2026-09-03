# Contributing

Thank you for contributing to Grocy Receipt Importer.

Contributions are especially welcome for adding support for new retailers and improving existing receipt parsers.

## Adding a new retailer

Retailer-specific receipt handling belongs in a plugin.

Create a new file under:

```text
plugins/
```

For example:

```text
plugins/coop.py
```

The plugin should inherit from `ReceiptParser`:

```python
from .base import ReceiptParser


class CoopParser(ReceiptParser):
    retailer = "Coop"

    def matches(self, text: str) -> bool:
        # Return True only for receipts belonging to this retailer.
        ...

    def parse(self, text: str) -> dict:
        # Return the common receipt structure.
        ...
```

You do not need to modify `app.py` or a central parser registry.

The application discovers parser plugins automatically.

## Keep plugins independent

A parser should only recognize and translate receipt text.

Plugins should not:

- call the Grocy API
- access the SQLite database
- create Grocy products
- import stock
- save product mappings
- contain web routes
- modify templates

The core application is responsible for those operations.

See [`docs/architecture.md`](docs/architecture.md) and [`docs/plugin-development.md`](docs/plugin-development.md).

## Tests

Please add tests for new parsers under:

```text
tests/plugins/
```

At minimum, test:

- positive retailer recognition
- negative recognition cases
- product parsing
- article numbers
- quantities
- units
- prices
- discounts
- unusual or missing fields

Run the existing test suite before submitting a pull request.

## Receipt fixtures

Receipt fixtures are useful for parser development and regression testing.

However, never commit an unredacted real receipt.

Remove or anonymize:

- names
- addresses
- payment information
- loyalty/customer identifiers
- personal identifiers
- unnecessary transaction identifiers

Keep only the information needed to test the parser.

## Common receipt structure

Plugins should return:

```python
{
    "metadata": {...},
    "items": [...]
}
```

Avoid adding retailer-specific fields to the common structure unless there is a strong reason.

If a new retailer requires a change to the shared interface, explain the requirement in the pull request before making the change.

## Code style

Keep parser code focused and readable.

Prefer small helper functions when they make complicated receipt parsing easier to understand.

Avoid changing unrelated parts of the application in a retailer-specific pull request.

## Pull requests

A new retailer parser should normally include:

1. The parser implementation.
2. Tests.
3. Sanitized receipt fixtures where useful.
4. Documentation for important retailer-specific assumptions.

The pull request description should explain:

- which retailer is being added
- which receipt formats were tested
- any known limitations
- any assumptions made while parsing

## Before submitting

Please check that:

- the application still starts
- existing parsers still work
- the new parser is automatically discovered
- tests pass
- no secrets are included
- no real personal receipt data is included
- retailer-specific logic has not been added to the core

Thank you for helping make the importer useful for more Grocy users.
