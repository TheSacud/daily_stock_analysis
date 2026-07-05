# Repository Claude Skills

This directory stores repository-level collaboration skills and is part of the versioned repository assets.

- Rule source of truth: root `AGENTS.md`.
- Compatibility entry point: root `CLAUDE.md`, which should be a symlink to `AGENTS.md`.
- Skills in this directory must stay aligned with `AGENTS.md`.
- `.claude/reviews/` contains local analysis artifacts and is not a rule source of truth.

If another agent directory is added later, such as `.agents/skills/` or `.github/skills/`, define the single source of truth first and then synchronize through scripts or mirrors instead of hand-maintaining multiple equivalent copies.