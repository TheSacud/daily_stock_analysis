# Notifications

Daily Stock Analysis can send reports, alerts, and system messages through multiple notification channels.

## Channels

Supported channels include email, WeCom/WeChat webhook, Feishu, DingTalk, Telegram, Discord, Slack, ServerChan, PushPlus, Pushover, Gotify, ntfy, custom webhooks, and related adapters.

## Routing

Notification routing is controlled by configuration values such as:

- `NOTIFICATION_REPORT_CHANNELS`
- `NOTIFICATION_ALERT_CHANNELS`
- `NOTIFICATION_SYSTEM_ERROR_CHANNELS`

Leave a routing value empty to use all configured channels. Use comma-separated channel names to target specific channels.

## Noise Control

Static notifications can use deduplication, cooldown, severity filters, and quiet hours. Dynamic alerts have their own trigger and cooldown logic.

## Failure Handling

A failed notification channel should not stop the full analysis workflow. Record the attempt, error code, elapsed time, and diagnostics so operators can fix the channel without losing the analysis result.

## Validation

Use the settings page test panel or channel-specific tests to verify credentials before enabling scheduled delivery.