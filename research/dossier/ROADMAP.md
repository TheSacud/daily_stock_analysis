# Daily Stock Analysis Research Roadmap

Last refreshed: 2026-07-07 from the 2026W27 research swarm synthesis.

North-star: `stocks.sacud.com` should provide a dependable, authenticated stock-analysis dashboard/API with fresh analysis artifacts, healthy scheduled processing, and no direct origin port exposure outside Nginx/Cloudflare.

## Current Metrics

| Metric | Current value | Evidence | Gap |
| --- | --- | --- | --- |
| Origin exposure | Allowed live listener evidence shows `127.0.0.1:8010` only | `ss -ltn '( sport = :8010 )'` on 2026-07-07 | External TCP and Docker NAT were not re-measured under no-arbitrary-network/no-sudo limits. |
| Local health | `status=ok`, timestamp `2026-07-07T15:57:09.227662` | `curl -fsS --max-time 5 http://127.0.0.1:8010/health` | None for local FastAPI health. |
| Docker health | Untrusted from source until fixed | `docker/Dockerfile` probes `8000` and falls back to success; Compose server runs `${API_PORT:-8010}` | Live `docker ps` was not run because Docker is prohibited for this worker. |
| Analysis freshness | Not safely measurable yet | Authenticated scheduler endpoint returned `401`; no safe aggregate freshness endpoint exists | Latest history/report/market-review timestamps require a new sanitized aggregate signal or approved authenticated check. |

## Roadmap

Scoring uses `impact x confidence / sqrt(effort)` against the north-star. Status values are `done`, `selected`, `ready`, `later`, or `blocked`.

| Score | Status | Milestone | Lens | Target metric | I | C | E | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Completed | done | Rebind Docker app port to `127.0.0.1` | Ingress security | Origin exposure | 5 | 5 | 1 | Keep regression checks; do not re-select. |
| 25.0 | selected | Fix Docker healthcheck port alignment and fail-closed behavior | Runtime resilience | Docker health agreement | 5 | 5 | 1 | Update Dockerfile/Compose healthchecks and add static regression coverage. |
| 14.4 | ready | Add a safe aggregate freshness endpoint/service with regression tests | Analysis freshness | Analysis freshness observability | 5 | 5 | 3 | Return latest non-sensitive scheduler/history/report freshness and stale/ok state. |
| 10.0 | ready | Sync deployment docs/FAQ to loopback-only app-port examples | Ingress security | Origin exposure regression risk | 2 | 5 | 1 | Replace public `8000:8000`/`-p 8000:8000` examples where they imply origin exposure. |
| 9.2 | ready | Persist scheduler heartbeat/run status in non-sensitive fields | Analysis freshness | Scheduler freshness survives restart | 4 | 4 | 3 | Store last run/success/error timestamps without symbols, report bodies, or credentials. |
| 9.2 | ready | Add safe runtime diagnostics for writable dirs and log readiness | Runtime resilience | Runtime readiness observability | 4 | 4 | 3 | Report aggregate writability/readiness only; no file listings or content reads. |
| 8.5 | ready | Add a static ingress guard for public `stock-server` mappings | Ingress security | Origin exposure regression risk | 3 | 4 | 2 | Fail CI on public app-port mappings in Compose/docs examples. |
| 5.7 | later | Add freshness alerts/guards after the safe source exists | Analysis freshness | Stale-analysis detection latency | 2 | 4 | 2 | Bundle after aggregate freshness and durable heartbeat exist. |
| 5.7 | later | Document Docker volume/data retention and cleanup guardrails | Runtime resilience | Data retention risk | 2 | 4 | 2 | Define retention boundaries for data/log/report/strategy/token-cache paths. |
| 4.2 | blocked | Add public-edge smoke through `stocks.sacud.com` | Ingress security/runtime resilience | Public edge health | 2 | 3 | 2 | Requires Loop capacity allowlist for `stocks.sacud.com`. |

## Notes

- There were no open PRs on 2026-07-07, so no active PR overlap changed the selected next item.
- The Loop seed remains useful as the upstream north-star, but its stage text is stale for origin exposure after the loopback bind shipped.
- Docker/sudo probes require explicit operator-approved read-only validation outside this worker's limits.
