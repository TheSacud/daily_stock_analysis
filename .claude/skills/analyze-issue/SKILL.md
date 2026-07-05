# Analyze Issue

Analyze a GitHub issue and judge whether it is real, how urgent it is, whether it belongs to this repository, and what action is recommended.

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis/issues

## Usage

```text
/analyze-issue <issue_number>
```

## Instructions

Use concise English and follow root `AGENTS.md` first.

### Step 1: Sync The Latest Code Baseline

Before analyzing an issue, refresh remote state and safely advance the local baseline when possible:

```bash
git status --short
git fetch --all --prune
# Run only when the worktree is clean and the current branch can fast-forward:
git pull --ff-only
```

- Run and accept `git pull --ff-only` only when the worktree is clean and the current branch has a fast-forwardable upstream.
- If there are local changes, conflicts, risky untracked files, no upstream branch, or non-fast-forward history, do not run `stash`, `reset`, force checkout, or overwrite local state. Analyze against the fetched `origin/main` or relevant remote refs instead.
- In the output document `Evidence` section, record the sync result: local HEAD, remote baseline used, and why the local worktree was not updated if applicable.

### Step 2: Fetch Issue Details

```bash
gh issue view <issue_number> --repo ZhuLinsen/daily_stock_analysis
gh issue view <issue_number> --repo ZhuLinsen/daily_stock_analysis --comments
```

For bugs, first check whether the issue template provides:

- Whether the reporter is on the latest version.
- Commit hash or version baseline.
- Runtime environment and reproduction steps.
- Logs or error messages.

### Step 3: Answer Four Core Questions

1. Is the version baseline clear?
2. Is the problem real and verifiable?
3. Is it within this repository's responsibility boundary?
4. Is it worth handling now?

### Step 4: Check Evidence Against The Repository

- Read the relevant code, configuration, tests, scripts, workflows, and docs.
- If the issue touches API, data-source fallback, report generation, notification delivery, auth, desktop, or release flow, state the impact surface.
- Judge whether it is an actual bug, environment/configuration problem, usage problem, or external dependency problem.
- If it may already be fixed, inspect current code instead of relying only on the issue description.

### Step 5: Form A Conclusion

Include at least these fields:

- `Version baseline`: latest / not latest / not provided.
- `Reasonable`: yes/no plus rationale.
- `Is issue`: yes/no plus rationale.
- `Easy to solve`: yes/no plus difficulty.
- `Conclusion`: valid / partially valid / invalid.
- `Category`: bug / feature / docs / question / external.
- `Priority`: P0 / P1 / P2 / P3.
- `Difficulty`: easy / medium / hard.
- `Recommended action`: fix now / schedule fix / clarify docs / close.

### Step 6: Generate The Analysis Document

Save it to `.claude/reviews/issues/issue-<number>.md`.

## Output Document Format

```markdown
# Issue #<number> Analysis

**Date**: YYYY-MM-DD
**Status**: Pending Review

## Summary

- Version baseline:
- Reasonable:
- Is issue:
- Easy to solve:
- Conclusion:
- Category:
- Priority:
- Difficulty:
- Recommended action:

## Evidence

- Code sync baseline:
- Key issue information:
- Key code/script/workflow evidence:

## Impact Scope

- Affected modules:
- Affected runtime paths (local / Docker / GitHub Actions / API / Web / Desktop):

## Root Cause / Main Reasoning

<Root cause or main reasoning>

## Proposed Handling

<Recommended fix, clarification, or closure path>

If a follow-up PR is recommended, suggest a PR title that follows `AGENTS.md`: use `<type>: <change summary>`, do not add `[codex]`, `codex`, `autocode`, `copilot`, or another tool/agent source prefix. This convention is for collaboration consistency only and should not be treated as a standalone review blocker.

## Risks And Rollback

- Risks:
- Rollback path if fixed:

## Draft Reply

<Suggested reply>
```

## Allowed Auto-Actions (No Confirmation Needed)

- Fetch issue details and comments.
- Run `git fetch --all --prune`, and run `git pull --ff-only` only when the worktree is clean and fast-forwardable.
- Read related code, configuration, scripts, workflows, and docs.
- Generate the analysis document.

## Actions Requiring Confirmation

Ask the user before doing any of these:

1. Add or modify labels.
2. Comment on the issue.
3. Close the issue.
4. Start fixing the issue.