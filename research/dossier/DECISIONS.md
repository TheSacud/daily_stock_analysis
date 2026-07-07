# Daily Stock Analysis Research Decisions

## 2026-07-07 - Select Docker Healthcheck Contract Fix

Context:

- The 2026W27 swarm covered ingress security, analysis freshness, and runtime resilience.
- No open PRs currently overlap the selected next change.
- The prior top recommendation, rebinding the Docker app port to `127.0.0.1`, has shipped in repo history and current Compose source.
- Allowed live checks show local health is green and the app listener is loopback-only.
- Live Docker health, Docker NAT, and broad host process inspection were not run because this worker is prohibited from Docker and broad sudo.

Decision:

- Mark the Docker loopback rebind as done and do not recommend it again.
- Select `Fix Docker healthcheck port alignment and fail-closed behavior` as the next change.
- Keep the safe aggregate freshness endpoint as the next ready item after the Docker health contract is fixed.

Why:

- Docker health is a north-star metric, but current source can report healthy without proving FastAPI is reachable.
- The fix is low effort and high confidence: remove the always-success fallback and align probes with the actual runtime port.
- It closes a concrete disagreement between FastAPI `/health` and Docker health before adding broader diagnostics.

How to validate the selected change:

- Add a static regression test for Docker healthcheck port alignment and absence of always-success fallbacks.
- Run `python -m pytest tests/test_docker_healthcheck.py tests/test_api_health.py`.
- Run `sh -n docker/entrypoint.sh` and `git diff --check`.
- With operator approval after merge/deploy, run read-only `docker ps` health and `curl -fsS http://127.0.0.1:8010/health`.

Rollback:

- Revert the Dockerfile/Compose healthcheck change. The expected behavior after the fix is stricter Docker health reporting, so a failing healthcheck should be investigated before rollback.
