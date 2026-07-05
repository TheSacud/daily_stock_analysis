# AGENTS.md

## Sacud VPS Fork Workflow

- This local clone and the VPS deployment are based on the `TheSacud/daily_stock_analysis` fork.
- Keep `origin` pointing to `git@github.com:TheSacud/daily_stock_analysis.git`.
- Keep `upstream` pointing to `https://github.com/ZhuLinsen/daily_stock_analysis.git` for pulling original project updates only.
- Do not push to `upstream`; on the VPS it should stay configured as `DISABLED` for push.
- Use the `sacud/vps` branch for Sacud-specific deployment changes, local config examples, service wrappers, nginx/systemd notes, and integration work with Kai.
- To update from the original project: fetch `upstream`, merge or rebase `upstream/main` into `sacud/vps`, resolve conflicts deliberately, then push only to `origin`.
- Do not commit secrets, `.env` files, generated runtime data, Cloudflare Access tokens, API keys, or VPS-only private paths.

This file defines the default development process for this repository. The goal is to reduce repeated clarification, avoid rework, and keep changes aligned with the current project structure.

If this file differs from executable scripts, workflows, or current code behavior, trust the executable source and update the documentation as part of the related change so the rules do not drift.

## 1. Hard Rules

- Respect the existing directory boundaries:
  - Backend logic belongs in `src/`, `data_provider/`, `api/`, and `bot/`.
  - Web frontend changes belong in `apps/dsa-web/`.
  - Desktop changes belong in `apps/dsa-desktop/`.
  - Deployment and pipeline changes belong in `scripts/`, `.github/workflows/`, and `docker/`.
- Do not run `git commit`, `git tag`, or `git push` without explicit confirmation.
- Commit messages must be in English and must not add `Co-Authored-By`.
- Do not hardcode secrets, accounts, paths, model names, ports, or environment-specific branching logic.
- Prefer existing modules, configuration entry points, scripts, and tests. Do not add parallel implementations.
- Default to stability over opportunistic cleanup. Avoid unrelated refactors, abstractions, and infrastructure migrations unless the current task directly requires them.
- When adding configuration, update `.env.example` and the relevant docs at the same time.
- When changing user-visible capability, CLI/API behavior, deployment mode, notification behavior, or report structure, update the relevant docs and `docs/CHANGELOG.md`.
- When changing report format, report rendering, or Web UI screens, the PR description must include screenshots of the affected report/page. Prefer before/after evidence when there is a visual difference. If screenshots are not possible, explain why and provide alternative visual evidence.
- Issue/PR process screenshots, review screenshots, one-off acceptance screenshots, and temporary visual evidence must not be committed to the repository. Put them in the PR description, PR comments, GitHub attachments, Actions artifacts, or externally accessible evidence links. Long-term product documentation images are allowed when needed, but filenames and document semantics must not depend on a specific issue or PR number.
- The `[Unreleased]` section in `docs/CHANGELOG.md` uses a flat format: each entry is one line in the form `- [type] description`, where `type` is one of `feature`/`improvement`/`fix`/`docs`/`test`/`chore`. Do not add `### category headings` inside `[Unreleased]`; this reduces merge conflicts across concurrent PRs. Maintainers reorganize release entries into the formal categorized format when cutting a release.
- `README.md` is only for project positioning, high-level capability overview, quick start, main entry points, and sponsorship/cooperation information. Avoid updating README unless the change is homepage-level.
- Put detailed module behavior, page interactions, topic configuration, troubleshooting, field contracts, implementation semantics, and edge cases in the appropriate `docs/*.md` or topic document instead of README.
- When changing one side of bilingual documentation, evaluate whether the other side needs synchronization. If not synchronized, explain why in the delivery notes.
- Comments, docstrings, and log text should be clear and accurate. English is preferred for repository consistency.

## 1.1 PR Title Guidance (Non-Blocking)

- Prefer `<type>: <change summary>` for PR titles, for example `fix: restore market-review history persistence`. Preferred types are `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`.
- Titles should describe the actual change. Avoid `[codex]`, `codex`, `autocode`, `copilot`, or other tool/agent source prefixes.
- This guidance improves collaboration readability and consistency. It must not be used as a standalone review blocker.

## 1.2 Contribution Quality Baseline

- This repository does not accept PRs that substitute code volume, broad diffs, or patch-stacking review responses for real design convergence.
- Contribution quality is measured by whether the PR solves a clear problem, minimizes impact, preserves existing contracts, and covers real risk paths. It is not measured by added lines, file count, feature marketing, or an appearance of completeness.
- Do not treat this repository as a low-cost experiment, resume showcase, or contribution-farming target. Every PR must show that the author understands the current system contracts and has completed basic self-review, integration, and validation.
- AI-assisted development is acceptable. The problem is submitting AI-generated code without human semantic review, verification, and convergence. Such PRs are treated as low-quality submissions.
- After review feedback, do not only patch the exact lines called out by the reviewer and claim everything is fixed. Re-check every runtime entry point, configuration, test, doc, workflow, and user-visible path that shares the same business semantics.
- If a PR continues to show the same kind of contract drift, repeated fallback, test avoidance of real risk layers, or PR-body/diff mismatch after multiple review rounds, maintainers may ask to close and redo it instead of continuing point-by-point review.

## 2. AI Collaboration Asset Governance

- `AGENTS.md` is the single source of truth for repository AI collaboration rules.
- `CLAUDE.md` must be a symlink to `AGENTS.md` for Claude ecosystem compatibility.
- `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md` are mirrors or layered additions for GitHub Copilot / Coding Agent. If they conflict with this file, `AGENTS.md` wins.
- Repository collaboration skills live in `.claude/skills/`; analysis artifacts live in `.claude/reviews/`. Skills may be committed; reviews are local artifacts by default.
- Root `SKILL.md` and `docs/openclaw-skill-integration.md` are product or external integration documentation. They are not sources of truth for repository collaboration rules.
- If `.agents/skills/` or another agent-specific directory is added later, define the single source of truth first and then synchronize through scripts or mirrors. Do not hand-maintain multiple equivalent copies long term.
- When changing AI collaboration governance assets, run:

```bash
python scripts/check_ai_assets.py
```

## 3. Repository Overview

- Project positioning: an AI stock analysis system covering A-shares, Hong Kong stocks, and US stocks.
- Main flow: fetch data -> technical analysis/news retrieval -> LLM analysis -> report generation -> notification delivery.
- Key entry points:
  - `main.py`: main analysis task entry point.
  - `server.py`: FastAPI service entry point.
  - `apps/dsa-web/`: Web frontend.
  - `apps/dsa-desktop/`: Electron desktop app.
  - `.github/workflows/`: CI, release, and daily tasks.
- Core responsibilities:
  - `src/core/`: main flow orchestration.
  - `src/services/`: business service layer.
  - `src/repositories/`: data access layer.
  - `src/reports/`: report generation.
  - `src/schemas/`: schemas and data structures.
  - `data_provider/`: multi-source data adapters and fallback.
  - `api/`: FastAPI API.
  - `bot/`: bot integrations.
  - `scripts/`: local scripts.
  - `.github/scripts/`: GitHub automation scripts.
  - `tests/`: pytest tests.
  - `docs/`: documentation.

## 4. Common Commands

### Run The App

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Backend Validation

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
```

### Web / Desktop

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build

cd ../dsa-desktop
npm install
npm run build
```

### PR / CI Evidence

```bash
gh pr view <pr_number>
gh pr checks <pr_number>
gh run view <run_id> --log-failed
```

## 5. Default Workflow

1. Classify the task first: `fix / feat / refactor / docs / chore / test / review`.
2. Read the existing implementation, configuration, tests, scripts, workflows, and docs before editing.
3. Identify the change boundary: backend / API / Web / Desktop / workflow / docs / AI collaboration assets.
4. Check whether the change touches high-risk areas: configuration semantics, API/schema, data-source fallback, report structure, authentication, scheduling, release flow, or desktop startup chain.
5. Make the smallest change directly related to the current task. Do not bundle unrelated refactors.
6. If docs, scripts, or workflow descriptions disagree with the executable code, trust the code/workflow first and then decide whether to update the docs.
7. After editing, run the relevant checks from the validation matrix below.
8. Final delivery should explain:
   - What changed.
   - Why it changed.
   - Validation performed.
   - Items not validated.
   - Risks.
   - Rollback path.

## 6. Validation Matrix

### CI Coverage Principles

Current repository CI mainly includes:

| Check | Source | Description | Blocking |
| --- | --- | --- | --- |
| `ai-governance` | `.github/workflows/ci.yml` | Validates relationships between `AGENTS.md`, `CLAUDE.md`, `.github` instructions, and `.claude/skills` | Yes |
| `backend-gate` | `.github/workflows/ci.yml` | Runs `./scripts/ci_gate.sh` | Yes |
| `docker-build` | `.github/workflows/ci.yml` | Docker build and key module import smoke | Yes |
| `web-gate` | `.github/workflows/ci.yml` | Runs `npm run lint` and `npm run build` when frontend changes trigger it | Yes, when triggered |
| `network-smoke` | `.github/workflows/network-smoke.yml` | `pytest -m network` plus `scripts/test.sh quick` | No, observation only |
| `pr-review` | `.github/workflows/pr-review.yml` | PR static checks, AI review, and automatic labels | No, helper only |

If a PR already has relevant CI results, those results may be cited directly. If CI does not cover the changed surface, or local/CI environments differ materially, explain local validation and gaps.

### By Changed Surface

- Python backend changes:
  - Applies to: `main.py`, `src/`, `data_provider/`, `api/`, `bot/`, `tests/`.
  - Prefer: `./scripts/ci_gate.sh`.
  - Minimum: `python -m py_compile <changed_python_files>`.
  - If the change affects API, task orchestration, report generation, notification delivery, data-source fallback, authentication, or scheduling, state whether that path was covered.

- Web frontend changes:
  - Applies to: `apps/dsa-web/`.
  - Default: `cd apps/dsa-web && npm ci && npm run lint && npm run build`.
  - If the change affects API integration, routing, state management, Markdown/chart rendering, or auth state, state the interaction surface and uncovered risks.

- Desktop changes:
  - Applies to: `apps/dsa-desktop/`, `scripts/run-desktop.ps1`, `scripts/build-desktop*.ps1`, `scripts/build-*.sh`, `docs/desktop-package.md`.
  - Default: build Web first, then build desktop.
  - If platform limits prevent full validation, state whether Web artifacts, Electron build, and release workflow impact were checked.

- API / schema / auth integration changes:
  - Applies to: `api/**`, `src/schemas/**`, `src/services/**`, `apps/dsa-web/**`, `apps/dsa-desktop/**`.
  - Cover the relevant backend validation plus affected client build validation.
  - For login, Cookie, session, polling state, field additions/removals, or enum changes, explicitly state compatibility impact.

- Documentation and governance changes:
  - Applies to: `README.md`, `docs/**`, `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/**`, `.claude/skills/**`.
  - Code tests are not mandatory.
  - Confirm commands, config keys, filenames, and workflow names against the actual repository.
  - When changing AI collaboration governance assets, run `python scripts/check_ai_assets.py`.

- Workflow / script / Docker changes:
  - Applies to: `.github/**`, `scripts/**`, `docker/**`.
  - Run the closest local validation for the changed surface.
  - In delivery, state which pipeline, release path, or deployment path changed.
  - If Docker or GitHub Actions validation was not run, explain why and note the potential risk.

- Network or third-party dependency changes:
  - Run offline or deterministic checks first.
  - Confirm timeout, retry, fallback, error wording, and degradation paths still hold.
  - If online validation was not run, state why.

## 7. Stability Guardrails

- Configuration and runtime entry points:
  - When changing `.env` semantics, defaults, CLI parameters, service startup mode, or scheduling semantics, assess local runs, Docker, GitHub Actions, API, Web, and Desktop together.
  - New configuration should usually be optional: the app should run without it, and configuration should enhance capability rather than introduce stacked switches or mutually exclusive modes.

- Data sources and fallback:
  - When changing `data_provider/`, check source priority, failure degradation, field standardization, cache behavior, and timeout strategy.
  - One data source failure should not take down the full analysis flow unless the requirement explicitly asks for fail-fast behavior.

- API / Web / Desktop compatibility:
  - When changing API, schema, auth, or report payloads, check backend, Web, and Desktop compatibility together.
  - Prefer adding fields, preserving old fields, or providing a compatibility layer over silently breaking existing clients.

- Reports / prompts / notifications:
  - When changing report structure, prompts, extractors, notification templates, or bot chains, check whether upstream inputs and downstream consumers remain compatible.
  - One notification channel failure should not take down the main analysis flow unless the requirement explicitly asks for fail-fast behavior.
  - When changing `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, include the complete latest prompt in the PR description.

- Workflows / releases / packaging:
  - When changing automatic tags, releases, Docker publishing, daily analysis, or desktop packaging, assess triggers, artifact paths, permission boundaries, and rollback.
  - Automatic tagging remains opt-in by default: only commit titles containing `#patch`, `#minor`, or `#major` trigger version updates, unless the requirement explicitly asks to change release policy.

## 8. Issue / PR / Skill Workflow

- The repository has these reusable skills:
  - `.claude/skills/analyze-issue/SKILL.md`
  - `.claude/skills/analyze-pr/SKILL.md`
  - `.claude/skills/fix-issue/SKILL.md`
- If the task is explicitly issue analysis, PR review, or issue fixing, prefer the matching skill and save artifacts to `.claude/reviews/`.
- Skill commands, templates, validation order, and delivery structure must stay aligned with `AGENTS.md`.
- Before creating/updating a PR, reviewing a PR, or analyzing an issue, synchronize the latest code baseline: check worktree status and run `git fetch --all --prune`; if the worktree is clean and the current branch can fast-forward, run `git pull --ff-only`. If local changes, conflicts, risky untracked files, or non-fast-forward history make that unsafe, do not force checkout, stash, reset, or overwrite local state. For PR review / issue analysis, analyze fetched remote refs or the PR head and record why the local worktree was not updated, the current local HEAD, and the remote baseline used. For PR creation/update, first explain the current branch versus target baseline difference and ask for confirmation if rebase, merge, or continuing from the current branch needs a decision.
- Skills should read CI/workflow evidence first, then decide whether local validation is needed.
- Except for the safe fast-forward synchronization above, skills must not run `git pull`, `git push`, `git tag`, `gh pr create`, or other commands that change remote or current branch state by default. These operations require user confirmation.
- Default PR review order:
  1. Necessity.
  2. Relevance.
  3. Title suggestion (`<type>: <change summary>`, no tool/agent prefix; not a hard blocker).
  4. Description completeness against `.github/PULL_REQUEST_TEMPLATE.md`.
  5. Validation evidence.
  6. Implementation correctness.
  7. Merge recommendation.
- For `fix` PRs, explain: original problem, root cause, fix point, and regression risk.
- Merge blockers:
  - Correctness or security problems.
  - Blocking CI failure.
  - Material contradiction between PR description and actual diff.
  - Missing rollback plan.
  - Repeated unconverged contract drift, patch stacking, or invalid validation evidence.

## 8.1 Review Feedback Handling And Patch-Stacking Ban

When handling review feedback, do not only add a local patch at the lines the reviewer named and claim everything is fixed. First understand the business contract behind the review feedback, then check every runtime entry point, configuration, test, doc, workflow, and user-visible path that shares the same semantics.

After receiving review feedback, process it in this order:

1. List each original issue raised by the reviewer.
2. Explain the root cause; do not only describe which lines changed.
3. Identify every related path affected by the same semantics, such as runtime, API/Web, CLI, diagnostics, workflow, docs, and tests.
4. Fix the full contract, not only the currently failing test or commented line.
5. Add regression tests or final-entry validation that covers the reviewer counterexample, or clearly explain why validation is not possible.
6. Update the PR body so scope, validation, compatibility, risk, and rollback match the current head.

If you cannot complete this convergence, do not continue stacking patches and do not claim the PR is ready to merge. State whether the PR should be split, closed and redone, or needs maintainer confirmation on a new minimal scope.

The following are treated as low-quality PR behavior:

- Using broad fallback, silent degradation, or `return False/None/[]` to hide unclear contracts.
- Mocking away the real risk layer so tests only prove a local implementation detail.
- Claiming the issue is closed because CI passed without covering the reviewer counterexample.
- PR body mismatches with the actual diff, validation results, or compatibility risk.
- Continuing to add scattered patches after review instead of reconverging the full semantics.
- The same business semantics behaving inconsistently across runtime, Web/API, docs, workflow, and tests.

CI passing only means automated checks passed. It does not replace human semantic convergence and does not, by itself, prove that reviewer counterexamples are closed.

## 9. Delivery And Release

- Default delivery structure:
  - What changed.
  - Why it changed.
  - Validation performed.
  - Items not validated.
  - Risks.
  - Rollback path.
- For docs-only tasks, you may write `Docs only, tests not run`, but still state whether commands and filenames were checked.
- Automatic tagging is off by default. Only commit titles containing `#patch`, `#minor`, or `#major` trigger version updates.
- Manual tags must be annotated tags.
- User-visible changes should normally land through a PR with labels and validation notes.