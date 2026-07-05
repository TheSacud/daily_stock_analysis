# Tushare Stock List Guide

This guide describes how to use Tushare as one stock-list and market-data source.

## Requirements

- A valid `TUSHARE_TOKEN`.
- Network access from the runtime environment to Tushare.
- Provider priority configured so Tushare is used where appropriate.

## Stock List Refresh

Use the stock-index refresh scripts when you need to update local autocomplete or market lookup data. Generated index files may include native market names and aliases for compatibility.

## Troubleshooting

- If the token is missing or invalid, Tushare-specific calls should fail with diagnostics and allow other providers to run when possible.
- If rate limits occur, reduce refresh frequency or use cached stock-index data.
- Do not commit private tokens or generated runtime cache files.