# Grocy Receipt Importer

**Version 0.3.3**

A self-hosted web application that extracts receipt data from PDF files, lets you review and map products, and imports selected items into [Grocy](https://grocy.info/).

Retailer-specific receipt formats are implemented as plugins, making it possible to add support for additional retailers without changing the core application.

## Features

- PDF receipt text extraction
- Automatic retailer/parser detection
- Plugin-based receipt parsing
- Review receipts before importing
- Select which items to import
- Import button showing the number of selected items
- Protection against re-importing already imported items
- Saved article-number to Grocy-product mappings
- Configure and stage new Grocy products directly from the receipt review
- Select Grocy location, purchase unit, and stock unit when creating products
- Product-specific purchase-to-stock quantity conversions
- Quantity conversion to the selected Grocy product's stock unit
- Receipt line prices calculated as price per imported stock unit
- Discounts and receipt metadata
- Best-before and purchase-date support
- Undo imported Grocy transactions
- Unlink saved article-number mappings
- Receipt history
- Delete receipts from the importer
- English and Swedish interface
- Persistent language selection
- Light/dark mode
- Docker deployment
- Extensible parser architecture

## Supported retailers

### ICA

ICA receipt parsing is currently supported through:

```text
plugins/ica.py
```

### Coop

Coop receipt parsing is currently supported through:

```text
plugins/coop.py
```

Additional retailers can be added as plugins.

## Requirements

- Docker
- Docker Compose
- A running Grocy instance
- A Grocy API key
- Receipt PDFs containing selectable/extractable text

## Installation

Clone the repository:

```bash
git clone https://github.com/samuelcomplex/grocy-receipt-importer.git
cd grocy-receipt-importer
```

Create the local environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
GROCY_BASE_URL=http://your-grocy-server:9283
GROCY_API_KEY=your-grocy-api-key
TZ=Europe/Stockholm
```

Start the application:

```bash
docker compose up -d --build
```

The web interface will be available on port `9284`:

```text
http://your-server:9284
```

## Configuration

Configuration is provided through `.env`.

| Variable | Description |
|---|---|
| `GROCY_BASE_URL` | Base URL of the Grocy installation |
| `GROCY_API_KEY` | Grocy API key used for stock imports |
| `TZ` | Time zone used by the application |

Never commit `.env` to GitHub. The repository contains `.env.example` as a template.

## Data

Application data is stored in:

```text
data/
```

The SQLite database is:

```text
data/receipts.sqlite3
```

The `data/` directory is intentionally excluded from Git so local receipt history and mappings are not committed to the repository.

### Deleting receipts

Deleting a receipt removes it from the importer database.

It does **not** remove stock or transactions that have already been imported into Grocy.

## Using the importer

1. Upload a receipt PDF.
2. Let the application detect and parse the retailer.
3. Review the receipt and check the product matches.
4. For unmatched items, select **New product** and configure the Grocy product if needed.
5. Select the items you want to import.
6. Click **Import items**.
7. Successfully imported items are marked as imported and cannot be imported again accidentally.

Receipts remain available in Recent receipts until they are deleted.

### Creating new Grocy products

When an item cannot be matched to an existing Grocy product, it can be configured directly from the receipt review.

The configuration allows you to select:

- Grocy product name
- Location
- Purchase quantity unit
- Stock quantity unit
- Purchase-to-stock conversion when the units differ

The product is staged before the receipt is imported. This allows the product configuration to be reviewed as part of the receipt workflow.

## Grocy quantity units and receipt prices

When importing a receipt, the importer treats each receipt item's `net` value as the **total price paid for that receipt line**.

The importer converts the receipt quantity into the selected Grocy product's **stock quantity unit** and then calculates the price sent to Grocy as:

`receipt line total / imported stock amount = price per stock unit`

For example, a receipt line containing `1.79 kg` with a total price of `211.76` is imported as:

- Stock amount: `1.79 kg`
- Price per stock unit: `211.76 / 1.79 ≈ 118.30 kr/kg`
- Stock value: `211.76 kr`

For this reason, the Grocy product's stock quantity unit is especially important.

When creating products directly in Grocy, choose a stock unit that matches the quantity unit used on the receipt whenever possible. For example, use `kg` for a receipt item reported in kilograms, or `piece` for an item reported in pieces.

If the purchase unit and stock unit differ, a product-specific Grocy quantity-unit conversion must describe how the purchased quantity becomes stock. The importer uses that conversion when calculating both the imported stock amount and the price per stock unit.

## Languages

The interface currently supports:

- English (`EN`)
- Swedish (`SV`)

The selected language is remembered by the browser.

Translations are stored in:

```text
translations/
├── en.json
└── sv.json
```

## Plugins

Retailer parsers live in:

```text
plugins/
```

The application automatically discovers parser classes that inherit from `ReceiptParser`.

A new retailer can normally be added by creating a new plugin without modifying the core application.

See [docs/plugin-development.md](docs/plugin-development.md) for details.

## Development

For local development without Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For normal deployment, Docker Compose is recommended.

## Testing

Parser tests should be added under:

```text
tests/plugins/
```

Tests should cover:

- retailer recognition
- rejection of unrelated receipts
- product parsing
- quantities and units
- prices and discounts
- unusual or missing fields

Receipt fixtures must be sanitized before being committed.

Do not commit real receipts containing personal, payment, customer, or other sensitive information.

Run the complete test suite before submitting changes:

```bash
DATA_DIR=/tmp/grocy-receipt-importer-test .venv/bin/python -m pytest tests
```

## Documentation

- [Architecture](docs/architecture.md)
- [Plugin development](docs/plugin-development.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Versioning

The current version is stored in:

```text
VERSION
```

The project follows [Semantic Versioning](https://semver.org/):

```text
MAJOR.MINOR.PATCH
```

The current release is **v0.3.2**.

See [CHANGELOG.md](CHANGELOG.md) for the release history.

## Security

Do not commit:

- `.env`
- Grocy API keys
- real receipt PDFs containing personal information
- customer or loyalty identifiers
- payment information
- private database files

If you discover a security issue, please report it privately rather than opening a public issue with sensitive details.

## What's new in 0.3.2

- Refactored the application into separate modules for the web layer, Grocy integration, product matching, receipt models, and storage.
- Added typed receipt and receipt-item models and expanded automated test coverage.
- Added the ability to configure and stage new Grocy products directly from the receipt review.
- Added Grocy location, purchase-unit, and stock-unit selection when creating new products.
- Added product-specific purchase-to-stock quantity conversions for products whose purchase and stock units differ.
- Receipt quantities are converted to the selected Grocy product's stock unit during import.
- Receipt line prices are treated as total line prices and converted to price per imported stock unit before being sent to Grocy.
- Added undo and unlink actions to the receipt review.
- Improved import error handling, receipt status handling, and JSON response handling.

## What's new in 0.2.5

- Undo imported Grocy transactions directly from the receipt review.
- Unlink saved product mappings from the receipt review.
- Receipt units no longer require Grocy quantity-unit conversions.
- Import failures are shown directly on the affected receipt item.

## License

This project is licensed under the MIT License.
