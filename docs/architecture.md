# Architecture

## Overview

Grocy Receipt Importer separates the core application from retailer-specific receipt parsing.

```text
Receipt PDF
    │
    ▼
PDF text extraction
    │
    ▼
Plugin discovery
    │
    ▼
Retailer parser
    │
    ▼
Common receipt structure
    │
    ▼
Review and product mapping
    │
    ▼
Selected item import
    │
    ▼
Grocy
```

The key architectural principle is:

> Retailer-specific receipt knowledge belongs in plugins, not in the core application.

This allows new retailers to be added without modifying the core importer.

## Core application

The core application is responsible for:

- accepting receipt PDF uploads
- extracting text from PDFs
- discovering receipt parser plugins
- selecting a parser that recognizes the receipt
- applying saved product mappings
- storing receipt information
- displaying the review interface
- communicating with Grocy
- importing selected items into Grocy
- handling quantities, units, prices, and dates
- tracking receipt and item status
- managing receipt history
- managing UI translations and language selection

The core should not contain retailer-specific parsing rules.

## Parser plugins

Each supported retailer has its own parser plugin.

```text
plugins/
├── __init__.py
├── base.py
├── discovery.py
└── ica.py
```

A parser has two main responsibilities:

```python
matches(text) -> bool
parse(text) -> dict
```

### Recognition

`matches(text)` determines whether the plugin recognizes the receipt.

Recognition logic should be specific enough to avoid incorrectly claiming receipts belonging to another retailer.

### Parsing

`parse(text)` converts retailer-specific receipt text into the common receipt structure used by the core application.

The parser does not import anything into Grocy.

## Common receipt structure

Parsers return structured data containing metadata and receipt items:

```python
{
    "metadata": {...},
    "items": [...]
}
```

Items may contain information such as:

- article number
- description
- quantity
- unit
- gross price
- discount
- net price

The common structure should represent information required by the importer rather than reproducing every retailer's receipt format.

## Plugin discovery

Parser plugins are discovered automatically from the `plugins/` directory.

The discovery system loads Python modules and identifies classes inheriting from `ReceiptParser`.

Framework modules such as `base.py` and `discovery.py` are not treated as retailer parsers.

Adding a retailer normally requires only a new plugin file:

```text
plugins/new_retailer.py
```

No central parser registry is required.

## Responsibility boundaries

### Core

The core handles:

- PDF processing
- database access
- Grocy API communication
- product mappings
- receipt storage
- review state
- import state
- receipt history
- translations

### Plugins

Plugins handle:

- retailer recognition
- retailer-specific text parsing
- normalization into the common receipt structure

### Plugins should not

Plugins should not:

- call the Grocy API
- access the application database
- create Grocy products
- import stock
- save product mappings
- contain web routes
- modify templates
- manage translations

Keeping these boundaries makes parsers easier to test and maintain.

## Receipt import lifecycle

A typical receipt import follows these steps:

1. The user uploads a receipt PDF.
2. The core extracts text from the PDF.
3. Parser plugins are checked for a match.
4. The matching plugin parses the receipt.
5. Saved product mappings are applied where available.
6. The receipt is stored in the local SQLite database.
7. The user reviews the parsed receipt.
8. The user selects the items to import.
9. The selected items are imported into Grocy.
10. Successfully imported items are marked as `Imported`.
11. Imported items cannot be imported again accidentally.
12. Receipt history remains available until the receipt is deleted.

## Product mappings

When an item has an article number, the importer can associate that article number with a Grocy product.

Mappings are stored independently of individual receipts so that future receipts from the same retailer can benefit from previous selections.

The mapping key includes the retailer/store organization and article number.

## Import state

Receipt items have an internal status used by the application.

Important states include:

- `Imported`
- `Skipped`
- `Failed`

The UI translates these states according to the selected language, while the internal values remain stable for application logic.

An item marked `Imported` is not imported again when the receipt is submitted later.

## Receipt deletion

Deleting a receipt removes the receipt from the importer's database.

It does not:

- remove Grocy products
- remove Grocy stock
- undo previous Grocy transactions

Receipt deletion is therefore a history-management operation, not a rollback operation.

A future rollback feature would need to track the corresponding Grocy transaction IDs and explicitly undo those transactions.

## Internationalization

Translations are stored in:

```text
translations/
├── en.json
└── sv.json
```

Translation files are loaded when the application starts.

Templates use the translation helper:

```jinja2
{{ t("ui.receipt_review") }}
```

If a translation is missing in the selected language, the application falls back to English.

The application name remains fixed as:

```text
Grocy Receipt Importer
```

It is intentionally not translated.

The selected language is stored in a browser cookie.

## Docker layout

The Docker image contains the application code, templates, plugins, and translations:

```text
/app
├── app.py
├── common.py
├── plugins/
├── templates/
├── translations/
└── VERSION
```

Runtime data is mounted separately:

```text
/data
└── receipts.sqlite3
```

The plugins directory is mounted read-only so parser plugins can be updated independently of the application image.

## Data flow

```text
                 ┌──────────────────┐
                 │    Receipt PDF   │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │  Text extraction │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Plugin discovery │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Retailer parser  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Structured data  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ SQLite / Review  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Selected imports │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │      Grocy       │
                 └──────────────────┘
```

The core application owns the transitions between these stages. Plugins only own retailer-specific recognition and parsing.
