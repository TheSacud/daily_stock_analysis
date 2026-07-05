# Run Diagnostics P3

P3 diagnostics cover extended, low-priority, or exploratory checks.

## Scope

- Long-running provider smoke tests.
- Network-only verification.
- Optional feature probes.
- Historical data completeness checks.

## Guidance

P3 diagnostics should not block normal local development unless a task specifically depends on the checked feature. Mark network-dependent checks clearly.