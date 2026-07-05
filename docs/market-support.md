# Market Support

Daily Stock Analysis supports multiple equity markets through market-specific normalization, data-provider routing, trading calendars, and report behavior.

## Supported Market Families

- Mainland China A-shares and ETFs.
- Hong Kong stocks.
- US stocks and ETFs.
- Taiwan stocks.
- Japan stocks.
- Korea stocks.

Actual data coverage depends on configured providers, tokens, and fallback availability.

## Market-Specific Notes

- A-shares may require Chinese market data providers and local trading calendars.
- Hong Kong and US symbols use offshore-style routing and provider fallbacks.
- Taiwan reports can include institutional flow fields when provider data is available.
- Japan and Korea support depends on symbol normalization and provider coverage.

## Compatibility

Stock-name indexes and seed files may keep native market names and aliases so lookup, autocomplete, and historical fixtures remain accurate. UI and documentation should still be English-first.