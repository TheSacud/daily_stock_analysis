# Zeabur Deployment

This guide describes a Docker-based Zeabur deployment for Daily Stock Analysis.

## Required Configuration

Configure environment variables in Zeabur instead of committing a `.env` file. At minimum, configure a model provider and the watchlist:

```env
STOCK_LIST=600519,AAPL,hk00700
LITELLM_MODEL=<provider/model>
```

Add provider keys such as `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, or other channel-specific variables as needed.

## Deployment Steps

1. Connect the GitHub repository to Zeabur.
2. Select the Docker deployment path.
3. Configure environment variables and secrets.
4. Expose the backend port configured by `WEBUI_PORT`.
5. Deploy and verify the health endpoint and Web UI.

## Persistent Data

Mount persistent storage for runtime data if reports, cache, or history must survive redeploys. Do not mount secrets into paths that could be served statically.

## Troubleshooting

- If the backend starts but analysis fails, check provider keys and model names.
- If the Web UI loads but API calls fail, check proxy routing and CORS/origin settings.
- If scheduled tasks do not run, check timezone and scheduler configuration.