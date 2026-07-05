# Deploying The Web UI To Cloud Hosts

This page summarizes the cloud deployment path for the Web UI and FastAPI backend.

## Build Inputs

- Backend entrypoint: `server.py` or `python main.py --serve-only`.
- Web app: `apps/dsa-web`.
- Runtime configuration: `.env` or platform environment variables.
- Required secrets: model provider keys and optional data-provider tokens.

## Recommended Flow

1. Install backend dependencies from `requirements.txt`.
2. Build the Web app with `cd apps/dsa-web && npm ci && npm run build`.
3. Start the backend with a production ASGI server or `python main.py --serve-only` for simple deployments.
4. Configure reverse proxy routing to the backend port.
5. Store `.env` values in the platform secret manager rather than in the repository.

## Health Checks

Use the backend health endpoint and the Web app route smoke checks after deployment. If authentication is enabled, verify login and session persistence.

## Rollback

Rollback by redeploying the prior image or commit, restoring the previous environment-variable set, and restarting the backend. Do not roll back by editing generated runtime files in place.