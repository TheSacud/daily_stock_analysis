# Analysis Context Pack

The analysis context pack captures structured evidence used by stock analysis, market review, diagnostics, and downstream report rendering.

## Purpose

The context pack gives the LLM and report pipeline a stable snapshot of inputs instead of forcing every component to infer from raw text. It should include market state, price data, indicators, news/intelligence summaries, decision context, diagnostics, and data-quality notes.

## Core Sections

- `stock`: symbol, market, normalized display metadata.
- `market_phase_summary`: current phase, confidence, and partial-bar status.
- `daily_market_context`: broader market and trading-calendar context.
- `price_context`: current quote, history-derived indicators, support/resistance, and freshness.
- `intelligence`: news, announcements, catalysts, risks, and source diagnostics.
- `decision_context`: strategy, watch conditions, entry/exit plan, and confidence.
- `data_quality`: missing fields, stale providers, fallback use, and uncertainty.

## Contract Rules

- Prefer structured fields over free-form report text.
- Preserve original provider diagnostics instead of hiding fallback behavior.
- Do not invent missing stop-loss, target, or confidence fields.
- Keep compatibility with saved history snapshots.
- New fields should be additive unless a migration is explicitly planned.

## Validation

When changing the context pack, update tests, report rendering, and documentation together. Verify extraction, report persistence, dashboard rendering, and diagnostics behavior.