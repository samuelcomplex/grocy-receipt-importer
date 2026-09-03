# Changelog

All notable changes to Grocy Receipt Importer are documented here.

The project follows [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-09-04

### Added

- English and Swedish UI translations.
- Persistent language selection with `EN` / `SV`.
- Light and dark mode controls.
- Localized PDF file selection.
- Receipt deletion with confirmation.
- Open and delete actions in Recent receipts.
- Hover tooltips for receipt actions.
- Import button showing the number of selected items.
- Application version tracking through the `VERSION` file.

### Changed

- Improved the receipt review and import workflow.
- Renamed the primary import action to **Import items**.
- The import button is disabled when no items are selected.
- Already-imported items are disabled and cannot be imported again.
- Already-imported items are no longer counted as newly imported.
- Improved the Recent receipts layout.
- Improved receipt status presentation.
- Added translation loading from the `translations/` directory.
- Updated the Docker image to include translation files.
- Standardized the application name as **Grocy Receipt Importer**.

### Fixed

- Prevented previously imported items from being imported again when a receipt is submitted a second time.
- Replaced browser-native file input text with a localized file-selection interface.

### Important note

Deleting a receipt removes it from the importer database only.

It does **not** remove stock or transactions that have already been imported into Grocy.

## [0.1.0]

Initial release.

- PDF receipt importing.
- Retailer-specific parser plugins.
- Receipt review before import.
- Grocy product matching.
- Saved article-number mappings.
- Grocy stock importing.
- Receipt history.
- Docker deployment.
