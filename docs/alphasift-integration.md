# AlphaSift Integration

AlphaSift is integrated as an external screening engine through a stable DSA adapter. DSA does not copy AlphaSift strategy logic into this repository; it calls the adapter and enriches results with DSA provider context where needed.

## Current Design

- Default state: `ALPHASIFT_ENABLED=false`.
- Enable through the Web settings page, the screening page, or `.env`.
- Runtime dependency is pinned in `requirements.txt` and validated by `ALPHASIFT_INSTALL_SPEC` allow-list behavior.
- Missing adapter dependency should return unavailable diagnostics instead of attempting runtime installation during business requests.

## Responsibilities

AlphaSift owns screening strategy execution, factor scoring, market snapshots, candidate ranking, and adapter contracts. DSA owns configuration, API shell, provider enrichment, display, diagnostics, and notification/report integration.

## Data And LLM Context

DSA may inject model settings, provider priority, isolated cache paths, quote context, and news enrichment into AlphaSift calls. Fallbacks should keep screening resilient when an upstream source times out or returns stale data.

## Rollback

- Fast business rollback: set `ALPHASIFT_ENABLED=false` and restart.
- Adapter rollback: revert the dependency pin, allow-list constant, and `.env.example` sample together, then rebuild backend or desktop artifacts.

## Review Checklist

- Confirm adapter version and allow-list are consistent.
- Confirm Web/API diagnostics explain missing dependency versus runtime adapter failure.
- Confirm cache paths do not leak into packaged or committed artifacts.
- Confirm screening failures do not break unrelated analysis flows.