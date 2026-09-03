# Grocy Receipt Importer

A self-hosted web application that extracts receipt data from PDF files, lets you review and map products, and imports selected items into [Grocy](https://grocy.info/).

Retailer-specific receipt formats are implemented as plugins, so support for additional retailers can be added without changing the core application.

## Features

- PDF receipt text extraction
- Automatic retailer/parser detection
- Plugin-based receipt parsing
- Review before importing into Grocy
- Saved article-number to Grocy-product mappings
- Quantity and unit handling
- Discounts and receipt metadata
- Best-before and purchase-date support
- Docker deployment
- Light/dark mode
- Extensible parser architecture

## Architecture

The application follows this flow:

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
Grocy import
```

The core application does not contain retailer-specific receipt parsing.

Each retailer is implemented as a parser plugin with two responsibilities:

```python
matches(text) -> bool
parse(text) -> dict
```

The parser identifies receipts belonging to its retailer and translates the receipt into the common structure used by the core application.

See [`docs/architecture.md`](docs/architecture.md) for more information.

## Currently supported retailers

### ICA

ICA receipt parsing is currently supported through:

```text
plugins/ica.py
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
git clone https://github.com/YOUR-USERNAME/grocy-receipt-importer.git
cd grocy-receipt-importer
```

Create the local environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```text
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

Never commit `.env` to GitHub.

The repository contains `.env.example` as a template.

## Data

Application data is stored in:

```text
data/
```

The SQLite database is:

```text
data/receipts.sqlite3
```

The `data/` directory is intentionally excluded from Git.

This keeps local receipt history and mappings out of the public repository.

## Plugins

Retailer parsers live in:

```text
plugins/
```

For example:

```text
plugins/
├── __init__.py
├── base.py
├── discovery.py
└── ica.py
```

To add a new retailer, create another plugin:

```text
plugins/coop.py
```

The application automatically discovers parser classes that inherit from `ReceiptParser`.

No changes to `app.py` or a central parser registry are required.

See [`docs/plugin-development.md`](docs/plugin-development.md) for the complete plugin development guide.

## Example parser

A minimal parser looks like this:

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

Real parsers will need retailer-specific logic to extract products, quantities, prices, article numbers, and other useful fields.

## Development

Create a Python virtual environment if you want to run the application directly:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The application can then be started with:

```bash
uvicorn app:app --reload
```

For normal deployment, Docker Compose is recommended.

## Testing

Parser tests should be added under:

```text
tests/plugins/
```

Tests should cover:

- correct retailer recognition
- rejection of unrelated receipts
- product parsing
- quantities
- units
- prices
- discounts
- unusual or missing fields

Receipt fixtures must be sanitized before being committed.

Do not commit real receipts containing personal, payment, customer, or other sensitive information.

## Contributing

Contributions are welcome, especially new retailer parsers.

A typical new retailer contribution should contain:

1. A new parser in `plugins/`.
2. Parser tests.
3. Sanitized receipt fixtures where useful.
4. Documentation for retailer-specific assumptions.

Please keep retailer-specific logic inside the plugin rather than modifying the core application.

See [`docs/plugin-development.md`](docs/plugin-development.md) before creating a new parser.

## Security

Do not commit:

- `.env`
- Grocy API keys
- real receipt PDFs containing personal information
- customer or loyalty identifiers
- payment information
- private database files

If you discover a security issue, please report it privately rather than opening a public issue with sensitive details.

## License

This project is licensed under the MIT License.

See [`LICENSE`](LICENSE).
