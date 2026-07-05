# Alerts

Alerts evaluate configured rules against market data, portfolio/account state, watchlists, and system conditions. They can trigger notification delivery without blocking the core analysis workflow.

## Rule Types

Alert rules may cover:

- Price and percentage-change thresholds.
- Daily technical indicators.
- Watchlist symbols.
- Portfolio/account-linked conditions.
- Market-light or broad market conditions.
- System or provider degradation conditions.

## Evaluation Flow

1. Load enabled rules.
2. Resolve the rule scope and required data.
3. Evaluate the condition.
4. Apply deduplication, cooldown, quiet hours, and severity filters.
5. Dispatch notifications through configured channels.
6. Record trigger history and notification attempts.

## Notification Attempts

Each attempt should record channel, success state, error code, elapsed time, and diagnostics. A failed channel should not prevent other channels from receiving the alert.

## Error Codes

Common internal states include cooldown suppression, cooldown-read failure, noise suppression, no available channel, dispatch failure, and context/channel mismatch.

## Configuration

Use settings and environment variables to configure alert routing, notification severity, quiet hours, and channel credentials. Leave route-specific channel lists empty to use all configured channels.

## Validation

When changing alert behavior, verify:

- rule creation and update APIs
- one-time rule testing
- background worker evaluation
- trigger history persistence
- notification-attempt diagnostics
- Web alert page rendering