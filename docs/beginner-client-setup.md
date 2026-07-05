# Beginner Client Setup

This guide helps a new user connect Daily Stock Analysis to a model provider and run the first analysis.

## Prerequisites

- Python dependencies installed from `requirements.txt`.
- A configured model provider through `.env`, `LITELLM_CONFIG`, or the Web settings page.
- At least one stock code in `STOCK_LIST`.

## Basic Steps

1. Copy `.env.example` to `.env`.
2. Configure one model channel, for example `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, or a LiteLLM-compatible channel.
3. Set `LITELLM_MODEL` to a model that exists in the configured provider.
4. Set `STOCK_LIST` to comma-separated symbols such as `600519,AAPL,hk00700`.
5. Run `python main.py --dry-run` to verify data loading.
6. Run `python main.py --stocks 600519` for a first analysis.

## Web Setup

Start the backend with:

```bash
python main.py --serve-only
```

Then open the Web UI and configure channels under Settings. The Web settings page writes supported values back to `.env` when the backend allows it.

## Troubleshooting

- If `/status` reports that AI service is not configured, verify the model name and API key source.
- If data loading fails, run with `--debug` and check provider fallbacks.
- Do not commit `.env`, API keys, access tokens, or runtime data.