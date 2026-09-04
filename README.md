# Grocy Receipt Importer

**Version 0.2.5**

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
- Quantity and unit handling
- Discounts and receipt metadata
- Best-before and purchase-date support
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
4. Select the items you want to import.
5. Click **Import items**.
6. Successfully imported items are marked as imported and cannot be imported again accidentally.

Receipts remain available in Recent receipts until they are deleted.

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
uvicorn app:app --reload
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

The current release is **v0.2.5**.

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

## What's new in 0.2.5

- Undo imported Grocy transactions directly from the receipt review.
- Unlink saved product mappings from the receipt review.
- Receipt units no longer require Grocy quantity-unit conversions.
- Import failures are shown directly on the affected receipt item.

## License

This project is licensed under the MIT License.
