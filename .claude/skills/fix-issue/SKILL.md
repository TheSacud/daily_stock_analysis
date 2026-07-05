# Fix Issue

Implement a fix based on issue analysis, then complete validation, risk notes, and rollback notes according to repository rules.

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis

## Usage

```text
/fix-issue <issue_number>
```

## Prerequisites

Prefer completing `/analyze-issue <issue_number>` first so the problem is validated and the boundary is clear.

## Instructions

### Step 1: Confirm The Analysis Baseline

Check whether `.claude/reviews/issues/issue-<number>.md` exists. If it does not, first perform issue analysis or include the minimal analysis conclusion in this fix.

### Step 2: Sync The Latest Code Baseline And Choose A Safe Work Mode

Before starting the fix or preparing to create/update a PR, refresh according to `AGENTS.md`:

```bash
git status --short
git fetch --all --prune
# Run only when the worktree is clean and the current branch can fast-forward:
git pull --ff-only
```

- Default to making the smallest relevant change in the current worktree.
- Run and accept `git pull --ff-only` only when the worktree is clean and the current branch has a fast-forwardable upstream.
- If there are local changes, conflicts, risky untracked files, no upstream branch, or non-fast-forward history, do not run `stash`, `reset`, force checkout, or overwrite local state. Record local HEAD, remote baseline used, and why the local worktree could not be updated.
- If creating/updating a PR later, first explain the current branch versus target baseline difference. Ask the user to confirm rebase, merge, or continuing from the current branch when needed.
- Do not switch branches or rewrite the user's current state by default.
- If the user explicitly asks to create a branch, perform only the minimum necessary branch operation.

### Step 3: Implement The Fix

- Use the issue conclusion to locate relevant files.
- Prefer existing modules, configuration entry points, scripts, and tests.
- Preserve backward-compatible default behavior and avoid breaking fallback / fail-open paths.
- If the fix changes user-visible behavior, configuration semantics, CLI/API, deployment, notifications, or report structure, update relevant docs, `docs/CHANGELOG.md`, and `.env.example`.
- When adding a `docs/CHANGELOG.md` entry, append one line under `[Unreleased]` in the form `- [type] description`, choosing `type` from `feature`/`improvement`/`fix`/`docs`/`test`/`chore`. Use `fix` only for bug fixes. Do not add `### category headings` inside `[Unreleased]`.
- `README.md` is only for project positioning, core capabilities, quick start, main entry points, and sponsorship/cooperation information. Avoid updating README unless necessary.
- Put detailed module behavior, page interactions, topic configuration, troubleshooting, field contracts, implementation semantics, and edge cases in the appropriate `docs/*.md` file.

### Step 4: Validate By Changed Surface

Run the closest checks from the `AGENTS.md` validation matrix:

- Backend preferred: `./scripts/ci_gate.sh`.
- Backend minimum: `python -m py_compile <changed_python_files>`.
- Frontend: `cd apps/dsa-web && npm ci && npm run lint && npm run build`.
- Desktop: build Web first, then build desktop.

If full validation cannot be completed, record the gap, reason, and potential risk.

### Step 5: Update The Issue Analysis Document

Append to `.claude/reviews/issues/issue-<number>.md`:

```markdown
## Fix Implementation

**Date**: YYYY-MM-DD

### Changes Made

- Files and change points:

### Validation

- Run:
- Not run:

### Risks

- Risks:

### Rollback

- Rollback path:
```

### Step 6: Confirm Follow-Up Actions

If the user asks to create a PR, generate a PR title, or draft a PR description, suggest a PR title that follows `AGENTS.md`:

- Use `<type>: <change summary>`, for example `fix: restore market-review history persistence`.
- Prefer `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`.
- Title should describe only the actual change. Avoid `[codex]`, `codex`, `autocode`, `copilot`, or another tool/agent source prefix.
- This convention is for collaboration consistency only and should not be treated as a process blocker.

Only run the following after explicit user confirmation:

- Create a branch.
- `git commit`.
- `git push`.
- Create a PR.
- Reply to or close the issue.

## Allowed Auto-Actions (No Confirmation Needed)

- Read and analyze code.
- Run `git fetch --all --prune`, and run `git pull --ff-only` only when the worktree is clean and fast-forwardable.
- Apply the smallest fix directly related to the current task.
- Run non-destructive local validation.
- Update the local issue analysis document.

## Actions Requiring Confirmation

1. Switch or create a branch.
2. `git commit`.
3. `git push`.
4. Create a PR.
5. Reply to or close the issue.