# Daily Stock Analysis Architecture Baseline

Last reviewed: 2026-07-06

This baseline describes the versioned architecture visible in this repository.
It is intended to reduce repeated code exploration before future changes.

## Review Scope

- Source of truth: checked workspace files in this repository.
- Codebase-memory note: the requested project
  `home-hermes-workspaces-daily-stock-analysis` was not indexed during this
  review, so source-file verification was used after the MCP status check.
- Restricted runtime state was not inspected: no `.env`, `data/`, database,
  log, credential, token, or deployment-private files were read.
- No ADR was added because this review found existing implementation contracts,
  not a new architecture decision.

## System Overview

Daily Stock Analysis is a Python backend with multiple user entry points:
CLI/scheduler, FastAPI, bot webhooks, a React Web UI, and an Electron desktop
wrapper. The main business flow is shared by these entry points:

```text
watchlist/request
  -> stock code normalization and trading-day filtering
  -> data providers and cached history
  -> technical, market, news, sentiment, and context enrichment
  -> LLM or local generation backend
  -> normalized report/result schema
  -> SQLite history, decision signals, reports, notifications, API responses
```

The shared analysis coordinator is `src/core/pipeline.py`. API and bot paths
should call service layers that eventually delegate to this pipeline instead of
implementing separate analysis behavior.

## Runtime Entry Points

| Surface | Files | Role |
| --- | --- | --- |
| CLI | `main.py` | Parses command-line options, loads config, runs one-off analysis, market review, backtest, scheduled mode, or API serving mode. |
| FastAPI | `server.py`, `api/app.py`, `api/v1/router.py` | Creates the API app, registers middleware and `/api/v1` routers, serves static Web UI assets when built, manages runtime scheduler lifecycle. |
| Web UI | `apps/dsa-web/` | Vite/React SPA for analysis, chat, portfolio, alerts, decision signals, backtest, usage, history, and settings. Uses `/api/v1/*`. |
| Desktop | `apps/dsa-desktop/` | Electron shell that starts the backend locally with `main.py --serve-only`, opens the Web UI, and manages desktop packaging/update state. |
| Bot webhooks | `bot/handler.py`, `bot/dispatcher.py`, `bot/commands/` | Parses platform webhooks, dispatches commands, and sends immediate or deferred responses. |
| GitHub Actions | `.github/workflows/00-daily-analysis.yml` | Scheduled/manual cloud runner for daily analysis using repository variables/secrets. |
| Docker | `docker/Dockerfile`, `docker/docker-compose.yml`, `docker/entrypoint.sh` | Builds Web assets into the Python image, runs as non-root `dsa`, and persists runtime data through mounts. |

Common command entry points:

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## Backend Architecture

### CLI And Scheduler

- `main.py` loads environment/config, resolves CLI flags, applies trading-day
  filtering, initializes logging, and calls `run_full_analysis()`.
- `run_full_analysis()` builds a `StockAnalysisPipeline`, runs stock analysis,
  optionally runs market review, optionally merges notification output, and
  optionally runs automatic backtest.
- `src/scheduler.py` wraps the `schedule` package for foreground scheduled
  runs with graceful shutdown.
- `src/services/runtime_scheduler.py` provides scheduler ownership for
  long-lived API/Web/Desktop processes. It uses an in-process global analysis
  lock and reconciles runtime schedule settings from config.

### Core Analysis Pipeline

- `src/core/pipeline.py` owns single-stock and multi-stock analysis orchestration.
- Pipeline collaborators include:
  - `data_provider.DataFetcherManager` for market data and fallback.
  - `src.stock_analyzer.StockTrendAnalyzer` for technical indicators.
  - `src.analyzer.GeminiAnalyzer` for report generation and result normalization.
  - `src.search_service.SearchService` for news/search enrichment.
  - `src.services.daily_market_context.DailyMarketContextService` for reusable
    market context.
  - `src.notification.NotificationService` for report files and push delivery.
  - `src.storage.DatabaseManager` for persisted history and related entities.
- Pipeline outputs are persisted through `save_analysis_history()`, decision
  signal extraction, diagnostics snapshots, and optional report/notification
  rendering.
- Multi-stock runs use a `ThreadPoolExecutor`; single-stock API/bot paths usually
  constrain concurrency at the caller.

### Market Review

- `src/core/market_review.py` generates region-level reviews for configured
  markets: `cn`, `hk`, `us`, `jp`, `kr`, or multi-region forms.
- `main.py` wraps market review with `src/core/market_review_lock.py` to avoid
  duplicate review execution.
- Market review can save Markdown, persist history, send notifications, and
  return a structured payload for API/Web consumers.

### Data Providers

- `data_provider/base.py` defines `BaseFetcher`, stock-code normalization, market
  classification, standard OHLC columns, provider diagnostics, retries, and
  fallback behavior.
- `DataFetcherManager` coordinates providers such as efinance, AkShare, Tushare,
  Pytdx, Baostock, YFinance, Longbridge, Tencent, Finnhub, Alpha Vantage, and
  TickFlow-related fetchers.
- Provider failures should degrade to another source where possible. Changes in
  this area must preserve fallback order, code normalization, timeout behavior,
  cache behavior, and provider diagnostics.

### LLM And Agent Layer

- `src/llm/` abstracts generation backends. `backend_registry.py` defines
  supported backend identifiers; `backend_factory.py` constructs LiteLLM or
  local CLI generation backends.
- `src/analyzer.py` contains the stock report generation path and result
  normalization used by the pipeline.
- `src/agent/` provides chat/research agent behavior, tool execution, streaming
  events, provider trace capture, conversation state, skills, and strategy
  routing.
- Agent API routes live under `api/v1/endpoints/agent.py`; Web consumers live
  under `apps/dsa-web/src/api/agent.ts` and chat-related stores/pages.

### API Layer

- `api/app.py` creates the FastAPI app, CORS config, auth middleware, error
  handlers, static SPA serving, health endpoints, stock-index serving, and
  runtime scheduler lifecycle.
- `api/v1/router.py` mounts routers for auth, agent, analysis, history, stocks,
  backtest, system config, usage, portfolio, alerts, decision signals, AlphaSift,
  intelligence, and health.
- API handlers should stay thin. Business behavior belongs in `src/services/`,
  `src/repositories/`, `src/core/`, or `data_provider/`.
- API schemas live under `api/v1/schemas/`; backend domain schemas live under
  `src/schemas/`.
- `docs/architecture/api_spec.json` is the checked-in API spec artifact. Its
  generation and freshness process is an open follow-up below.

### Service And Repository Boundaries

- `src/services/` contains business services used by API, pipeline, bot, and
  runtime scheduler paths: analysis, task queue, portfolio, alerts, decision
  signals, intelligence, backtest, system config, history, diagnostics, report
  rendering, import parsing, stock index refresh, and related helpers.
- `src/repositories/` owns persistence access for analysis history, stocks,
  portfolio, alerts, intelligence, backtest, and decision-signal domains.
- New persistence behavior should go through repositories or `DatabaseManager`
  helpers instead of opening ad hoc SQLite connections.

### Notification And Reports

- `src/notification.py` composes report output and dispatches through sender
  mixins in `src/notification_sender/`.
- Supported notification implementations include WeCom, DingTalk, Feishu,
  Telegram, email, Pushover, ntfy, Gotify, PushPlus, ServerChan3, custom
  webhooks, Discord, Slack, and AstrBot.
- Markdown/Jinja report templates live in `templates/`; report schemas and
  rendering helpers live under `src/schemas/` and `src/services/report_renderer.py`.
- Notification failures should not take down the main analysis path unless a
  specific caller explicitly requires fail-fast behavior.

### Auth And Configuration

- `src/config.py` loads `.env`/process environment, validates settings, and
  produces the process-wide `Config` object.
- `src/services/system_config_service.py` supports Web/API settings reads,
  validation, imports/exports, channel testing, and runtime config updates.
- `src/auth.py` implements optional admin auth controlled by configuration,
  file-backed credential/session state under the data directory, signed cookies,
  rate limiting, password setup/change, and session rotation.
- `api/middlewares/auth.py` protects `/api/v1/*` when admin auth is enabled,
  exempting login/status/health/docs routes.

## Frontend Architecture

### Web App

- `apps/dsa-web/src/App.tsx` defines the route shell and auth-gated pages:
  home, chat, portfolio, decision signals, stock screening, backtest, alerts,
  usage, settings, login, and not-found.
- API clients live under `apps/dsa-web/src/api/`, use Axios with credentials,
  and target `API_BASE_URL` from `apps/dsa-web/src/utils/constants.ts`.
- UI state is split across contexts (`AuthContext`, `UiLanguageContext`) and
  Zustand stores under `apps/dsa-web/src/stores/`.
- Page/component tests live beside the Web source under `apps/dsa-web/tests/`
  and `apps/dsa-web/src/**/__tests__`.

### Desktop App

- `apps/dsa-desktop/main.js` launches either a packaged backend executable or
  development Python backend, selects a local port, waits for `/api/health`, and
  opens the Web UI in Electron.
- Runtime user data, configuration, database, logs, and update backup state are
  deployment-private. Do not commit desktop runtime output.
- Desktop packaging depends on Web build artifacts and backend build artifacts;
  see `docs/desktop-package.md` and `scripts/build-*`.

## Data And State Boundaries

| State | Default/location | Ownership |
| --- | --- | --- |
| Configuration | `.env` or process environment | Runtime-only; do not commit real values. `.env.example` documents placeholders. |
| SQLite DB | `DATABASE_PATH`, default `./data/stock_analysis.db` | Runtime data; stores stock daily rows, analysis history, news/intelligence, portfolio, alerts, decision signals, backtest, conversations, and usage telemetry. |
| Logs | `LOG_DIR`, default `./logs` | Runtime diagnostics; do not commit. |
| Reports | `./reports` by deployment convention | Generated output; do not commit unless deliberately adding stable fixtures/docs. |
| Web build | `static/` in backend runtime, built from `apps/dsa-web/` | Build artifact used by FastAPI and desktop packaging. |
| Stock autocomplete index | Remote cache or bundled `stocks.index.json` | Served by FastAPI with best-effort background refresh. |
| Auth state | Private files under the database directory | Runtime credential/session material; do not inspect or commit. |
| Third-party token caches | Deployment-private cache/mount paths | Runtime-only OAuth/API state; do not inspect or commit. |

`src/storage.py` uses SQLAlchemy, creates tables on startup, records schema
migration state, enables SQLite WAL/busy-timeout behavior when configured, and
serializes writes with retry helpers for SQLite lock conflicts.

## Deployment Boundaries

- Docker deployment builds the Web UI in a Node stage, copies backend code into
  a Python 3.11 runtime image, prepares writable `data`, `logs`, and `reports`
  directories, then runs as a non-root user.
- Docker Compose defines separate analyzer and server modes. Runtime mounts are
  deployment state, not source-controlled application code.
- Direct/systemd deployment is documented in `docs/DEPLOY.md`; local server mode
  can run through `python main.py --serve-only` or `uvicorn server:app`.
- GitHub Actions daily analysis runs from `.github/workflows/00-daily-analysis.yml`
  and injects configuration through repository variables/secrets.
- Release/build workflows live under `.github/workflows/`, including CI, Docker
  publishing, auto-tagging, release creation, desktop release, network smoke,
  and PR review helpers.
- Sacud-specific deployment changes should stay on the `sacud/vps` branch and
  avoid committing private VPS paths or runtime state.

## Installation And Validation Commands

Backend:

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
```

Web:

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

Desktop:

```bash
cd apps/dsa-web && npm ci && npm run build
cd ../dsa-desktop && npm install && npm run build
```

Documentation-only changes usually do not require the full backend/Web suite.
At minimum, verify referenced files and commands and run whitespace checks such
as:

```bash
git diff --check
```

## Change Risk Map

High-risk surfaces:

- Config loading and Web settings persistence (`src/config.py`,
  `src/services/system_config_service.py`).
- API/schema/auth compatibility (`api/**`, `src/schemas/**`,
  `apps/dsa-web/src/api/**`, desktop startup).
- Data-provider fallback, stock-code normalization, and market classification
  (`data_provider/**`, `src/services/market_symbol_utils.py`).
- Report format, prompt contracts, decision signal extraction, and notification
  payloads (`src/analyzer.py`, `src/core/pipeline.py`, `src/services/*signal*`,
  `src/notification.py`, `templates/`).
- Scheduling and duplicate-run protection (`main.py`, `src/scheduler.py`,
  `src/services/runtime_scheduler.py`, `src/core/market_review_lock.py`).
- Desktop packaging and backend startup (`apps/dsa-desktop/`, `scripts/build-*`,
  release workflows).
- SQLite write concurrency and schema evolution (`src/storage.py`,
  `src/repositories/**`).

Lower-risk surfaces:

- Pure docs that do not change commands, config keys, runtime paths, or workflow
  semantics.
- Localized UI text where schemas and API behavior are unchanged.
- Tests that only add coverage without changing fixtures consumed by runtime.

## Open Follow-Up Cards

- Index or repair codebase-memory for the Daily Stock Analysis workspace so
  future workers can use graph search and trace paths before file scanning.
- Define and document how `docs/architecture/api_spec.json` is generated and
  checked for freshness.
- Add a deployment overlay note for the Sacud VPS fork if the deployment shape
  differs from the generic Docker/direct/systemd documentation and can be
  documented without private paths or secrets.
- Consider a small architecture smoke test that verifies key imports and route
  mounting without starting external services.
