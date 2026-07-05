# Analyze PR

Analyze a GitHub pull request and evaluate necessity, description completeness, validation evidence, main risks, and whether it can be merged directly.

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis/pulls

## Usage

```text
/analyze-pr <pr_number>
```

## Instructions

Use concise English and follow root `AGENTS.md` and `.github/PULL_REQUEST_TEMPLATE.md` first.

### Step 1: Sync The Latest Code Baseline

Before analyzing a PR, refresh remote state and safely advance the local baseline when possible:

```bash
git status --short
git fetch --all --prune
# Run only when the worktree is clean and the current branch can fast-forward:
git pull --ff-only
```

- Run and accept `git pull --ff-only` only when the worktree is clean and the current branch has a fast-forwardable upstream.
- If there are local changes, conflicts, risky untracked files, no upstream branch, or non-fast-forward history, do not run `stash`, `reset`, force checkout, or overwrite local state. Analyze against fetched `origin/main`, the PR head, or the GitHub diff instead.
- In the output document `Validation Evidence` section, record the sync result: local HEAD, remote baseline used, and why the local worktree was not updated if applicable.

### Step 2: Fetch PR Information

```bash
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis --comments
gh pr checks <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr diff <pr_number> --repo ZhuLinsen/daily_stock_analysis
```

If CI failed, inspect failed logs before immediately rerunning all checks locally:

```bash
gh run view <run_id> --log-failed
```

### Step 3: Check Title And Description Completeness

First check whether the PR title follows the non-blocking `AGENTS.md` guidance:

- Format should be `<type>: <change summary>`, for example `fix: restore market-review history persistence`.
- Prefer `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`.
- It should not include `[codex]`, `codex`, `autocode`, `copilot`, or another tool/agent source prefix.
- The title should describe the actual change. If it does not match the diff, mention that in description completeness, but do not treat title format alone as a review-process blocker.

Compare against `.github/PULL_REQUEST_TEMPLATE.md` and confirm whether it covers:

- `PR Type`.
- `Background And Problem`.
- `Scope Of Change`.
- `Issue Link`.
- `Verification Commands And Results`.
- `Visual Evidence`, only when the PR changes report format, report rendering, or Web UI screens.
- `Compatibility And Risk`.
- `Rollback Plan`.

If the PR touches third-party model/API compatibility semantics, fixed request parameters, OpenAI-compatible routing, YAML aliases, fallback behavior, or runtime configuration save/cleanup/migration logic, also check whether the description states:

- Official source links or announcements.
- Current locked dependency / runtime compatibility range, such as the LiteLLM version window.
- Verified call-chain coverage.
- Whether old configuration is silently rewritten, cleared, migrated, or left unchanged.
- Minimal rollback path, usually reverting the PR.

If the PR changes report format, report rendering, or Web UI screens, check whether `Visual Evidence` includes affected report/page screenshots. Prefer before/after evidence when there is a visual difference. If screenshots are impossible, the description should explain why and provide alternative visual evidence.

### Step 4: Prefer CI / Diff Evidence

- Use `gh pr checks`, PR diff, existing tests, and workflow logs first.
- Add local minimal validation only when CI does not cover the changed surface, CI evidence is not enough to classify the issue, or a key regression risk needs verification.
- Do not switch branches by default and do not run `gh pr checkout` by default.

If local validation is required, choose the closest check for the changed surface:

- Backend: `./scripts/ci_gate.sh` or `python -m py_compile <changed_python_files>`.
- Frontend: `cd apps/dsa-web && npm ci && npm run lint && npm run build`.
- Desktop: build Web first, then Electron.

### Step 5: Evaluate Correctness And Risk

Focus on:

- Whether the PR solves a clear problem without bundling unrelated changes.
- Whether it breaks API / schema / Web / Desktop compatibility.
- Whether it breaks fallback, degradation paths, notification chains, or release flow.
- Whether there are clear logic errors, swallowed exceptions, security issues, or configuration semantic changes without docs.

### Step 6: Generate The Review Document

Save it to `.claude/reviews/prs/pr-<number>.md`.

## Output Document Format

```markdown
# PR #<number> Analysis

**Date**: YYYY-MM-DD
**Status**: Pending Review

## Findings

- [Severity] file:line - Issue description

## Summary

- Necessity:
- Linked issue:
- PR type:
- PR title:
- Description completeness:
- Validation:
- Main risks:
- Mergeable directly:

## Validation Evidence

- Code sync baseline:
- CI conclusion:
- Local supplemental validation, if any:

## Compatibility And Risk

- API / Web / Desktop:
- Config / Docker / GitHub Actions:
- Fallback / notifications / report structure:
- Third-party dependency / official constraint sources:
- Runtime compatibility window / covered chains:
- Old config migration or silent rewrite risk:

## Draft Review Comment

<Suggested comment>
```

## Allowed Auto-Actions (No Confirmation Needed)

- Fetch PR metadata, diff, comments, and CI status.
- Run `git fetch --all --prune`, and run `git pull --ff-only` only when the worktree is clean and fast-forwardable.
- Read related code, templates, workflows, and docs.
- Run minimal local validation when necessary.
- Generate the review document.

## Actions Requiring Confirmation

Ask the user before doing any of these:

1. Post a comment.
2. Approve the PR.
3. Request changes.
4. Merge the PR.
5. Close the PR.