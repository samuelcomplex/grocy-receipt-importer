# Changelog

All notable changes to Grocy Receipt Importer are documented here.

The project follows [Semantic Versioning](https://semver.org/).

## [0.3.5] - 2026-09-17

### Added

- Persistent ignored receipt-item mappings that are reapplied when receipts are reviewed again.
- Expanded parser contract coverage for common receipt metadata and item fields.
- ICA parser coverage using layout-preserved PDF text.

### Changed

- Standardized PDF receipt text extraction on `pypdf` with `extraction_mode="layout"`.
- Adapted ICA receipt parsing to the standardized layout-preserved text representation.
- Standardized the common receipt metadata field for receipt numbers as `receipt_no`.
- Receipt-review errors are kept on the current page where appropriate.

### Fixed

- Ignored receipt items can now be saved and restored through the same alias storage mechanism as product mappings.

## [0.3.4] - 2026-09-11

### Added

- Immediate creation of new Grocy products from the receipt review, with the created product made available to all receipt-line selectors.
- Inline creation of quantity units, storage locations, and product groups while configuring a new product.
- Inline storage-location creation with an option to mark newly-created locations as freezers; existing locations cannot be changed to freezers here.
- Undo for newly-created Grocy products, including confirmation when a product is assigned to multiple receipt lines.
- In-place removal of undone products and affected mappings without reloading the receipt review.
- Parser-agnostic numeric normalization to canonical `Decimal` values for common European and US number formats.

### Changed

- New-product creation is separated from receipt import and no longer requires importing the receipt to create the Grocy product.
- Saved mapping unlinking now completes in place on the receipt review instead of navigating to a separate response page.
- Expanded automated coverage for numeric parsing, new-product creation and undo, multi-line assignments, and mapping actions.

### Fixed

- Prevented stale unlink controls from remaining after undoing a newly-created product.
- Prevented receipt-review undo URLs from duplicating the receipt path.
- Prevented expected multi-line undo confirmation requests from losing the selected receipt-line indexes.
- Kept mapping-action errors on the receipt review page instead of displaying standalone error pages.


## [0.3.3] - 2026-09-08

### Fixed

- Prevented receipt imports without a retailer store organization from failing when saving product mappings and aliases.


## [0.3.2] - 2026-09-08

### Added

- Typed core receipt and receipt-item models.
- Configurable receipt and mapping storage backends.
- Explicit parser contracts and expanded automated test coverage.
- Refactored Grocy integration, product matching, product creation, receipt models, storage, and web application modules.
- Ability to configure and stage new Grocy products directly from the receipt review.
- Grocy location, purchase-unit, and stock-unit selection when creating a new product.
- Product-specific purchase-to-stock quantity conversions for new products.
- Receipt import support for products whose purchase and stock quantity units differ.
- Undo imported Grocy transactions directly from the receipt review.
- Unlink saved article-number mappings from the receipt review.
- English and Swedish translations for review actions and statuses.

### Changed

- Receipt units are treated as retailer metadata and no longer require a Grocy quantity-unit conversion for matching.
- Imported quantities are converted to the selected Grocy product's stock unit using the product-specific Grocy conversion.
- Receipt line prices are treated as total prices for the receipt line and are converted to price per imported stock unit before being sent to Grocy.
- The receipt review now supports configuring unmatched items as new Grocy products before importing.
- Improved receipt review and import error handling.
- Improved JSON response handling and application structure.
- Improved receipt status handling after undo operations.
- Previously imported items retain their protected state and cannot be imported again.
- Updated Docker packaging for the refactored application structure.

### Fixed

- Prevented incorrect receipt totals from being stored as per-stock-unit prices.
- Prevented incorrect stock quantities when purchase and stock units differ.
- Prevented unlink and undo actions from accidentally submitting the main receipt import form.
- Receipt import failures are shown directly on the affected item.

## [0.3.0] - 2026-09-07

### Added

- Typed core receipt models for receipt and receipt-item data.
- Configurable receipt and mapping storage backends.
- Explicit parser contracts and expanded automated test coverage.

### Changed

- Refactored the application into separate modules for the web layer, Grocy integration, product matching, receipt models, and storage.
- Separated parsed receipt data from application state and Grocy mappings.

## [0.2.5] - 2026-09-04

### Added

- Undo imported Grocy transactions directly from the receipt review.
- Unlink saved article-number mappings from the receipt review.
- English and Swedish translations for the new review actions and statuses.

### Changed

- Receipt units are treated as retailer metadata and no longer require Grocy quantity-unit conversions for import.
- The receipt review shows import failures directly on the affected item.
- The import checkbox is disabled when **Skip Product** is selected.
- Unlinking a saved mapping uses a dedicated link icon with a hover tooltip.
- Previously imported items retain their protected state and cannot be imported again.

### Fixed

- Prevented unlink and undo actions from accidentally submitting the main receipt import form.

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
