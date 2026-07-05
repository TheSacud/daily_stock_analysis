# Feishu Bot Configuration

This page describes the Feishu bot setup used by Daily Stock Analysis.

## Modes

Feishu can be used through webhook-style delivery or stream/event style integrations depending on the configured adapter.

## Setup Checklist

1. Create or select a Feishu application.
2. Add bot capability to the application.
3. Configure the app credentials and callback/event settings required by the selected mode.
4. Add the bot to the target group or conversation.
5. Add the required variables to `.env` or the deployment secret manager.
6. Test commands before enabling scheduled notifications.

## Configuration

Common values include `FEISHU_WEBHOOK_URL`, `FEISHU_WEBHOOK_SECRET`, `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, and stream-mode switches. Only configure values needed by the selected integration mode.

## Troubleshooting

- Verify the bot is installed in the target chat.
- Confirm callback URLs are reachable when using HTTP callbacks.
- Confirm credentials are stored as secrets and not committed.