# Decision Signals

Decision signals turn analysis output into trackable actions, watch conditions, invalidation points, and later outcome evaluation.

## Concepts

- `action`: normalized decision action such as buy, hold, reduce, sell, avoid, or alert.
- `confidence`: conservative report-level confidence used for display and history comparison.
- `watch_conditions`: conditions that should be monitored after the report is generated.
- `entry_low` / `entry_high`: optional price-plan bounds extracted from the report.
- `stop_loss` / `target_price`: optional risk and target levels.
- `metadata`: original report-level details and extraction provenance.

## Extraction Rules

Extraction should prefer structured fields from the analysis context and report dashboard. Free-form parsing is a fallback and must not invent missing prices. Missing stop-loss or target values should lower plan quality rather than fabricating values.

## Compatibility

The service may still accept legacy localized action aliases from old reports, but new documentation, UI, and prompts should use English action labels.

## Review Checklist

- Confirm the action mapping is deterministic.
- Confirm plan quality reflects missing fields.
- Confirm historical comparison does not overwrite original report metadata.
- Confirm outcome evaluation can link back to the stored decision signal.