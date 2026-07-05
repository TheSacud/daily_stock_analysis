# Data Source Stability And Fallbacks

Daily Stock Analysis uses multiple market-data providers and should continue when a single provider fails. The expected behavior is fail-open for optional enrichment and fail-fast only when the requested core data cannot be produced.

## Provider Principles

- Keep provider priority explicit in configuration.
- Normalize fields at provider boundaries.
- Apply timeouts and retries close to the external call.
- Record diagnostics when a provider fails or returns stale data.
- Fall back to the next provider instead of aborting the whole analysis when possible.

## Common Fallback Chain

Daily price and quote data can use providers such as Tushare, Efinance, AkShare, Pytdx, Baostock, Yfinance, Longbridge, and market-specific adapters. The actual order depends on market, token availability, and runtime configuration.

## Diagnostics

Provider failures should expose:

- provider name
- failure reason
- timeout or exception class
- stale-data status when relevant
- whether fallback data was used

## Operational Guidance

If a provider becomes unstable, lower its priority or disable it in configuration, then run the deterministic checks before restoring normal scheduling. Avoid adding silent `None` or empty-list fallbacks that hide real contract failures.