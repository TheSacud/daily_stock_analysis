# Security And Rollback Review

Review date: 2026-07-06

This note records the read-only security and rollback guardrail review for the
Sacud VPS fork workflow. It is intended to support PR handoff and follow-up
planning. It does not approve an autonomous deploy.

## Scope

Reviewed repository evidence:

- `docs/DEPLOY_EN.md` and deployment-related documentation.
- `docker/Dockerfile`, `docker/docker-compose.yml`, and `docker/entrypoint.sh`.
- `.github/workflows/ci.yml`, `.github/workflows/auto-tag.yml`,
  `.github/workflows/docker-publish.yml`, and `.github/PULL_REQUEST_TEMPLATE.md`.
- `.gitignore`, `docs/CONTRIBUTING_EN.md`, `docs/beginner-client-setup.md`,
  and `scripts/check_env.py`.

Not reviewed:

- No `.env` files, runtime data directories, logs, reports, database files,
  OAuth token caches, production service state, or raw credentials.
- No live request to the public deployment.
- No service restart, deployment command, Docker command, or production mutation.

## Existing Guardrails

- PR checks are defined in `.github/workflows/ci.yml`, including AI governance,
  backend gate, Docker image build/smoke, and frontend gate when Web files
  change.
- Automatic tagging is opt-in in `.github/workflows/auto-tag.yml`; only commit
  messages containing `#patch`, `#minor`, or `#major` trigger a tag update.
- Docker release publishing is tag or manual-dispatch based in
  `.github/workflows/docker-publish.yml`; the release path validates an
  annotated tag message and runs backend and Docker smoke checks before image
  publication.
- The PR template asks for compatibility, risk, and rollback details for every
  PR.
- The Docker image creates a non-root `dsa` user. Its entrypoint repairs
  writable mount ownership for `/app/data`, `/app/logs`, `/app/reports`, and
  the Longbridge cache path, then drops privileges before running the app.
- Compose binds the API service to loopback by default and mounts strategies as
  read-only.
- `.gitignore` excludes `.env` variants, local review artifacts, runtime data,
  reports, logs, database files, and local secret artifacts.
- User docs already warn contributors not to commit `.env`, API keys, access
  tokens, or runtime data.

## Missing Or Incomplete Guardrails

### Rollback

There is no Sacud VPS rollback runbook that defines the last-known-good
application ref or image, backup points, restore order, post-rollback checks, or
who may authorize rollback. The general deployment guide includes migration
backup examples and redeploy commands, but it does not define a production
rollback checklist for failed PR handoff, failed image rollout, failed service
restart, or broken public WebUI access.

### Permissions

The Docker runtime path is mostly least-privilege after startup, but the systemd
example still runs as `root`. The repo does not yet document a Sacud-specific
runtime user, writable directory ownership model, read-only production code
directory policy, or when temporary elevated access is allowed.

### Secret Handling

Secret files are ignored and docs warn against committing them, but the
operational path still has gaps:

- The migration example packages `.env`, runtime data, logs, and reports
  together without a redaction, encryption, or retention checklist.
- `scripts/check_env.py` prints credential prefixes for local diagnostics. That
  output should not be copied into PRs, issue comments, Kanban comments, or
  shared logs.
- There is no worker-facing diagnosis checklist that explicitly blocks reading
  `.env`, token caches, DB files, logs, reports, or private production state.

### Deploy Approval

The repository has PR validation and release workflows, but it does not define
the approval boundary for Sacud VPS production changes. In particular, it does
not state that autonomous workers must stop at reviewable PR handoff unless a
maintainer explicitly approves production mutation, service restart, Docker
operation, or privileged command execution.

### Public Exposure

The Compose file binds the API to `127.0.0.1`, which is a good default. The
repository does not yet document the approval requirement for changing public
exposure, reverse-proxy behavior, Cloudflare Access, TLS, or authentication
controls for `stocks.sacud.com`.

## Required Follow-Up Cards

Create separate implementation cards instead of broad recommendations:

1. `security: add Sacud VPS rollback runbook`
   - Add a VPS rollback document that names the rollback ref/image, backup
     artifacts, restore order, verification commands, and escalation owner.
   - Acceptance: rollback can be executed from a reviewed PR or release without
     reading raw secrets in shared output, and the rollback path includes a
     public WebUI health check that does not expose private data.

2. `security: document production write and deploy approval boundary`
   - Add a policy section for PR-only workers: no production mutation, service
     restart, Docker operation, privileged command, or deployment without
     explicit maintainer approval.
   - Acceptance: the policy states who may approve, what approval must say, and
     where deployment evidence belongs.

3. `security: replace root systemd example with least-privilege service`
   - Update the direct/systemd deployment guidance to use a dedicated runtime
     user and tightly scoped writable directories.
   - Acceptance: root is needed only for service installation or directory
     ownership setup, and secrets are kept outside committed files with
     restrictive permissions.

4. `security: redact diagnostic credential prefixes`
   - Change diagnostics that print key or token prefixes to report only
     configured/missing status, or add an explicit local-only unsafe flag.
   - Acceptance: shared diagnostic output cannot reveal key prefixes, webhook
     fragments, token cache paths containing account identifiers, or other
     credential-derived material by default.

5. `security: add backup and migration secret-handling checklist`
   - Document how to back up `.env`, runtime data, reports, logs, and token
     caches without committing, attaching, or pasting sensitive content.
   - Acceptance: backups require encrypted or access-controlled storage,
     retention guidance, and a redacted manifest suitable for PR or ticket
     evidence.

6. `security: document public WebUI exposure controls`
   - Add a Sacud deployment note for loopback binding, reverse proxy changes,
     access control, TLS, and public URL validation.
   - Acceptance: any change that exposes the app publicly requires PR review,
     explicit deployment approval, and a rollback step for the proxy route.

## PR Handoff Notes

- This review is documentation-only and has no runtime compatibility impact.
- It does not change provider/model/base URL or runtime config
  cleanup/migration semantics; existing configuration remains unchanged.
- Rollback for this note is to revert the documentation PR.
- A draft PR should remain review-only until the follow-up guardrail cards are
  triaged. Do not deploy this change as evidence that production approval has
  been granted.
