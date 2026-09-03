# Contributing

Thanks for contributing to Grocy Receipt Importer.

The project is especially interested in new retailer parsers, parser improvements, bug fixes, and usability improvements.

## Adding a retailer

Retailer-specific receipt parsing belongs in a plugin under:

```text
plugins/
```

Create a new parser by inheriting from `ReceiptParser`.

See [docs/plugin-development.md](docs/plugin-development.md) for the plugin interface, discovery process, testing guidance, and privacy requirements.

## Keep retailer logic in plugins

Plugins should handle:

- retailer recognition
- receipt parsing
- normalization into the common receipt structure

Plugins should not handle:

- Grocy API communication
- database access
- product mappings
- stock imports
- web routes
- templates
- translations

Changes that affect the core application should be made only when they are genuinely required.

## Tests

New parser functionality should include tests.

Test at least:

- retailer recognition
- rejection of unrelated receipts
- product parsing
- article numbers
- quantities and units
- prices and discounts
- missing or unusual fields

Run the test suite before submitting a pull request.

## Receipt fixtures

Receipt fixtures are useful for parser development, but never commit unredacted real receipts.

Remove or anonymize personal and sensitive information, including:

- names
- addresses
- payment information
- loyalty/customer identifiers
- unnecessary transaction identifiers

## Internationalization

User-facing text should use the translation system.

Translations are stored in:

```text
translations/
├── en.json
└── sv.json
```

When adding a new user-facing string:

1. Add the key to `translations/en.json`.
2. Add the corresponding Swedish translation to `translations/sv.json`.
3. Use the translation helper in templates.
4. Keep the application name as `Grocy Receipt Importer`.

## Pull requests

Please include:

- a clear description of the change
- tests for new parser functionality
- sanitized receipt fixtures where useful
- documentation updates when behavior or interfaces change

For new retailers, describe which receipt formats were tested and any known limitations.

## Security

Never commit:

- `.env`
- Grocy API keys
- private database files
- real receipts containing personal information
- payment information or customer identifiers

If you discover a security issue, report it privately rather than publishing sensitive details in a public issue.

## Versioning

The current application version is stored in:

```text
VERSION
```

The project follows Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Release notes are maintained in:

```text
CHANGELOG.md
```

Git release tags use the format:

```text
v0.2.0
```

When preparing a release:

1. Update `VERSION`.
2. Update `CHANGELOG.md`.
3. Run tests and validation.
4. Review the complete Git diff.
5. Commit the release.
6. Create the matching Git tag.
7. Push the commit and tag.
