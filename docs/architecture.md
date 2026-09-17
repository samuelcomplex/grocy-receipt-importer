# Architecture

## Overview

Grocy Receipt Importer separates the core application from retailer-specific receipt parsing.

The application is structured around a clear boundary:

```text
Receipt PDF
    |
    v
PDF text extraction (layout mode)
    |
    v
Plugin discovery
    |
    v
Retailer parser
    |
    v
Common receipt structure
    |
    v
Review and product mapping
    |
    v
Selected item import
    |
    v
Grocy
```

The key architectural principle is that retailer-specific receipt knowledge belongs in plugins. The core application should operate on a common receipt representation and should not contain retailer-specific parsing rules.

## Core application

The core application is responsible for:

- accepting receipt PDF uploads
- extracting receipt text from PDFs using `pypdf` with `extraction_mode="layout"`
- discovering parser plugins
- selecting the matching parser
- applying saved product mappings
- storing receipt information
- displaying the receipt review interface
- communicating with Grocy
- importing selected receipt items
- handling quantities, units, prices, and dates
- tracking receipt and item status
- managing receipt history
- providing UI translations and language selection
- staging/configuring new Grocy products from unmatched receipt items

The core should not contain retailer-specific parsing rules.

Current core modules include:

```text
app/
├── __init__.py
├── config.py
├── grocy.py
├── main.py
├── models.py
├── product_matching.py
├── product_service.py
├── receipt_model.py
├── storage.py
└── web.py
```

The previous monolithic `app.py` application has been replaced by these modules.

### Core module responsibilities

- `app/main.py` — application routes and the main receipt import/review workflow.
- `app/grocy.py` — Grocy API communication helpers.
- `app/product_service.py` — Grocy product creation/staging, product configuration, quantity-unit conversion handling, and related product operations.
- `app/product_matching.py` — matching receipt items to Grocy products and saved mappings.
- `app/receipt_model.py` — receipt and receipt-item domain structures.
- `app/models.py` — shared typed application models.
- `app/storage.py` — receipt, mapping, and related persistent storage.
- `app/config.py` — application configuration.
- `app/web.py` — web/application support functionality.

## Parser plugins

Retailer-specific parsing lives under `plugins/`.

Current plugin tree:

```text
plugins/
├── __init__.py
├── base.py
├── discovery.py
└── ica.py
```

The parser contract is centered on:

```text
matches(text) -> bool
parse(text) -> dict
```

The core application passes layout-preserved PDF text to these methods. Parsers should assume that whitespace and column positioning may carry meaning for the retailer's receipt format.

PDF extraction is a core application responsibility. Parser plugins must not perform PDF extraction themselves or choose a different extraction mode.

A parser is responsible for:

- recognizing whether the receipt text belongs to its retailer
- parsing retailer-specific receipt text
- normalizing the result into the common receipt structure

A parser must not communicate with Grocy.

### Plugin discovery

Plugins are discovered automatically.

The discovery system looks for parser classes inheriting from the common `ReceiptParser` base class. The base class and discovery mechanism do not contain retailer-specific logic.

To add a retailer:

1. Add a new plugin module under `plugins/`.
2. Implement the `ReceiptParser` contract.
3. Implement retailer recognition in `matches()`.
4. Implement retailer-specific parsing in `parse()`.
5. Return the common receipt structure.
6. Add parser tests and sanitized receipt fixtures as appropriate.

There is no central retailer registry that must be modified for each new plugin.

## Common receipt structure

Plugins normalize their output into a common receipt representation used by the core application.

Conceptually:

```python
{
    "metadata": {...},
    "items": [...]
}
```

Receipt items contain importer-relevant information such as:

- article number
- description
- quantity
- unit
- gross price
- discount
- net price

The common structure represents the information required by the importer rather than every field that may exist in an individual retailer's receipt format.

For receipt pricing, the `net` value represents the total price for the receipt line. The core import workflow calculates the price per imported Grocy stock unit from the line total and the final stock quantity.

## Responsibility boundaries

### Core application

The core owns:

- PDF handling and layout-preserving text extraction
- plugin discovery
- receipt parsing orchestration
- database/storage access
- Grocy API communication
- product matching
- saved article-number mappings
- receipt storage
- receipt review and import state
- quantity and unit handling
- price handling
- new Grocy product staging/configuration
- receipt history
- translations

### Plugins

Plugins own:

- retailer recognition
- retailer-specific receipt parsing
- retailer-specific normalization into the common receipt structure

### Plugins must not

Plugins should not:

- call the Grocy API
- access the application database
- create or modify Grocy products
- manage Grocy stock
- manage saved product mappings
- define web routes
- render templates
- implement UI translations

This separation keeps retailer-specific knowledge isolated and allows the core application to evolve without rewriting every parser.

## Receipt import lifecycle

The receipt import lifecycle is:

1. Upload receipt PDF.
2. Extract receipt text using layout mode.
3. Discover available parsers.
4. Select the parser that recognizes the receipt.
5. Parse the receipt.
6. Apply saved product mappings and product matching.
7. Store the receipt and its items.
8. Display the receipt review.
9. Select items for import.
10. Import selected items into Grocy.
11. Mark successfully imported items as protected from re-import.
12. Keep the receipt available in history until it is deleted.

Unmatched items can also be configured as new Grocy products from the receipt review. Product configuration is staged before the receipt item is imported.

If an import fails for an item, the failure is shown on the affected item and the item is not treated as successfully imported.

## Product mappings

Saved product mappings associate a retailer/article number with a Grocy product.

The mapping key includes the retailer/store context together with the article number so that article numbers from different retailers do not have to share the same mapping.

Mappings are stored independently from receipt records.

The receipt review also allows an existing article-number mapping to be unlinked.

## New Grocy product staging

When an unmatched receipt item needs to become a Grocy product, the receipt review can stage the required product configuration before import.

The configuration includes:

- product name
- Grocy location
- purchase quantity unit
- stock quantity unit
- purchase-to-stock quantity conversion

The staged product is then created/configured through the core Grocy product service rather than by the retailer parser.

The product-specific conversion is important when the purchase unit and stock unit differ. The application uses the resulting Grocy stock-unit quantity when importing receipt quantities.

Whenever possible, products created directly in Grocy should use a stock unit that matches the receipt quantity unit. When purchase and stock units differ, the Grocy product-specific conversion must describe the relationship between them.

## Quantities, units, and prices

Receipt units are treated as retailer metadata for matching and parsing. A receipt unit does not by itself require a global Grocy quantity-unit conversion merely to match a product.

When importing a receipt item, the application converts the receipt quantity into the selected Grocy product's stock unit using the product-specific Grocy conversion.

The receipt item's `net` price is the total price for the receipt line, not a per-stock-unit price.

Therefore the import price is calculated as:

```text
price per stock unit = receipt line total / imported stock amount
```

For example, a receipt line containing 1.79 kg with a total price of 211.76 results in:

```text
211.76 / 1.79 = 118.3016759... kr/kg
```

The value sent to Grocy is the calculated price per imported stock unit.

When the purchase and stock units differ, the stock quantity must be calculated first and the line total divided by that final stock quantity. For example, if 2 packs correspond to 4 stock pieces and the receipt line total is 30, the imported stock quantity is 4 and the price is:

```text
30 / 4 = 7.5 per stock piece
```

This keeps receipt line totals from being incorrectly stored as per-unit prices.

## Import state

Receipt items use stable internal import states such as:

- `Imported`
- `Skipped`
- `Failed`

The UI translates these states for the selected language.

Successfully imported items are protected and cannot be imported again.

Undo operations can reverse imported Grocy transactions directly from the receipt review. After an undo, receipt/item status is updated so the review reflects the current import state.

## Receipt deletion

Deleting a receipt removes the receipt from the importer database.

Receipt deletion does not remove:

- Grocy products
- Grocy stock
- Grocy transactions
- other Grocy-side data

Undoing an import is a separate operation from deleting a receipt. A future rollback design would need to retain the relevant Grocy transaction IDs.

## Internationalization

The application supports English and Swedish.

Translations are stored in:

```text
translations/
├── en.json
└── sv.json
```

The application uses the translation helper for UI text and falls back to English when a translation is unavailable.

The application name remains fixed rather than being translated.

Language selection is persisted using the browser cookie.

## Web application structure

The web application is built around the modular `app/` package and the templates under `templates/`.

The main receipt review workflow includes:

- receipt upload and parsing
- product matching
- selection of receipt items
- new Grocy product configuration
- importing selected items
- undoing imported transactions
- unlinking saved mappings
- receipt history and deletion

JSON responses are handled explicitly by the application routes, while user-facing errors are shown in the receipt review where appropriate.

## Docker layout

The application is packaged for Docker.

The current application source layout inside the container is based on the refactored project structure:

```text
/app
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── grocy.py
│   ├── main.py
│   ├── models.py
│   ├── product_matching.py
│   ├── product_service.py
│   ├── receipt_model.py
│   ├── storage.py
│   └── web.py
├── plugins/
├── templates/
├── translations/
└── VERSION

/data
└── receipts.sqlite3
```

Receipt data is stored under `/data`.

Plugin code is part of the application package and is treated as application source rather than user-generated data.

## Data flow

The high-level data flow is:

```text
Receipt PDF
    |
    v
Text extraction
    |
    v
Plugin discovery
    |
    v
Retailer parser
    |
    v
Structured receipt data
    |
    +----------------------+
    |                      |
    v                      v
SQLite / receipt       Review / matching
storage                    |
                            v
                     Selected imports
                            |
                            v
                          Grocy
```

The core application owns the transitions between these stages.

Plugins only recognize and parse retailer-specific receipt text and return normalized data. They do not participate in Grocy operations, persistence, product matching, or web presentation.

## Architectural principles

The main architectural principles are:

1. **Keep retailer knowledge in plugins.**
   Retailer-specific formats and parsing rules belong under `plugins/`.

2. **Keep Grocy integration in the core.**
   Plugins never communicate directly with Grocy.

3. **Use a common receipt model.**
   Parser output is normalized before the rest of the application processes it.

4. **Keep product operations in the product service.**
   Product creation, configuration, and quantity conversion are handled centrally.

5. **Treat receipt line prices consistently.**
   Parsed `net` values are line totals; the core calculates the corresponding price per imported stock unit.

6. **Protect successfully imported items.**
   The importer must not accidentally import the same receipt item twice.

7. **Keep importer data separate from Grocy data.**
   Deleting an importer receipt does not delete or roll back Grocy data.

8. **Keep UI concerns out of parsers.**
   Templates, routes, and translations belong to the application layer.

This architecture allows new retailers and future core features to be added without coupling retailer-specific parsing to Grocy or the web application.
