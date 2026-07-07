# 2026-07-07 Research Synthesis - Daily Stock Analysis 2026W27

## What The Data Says

Measured or re-checked on 2026-07-07 from the task worktree unless noted:

- Local health: `curl -fsS --max-time 5 http://127.0.0.1:8010/health` returned `{"status":"ok","timestamp":"2026-07-07T15:57:09.227662"}`.
- Origin listener exposure: non-sudo `ss -ltn '( sport = :8010 )'` showed `LISTEN 127.0.0.1:8010`, not `0.0.0.0:8010`.
- Docker health: not re-measured. This worker is prohibited from Docker, and broad sudo is prohibited.
- Docker/NAT host exposure: not re-measured. The sanctioned `sudo ss` and `sudo iptables` probes are outside this worker's hard limits.
- Signal file: `signals/docker-public-port-exposure.md` is missing from this worktree; `signals/` does not exist.
- Public edge: attempted `https://stocks.sacud.com/health` through `/home/hermes/Loop/scripts/research_web_fetch.py` on 2026-07-07; the helper rejected the domain as not allowlisted (`stocks.sacud.com`).
- Scheduler freshness: `GET http://127.0.0.1:8010/api/v1/system/scheduler/status` returned `401 Unauthorized`; no auth bypass was attempted.
- Open PR overlap: `gh pr list --repo TheSacud/daily_stock_analysis --state open --json number,title,headRefName,body` returned `[]`, so no open PR already ships the selected next change.

Canonical reconciliation: this repo had no committed `research/dossier/` or `docs/research-brief.md` before this synthesis, so the Loop dossier is the upstream seed. The Loop seed still says the app stage includes public Docker port exposure, but current source and allowed live checks show the loopback bind has shipped. This living dossier treats the rebind item as completed and avoids recommending it again.

## Prior Recommendation Retro

Previous top pick from the Loop seed: rebind the daily-stock-analysis Docker port to `127.0.0.1`.

Status:

- Shipped in repo history. `git log --oneline -20` includes `f3ed054 Bind Docker app port to loopback` and `2bd49f9 fix: restore Docker loopback port and Python 3.11 syntax`; current `docker/docker-compose.yml` maps `127.0.0.1:${API_PORT:-8010}:${API_PORT:-8010}` for `stock-server`.
- PR history supports the surrounding guardrail work. Merged PR #3 added security/rollback guardrails and cited the loopback Compose binding; merged PR #4 added the architecture baseline.
- Target metric moved by allowed evidence: current listener evidence shows `127.0.0.1:8010` only. Direct external TCP was not re-measured in this worker because the allowed public web helper cannot perform TCP probes and the task prohibits bypassing with arbitrary network scripts.

Result: do not re-select the Docker rebind. Keep it in the roadmap as completed, with an external TCP measurement gap for this cycle.

## Lens Summaries

### Ingress Security

Finding: the application port is currently loopback-bound by source and by non-sudo listener evidence, but the documentation still contains public-style examples (`8000:8000` and `-p 8000:8000`). This creates regression risk if operators follow older docs instead of the current Compose path.

Key parent candidates folded in:

- Sync deployment docs and FAQ to loopback-only host bindings.
- Add a static ingress guard that rejects public `stock-server` mappings in Compose/docs examples.
- Add a public-edge smoke once `stocks.sacud.com` is allowlisted for the Loop fetch helper.

### Analysis Freshness

Finding: the app has persisted history timestamps and in-memory scheduler timestamps, but there is no safe unauthenticated aggregate that proves latest scheduled analysis, latest saved history, latest market review, or report freshness without reading private DB/report data. The authenticated scheduler status endpoint correctly returned `401` to this worker.

Key parent candidates folded in:

- Add a safe aggregate freshness endpoint/service that returns non-sensitive freshness fields and stale/ok classification.
- Persist scheduler run status or heartbeat outside process memory.
- Add freshness guardrails/alerts and tests after the safe data source exists.

### Runtime Resilience

Finding: FastAPI health is green, but Docker health is not trustworthy from source. `docker/Dockerfile` hardcodes healthcheck probes to port `8000` and then falls through to `python -c "import sys; sys.exit(0)"`, while the Compose `stock-server` command runs on `${API_PORT:-8010}`. Docker can therefore report healthy even when FastAPI health is failing.

Key parent candidates folded in:

- Align Docker healthchecks with the runtime port and remove the always-success fallback.
- Add a secret-safe aggregate runtime diagnostics endpoint or CLI for mounted writable dirs/log readiness.
- Document data/log/report/token-cache retention and cleanup boundaries.

## Conflict Resolution

- Loop seed vs current evidence: the seed's public-exposure stage is stale after the loopback bind landed. The rebind item is marked completed.
- Docker health seed vs runtime lens: the seed says `stock-server` is healthy, but source shows the Docker healthcheck can succeed without probing the running API. This synthesis treats Docker health as untrusted until the healthcheck fails closed.
- Public edge smoke appears in both ingress and runtime lenses. It remains blocked on Loop capacity allowlisting for `stocks.sacud.com`, so it is not selected this cycle.
- Freshness cannot be live-proven today. That is the problem statement for the freshness endpoint, not evidence that the scheduler is stale.

## Merged Scored Roadmap

Scoring uses `impact x confidence / sqrt(effort)` against the north-star. Items that only move a metric when bundled are scored as the milestone bundle.

| Score | Status | Milestone | Primary lens | Target metric | I | C | E | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25.0 | Selected | Fix Docker healthcheck port alignment and fail-closed behavior | Runtime resilience | Docker health agreement | 5 | 5 | 1 | Low-effort source fix turns Docker health from a no-op into a real FastAPI probe, directly protecting the health metric. |
| 14.4 | Ready | Add a safe aggregate freshness endpoint/service with regression tests | Analysis freshness | Analysis freshness observability | 5 | 5 | 3 | Enables Loop and operators to verify latest history/report/scheduler freshness without private data reads. |
| 10.0 | Ready | Sync deployment docs/FAQ to loopback-only app-port examples | Ingress security | Origin exposure regression risk | 2 | 5 | 1 | Docs alone do not change runtime exposure, so impact is capped, but the work is small and removes misleading public bind examples. |
| 9.2 | Ready | Persist scheduler heartbeat/run status in non-sensitive fields | Analysis freshness | Scheduler freshness survives restart | 4 | 4 | 3 | Complements the aggregate endpoint by making scheduler state durable across process restarts. |
| 9.2 | Ready | Add safe runtime diagnostics for writable dirs and log readiness | Runtime resilience | Runtime readiness observability | 4 | 4 | 3 | Provides aggregate health of mounts/log paths without listing private files or reading contents. |
| 8.5 | Ready | Add a static ingress guard for public `stock-server` mappings | Ingress security | Origin exposure regression risk | 3 | 4 | 2 | Prevents regression to public host bindings in Compose/docs examples. |
| 5.7 | Later | Add freshness alerts/guards after the safe source exists | Analysis freshness | Stale-analysis detection latency | 2 | 4 | 2 | Impact is capped until the endpoint and durable heartbeat exist. |
| 5.7 | Later | Document Docker volume/data retention and cleanup guardrails | Runtime resilience | Data retention risk | 2 | 4 | 2 | Useful safety documentation, but does not move Docker health without an operator cleanup workflow. |
| 4.2 | Blocked | Add public-edge smoke through `stocks.sacud.com` | Ingress security/runtime resilience | Public edge health | 2 | 3 | 2 | Blocked because `stocks.sacud.com` is not allowlisted for the required Loop fetch helper. |
| Completed | Done | Rebind Docker app port to `127.0.0.1` | Ingress security | Origin exposure | 5 | 5 | 1 | Current Compose and allowed listener evidence show the prior top pick shipped. |

## Selected Next Change

Selected next change: fix Docker healthcheck port alignment and fail-closed behavior.

Implementation shape:

- Make the image-level Dockerfile healthcheck fail closed by removing the `python -c "import sys; sys.exit(0)"` fallback.
- Preserve standalone image behavior by probing the image's configured port default.
- Add or override the Compose `server` healthcheck so it probes the same `${API_PORT:-8010}` value used by the `stock-server` command and port mapping.
- Add a static regression test that fails if Docker healthchecks contain an always-success fallback or drift away from the Compose server port.

How to test:

- Local static/unit validation: `python -m pytest tests/test_docker_healthcheck.py tests/test_api_health.py` after adding the regression test.
- Syntax/smoke validation: `sh -n docker/entrypoint.sh` and `git diff --check`.
- Operator post-merge validation, with approval because it uses Docker: `docker compose -f docker/docker-compose.yml config`, `docker ps` health for `stock-server`, and `curl -fsS http://127.0.0.1:8010/health`.

Residual risk: this touches Docker runtime health semantics. The expected behavior is stricter: a broken API should make Docker health fail instead of reporting healthy. Rollback is reverting the Dockerfile/Compose healthcheck change.
