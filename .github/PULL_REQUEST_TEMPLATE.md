## PR Type

- [ ] fix
- [ ] feat
- [ ] refactor
- [ ] docs
- [ ] chore
- [ ] test

## Background And Problem

Describe the current problem, impact, and trigger scenario.

## Scope Of Change

List the modules and files changed in this PR.

> Please list the full changed-file scope from the actual `git diff` (include total file count when practical). Do not omit docs, backend, API, or frontend files because that makes the PR description inconsistent with the diff.

> If this PR changes collaboration or governance files such as `.github/PULL_REQUEST_TEMPLATE.md`, `.github/copilot-instructions.md`, `AGENTS.md`, `.github/instructions/*`, or `.claude/skills/**`, include the reason for the change, impact surface, and rollback path (default: revert) in Summary / Compatibility / Rollback.

Suggested commands:

```bash
BASE_REF=$(git merge-base HEAD origin/main)
git diff --stat "$BASE_REF"..HEAD
git diff --name-only "$BASE_REF"..HEAD
```

- File count / changed lines:
- Full file list:
- Documentation files updated (`docs/*`):

## Issue Link

Fill in one of:

- `Fixes #<issue_number>`
- `Refs #<issue_number>`
- If there is no issue, explain the motivation and acceptance criteria.

## Verification Commands And Results

Paste the commands you actually ran and the key results. Do not only write `tested`.

```bash
# example
./scripts/ci_gate.sh
python -m pytest -m "not network"
```

> `Full-suite note` must match the current HEAD CI result for this PR. If local reproduction has environment-specific failures, clearly mark them as local environment differences and include the GitHub CI conclusion and link.
> Do not keep historical failure wording unrelated to this PR. Report the current result.
> If a previous description still mentions `./scripts/ci_gate.sh` failures, update it to the current HEAD CI state or explain the source of difference from HEAD CI.
> If `Full-suite note` conflicts with current HEAD CI, update the PR description before submitting.

Required CI status fields:

- ai-governance: `pass` / `fail`, with link.
- backend-gate: `pass` / `fail`, with link.
- docker-build: `pass` / `fail`, with link.
- web-gate: `pass` / `fail`, with link.
- If this PR changes `.github/PULL_REQUEST_TEMPLATE.md` or similar process templates, explain necessity, impact boundary, and rollback path (default `revert this PR`); otherwise split process-template changes into a dedicated chore PR.

Key output / conclusion:

- Required current HEAD CI line: `ai-governance:pass / backend-gate:pass / docker-build:pass / web-gate:pass`, replacing values with the actual result and linking each check.
- If local failures are kept, include local environment difference, current CI pass/fail result, and CI link in the same section.
- If everything passes, add: `Current status: all pass`, and confirm all HEAD CI checks are pass.

## Visual Evidence (if applicable)

If this PR changes report formatting, report rendering, or Web UI, attach affected report/page screenshots here. Prefer before/after screenshots when relevant. Issue/PR process screenshots, review screenshots, one-off acceptance screenshots, and temporary visual evidence should be linked from the PR body/comments, GitHub attachments, Actions artifacts, or externally accessible evidence; do not commit them as repository files.

If screenshots cannot be captured, explain why and provide reproducible alternative evidence, such as Playwright/e2e artifact paths, review links, and traceable commands. For Web settings or report-rendering changes, the screenshot or alternative evidence must point to the changed item.

Suggested Web UI evidence path:

- Command: `cd apps/dsa-web && npx playwright test e2e/smoke.spec.ts --grep "settings page"`
- Artifact path: `apps/dsa-web/test-results/**/smoke-settings-page-*.png`
- Notes: the screenshot should show the modified setting field, label, or help text.

- Screenshot links:
- Suggested settings page names: `smoke-settings-page-en`.
- Before & after, if any:
- Settings field change note:
- Reason if not applicable, with reproducible evidence and command:

## Compatibility And Risk

Describe compatibility impact and potential risks. Write `None` if not applicable.

- If this PR changes third-party model/API compatibility, request parameters, routing prefixes, or provider fallback behavior, include an official source link or announcement and clarify whether the rule is permanent, runtime-specific, or a temporary compatibility workaround. Also list affected external APIs/services, regression scope, and rollback.
- If this PR does not touch third-party model/API, provider/model/base URL, or runtime config save/cleanup/migration semantics, write: `This PR does not change provider/model/base URL or runtime config cleanup/migration semantics; existing configuration remains unchanged; rollback is to revert this PR.`
- If this PR changes `.github/PULL_REQUEST_TEMPLATE.md` or other PR workflow template files, state that it only affects collaboration process and template maintenance, not runtime behavior; rollback is to revert; mention whether automated submission flow is affected.
- If this PR depends on a specific runtime or locked dependency window, such as a LiteLLM version range, OpenAI-compatible routing, or YAML alias behavior, state the verified compatibility range and covered paths.
- If this PR touches runtime config save, cleanup, migration, or backfill logic, state whether old config is automatically rewritten, cleared, migrated, or preserved, and how users can restore previous behavior.

## Rollback Plan

Provide at least one actionable rollback step.

- For compatibility fixes, include the minimal rollback path, such as `revert this PR`, and state whether additional config or data rollback is required.

## EXTRACT_PROMPT Change (if applicable)

If this PR changes `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, paste the full updated prompt here.

<details>
<summary>Expand: Full EXTRACT_PROMPT</summary>

```
(paste full prompt here)
```

</details>

## Checklist

- [ ] This PR has a clear motivation and value.
- [ ] Reproducible verification commands and results are included.
- [ ] Compatibility and risk have been assessed.
- [ ] A rollback plan is provided.
- [ ] If report formatting or Web UI changed, affected report/page screenshots are linked in the PR body/comments and one-off acceptance screenshots are not committed as repository files.
- [ ] If Web settings fields changed (labels or help text), settings page screenshots are included, or alternative visual evidence with command + artifact path points to the changed item.
- [ ] If user-visible changes are included, relevant docs and `docs/CHANGELOG.md` are updated; `README.md` is updated only for homepage-level changes, with details kept in `docs/*.md`.