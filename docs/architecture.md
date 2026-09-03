# Architecture

## Overview

Grocy Receipt Importer is designed around a simple separation of responsibilities:

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
Receipt parser
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

The important architectural rule is:

> Retailer-specific knowledge belongs in plugins, not in the core application.

This allows new retailers to be added without modifying the core importer.

## Core application

The core application is responsible for application-level behavior:

- accepting uploaded receipt PDFs
- extracting text from PDFs
- discovering receipt parser plugins
- selecting the parser that recognizes the receipt
- applying saved product mappings
- displaying the review interface
- storing receipt information
- communicating with Grocy
- importing stock
- handling dates, units, quantities, and stock transactions

The core should not need to know how a particular retailer formats its receipts.

## Parser plugins

Each retailer has its own parser plugin.

For example:

```text
plugins/
├── base.py
├── discovery.py
├── ica.py
└── coop.py
```

A plugin has two main responsibilities:

### 1. Recognition

The plugin implements:

```python
matches(text) -> bool
```

This determines whether the plugin owns the receipt.

Recognition logic is retailer-specific and therefore belongs inside the plugin.

### 2. Parsing

The plugin implements:

```python
parse(text) -> dict
```

The parser translates retailer-specific receipt text into the common receipt structure used by the core application.

The parser does not import anything into Grocy.

## Common receipt structure

The parser returns a dictionary containing:

```python
{
    "metadata": {...},
    "items": [...]
}
```

The exact fields may evolve as additional retailers are supported.

The goal is to keep the common structure focused on information required by the importer rather than reproducing every retailer's receipt format.

## Plugin discovery

Plugins are discovered automatically.

The discovery system scans the `plugins/` directory for Python modules.

It ignores the framework modules:

- `__init__.py`
- `base.py`
- `discovery.py`

Classes that inherit from `ReceiptParser` are instantiated automatically.

Therefore, adding a retailer normally requires only:

```text
plugins/new_retailer.py
```

No central registry needs to be edited.

No change to `app.py` should be necessary.

## Why this architecture?

Receipt formats are retailer-specific and can change independently.

Putting retailer logic in the core would eventually lead to code such as:

```python
if retailer == "ICA":
    ...
elif retailer == "Coop":
    ...
elif retailer == "Willys":
    ...
```

That approach becomes difficult to maintain as more retailers are added.

The plugin architecture instead keeps each format isolated:

```text
ICA receipt ──► ICAParser
Coop receipt ─► CoopParser
Willys receipt ► WillysParser
```

The core only sees the common result.

## Responsibility boundaries

### Core

The core may:

- work with PDFs
- work with the database
- communicate with Grocy
- manage review state
- manage product mappings
- import stock

### Plugins

Plugins may:

- inspect receipt text
- identify their retailer
- parse retailer-specific fields
- normalize retailer-specific values

### Plugins should not

Plugins should not:

- access the Grocy API
- access the application database
- create Grocy products
- import stock
- save product mappings
- contain web routes
- modify templates

Keeping this boundary makes plugins reusable and independently testable.

## Adding new common fields

Sometimes a new retailer may expose useful information that is not represented by the current common receipt structure.

Do not immediately add retailer-specific fields to the shared interface.

First consider whether the information is genuinely useful to the importer and whether it applies to multiple retailers.

If a change to the common structure is necessary, it should be discussed as an architectural change rather than implemented as a workaround inside one retailer plugin.

## Runtime plugin loading

Plugins are mounted into the Docker container:

```yaml
volumes:
  - ./plugins:/app/plugins:ro
```

This means a new plugin can be added without rebuilding the Docker image.

The plugin discovery code loads available parser modules dynamically.

After adding a plugin, restart the container if necessary and verify that the parser is discovered correctly.

## Data flow

A typical import works as follows:

1. The user uploads a receipt PDF.
2. The core extracts text from the PDF.
3. The core asks discovered plugins whether they recognize the receipt.
4. The first matching plugin parses the receipt.
5. The core applies previously saved product mappings.
6. The user reviews the parsed items.
7. The user selects or confirms Grocy products.
8. The core imports the selected items into Grocy.
9. The receipt remains represented in the application's local data as appropriate.

The parser is never responsible for steps 5–9.

## Design goal

The long-term goal is that contributors can add support for a retailer without needing to understand the entire application.

Ideally, adding support for a new retailer means:

1. Create a parser plugin.
2. Add sanitized receipt fixtures.
3. Add parser tests.
4. Submit a pull request.

The core application should remain unchanged.
