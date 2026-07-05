# Discord Bot Configuration

This guide summarizes Discord bot setup for report and command delivery.

## Setup Checklist

1. Create a Discord application in the Discord developer portal.
2. Add a bot user and copy the bot token into the deployment secret manager.
3. Enable the gateway intents required by the selected command mode.
4. Invite the bot to the target server with the required permissions.
5. Configure channel IDs or webhook URLs as required by the adapter.
6. Run a command smoke test before enabling scheduled delivery.

## Security

Do not commit bot tokens, webhook URLs, guild IDs tied to private deployments, or private channel identifiers.

## Troubleshooting

- If messages are not delivered, verify bot permissions in the target channel.
- If commands do not respond, verify gateway intents and command registration.
- If rate limits occur, reduce delivery frequency or use batching.