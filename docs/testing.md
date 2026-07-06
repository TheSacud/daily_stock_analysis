# Testing And PR Handoff Commands

This page is the deterministic command checklist for local workspace validation and PR handoff. Run commands from the repository root unless a command changes directory explicitly.

Do not run these commands against production paths. Do not read or print `.env`, database files, generated `data/`, private state, or raw credentials while collecting evidence.

## Read-Only Diagnosis

Start with read-only workspace checks before installing dependencies or editing files:

```bash
git status --short --branch
find . -maxdepth 3 \( -name package.json -o -name pyproject.toml -o -name AGENTS.md -o -name 'requirements*.txt' -o -name pytest.ini -o -name setup.cfg \) -not -path './.git/*' -not -path './data/*'
```

For PR handoff, also confirm the current branch and remotes without printing credentials:

```bash
git branch --show-current
git remote -v
```

Expected fork workflow:

- `origin` is the Sacud fork and is the only remote workers should push to.
- `upstream` is the original project and is only for fetching original project updates.
- Do not push to `upstream`.

## Install

Backend CI-equivalent install:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r .github/requirements-ci.txt
```

The CI requirements file installs `requirements.txt` plus the backend gate tools `flake8` and `pytest`. For runtime-only manual checks, `python -m pip install -r requirements.txt` is enough, but it is not equivalent to the PR backend gate.

Web install:

```bash
cd apps/dsa-web
npm ci
```

The Web package requires Node `>=20.19.0 <27` and npm `>=10`.

Desktop install:

```bash
cd apps/dsa-desktop
npm ci
```

Use `npm ci` for deterministic workspace validation because `apps/dsa-desktop/package-lock.json` is committed.

## Lint, Unit, And Build Checks

Default backend PR gate:

```bash
./scripts/ci_gate.sh
```

That gate runs Python syntax checks, flake8 critical checks, deterministic local checks, and the offline pytest suite. To isolate a phase:

```bash
./scripts/ci_gate.sh syntax
./scripts/ci_gate.sh flake8
./scripts/ci_gate.sh deterministic
./scripts/ci_gate.sh offline-tests
```

Useful narrower backend commands:

```bash
python -m py_compile <changed_python_files>
python -m pytest -m "not network"
python -m pytest tests/test_specific_file.py
./scripts/test.sh code
./scripts/test.sh yfinance
```

Web gate and unit checks:

```bash
cd apps/dsa-web
npm run lint
npm run test
npm run build
```

CI requires `npm run lint` and `npm run build` when `apps/dsa-web/**` changes. `npm run test` is the local Vitest unit/regression suite and should be run for Web logic changes even though it is not part of the current PR workflow.

Desktop checks:

```bash
cd apps/dsa-desktop
npm test
```

For desktop packaging changes, build the Web app first and then run the Electron build when the backend artifact expected by `apps/dsa-desktop/package.json` is available:

```bash
cd apps/dsa-web
npm ci
npm run build

cd ../dsa-desktop
npm ci
npm run build
```

Known gap: `npm run build` for the desktop package can require platform tooling and the backend bundle at `dist/backend/stock_analysis`. For JavaScript-only desktop changes, `npm test` is the deterministic local check.

## Smoke Checks

Offline deterministic smoke checks:

```bash
./scripts/test.sh code
./scripts/test.sh yfinance
```

Network smoke checks are optional and environment-dependent:

```bash
python -m pytest -m network -q
./scripts/test.sh quick --no-notify
```

Known gap: the scheduled `network-smoke` workflow runs these checks as non-blocking observation only. It may fail because of market data availability, third-party network behavior, or missing provider configuration, and it does not replace the backend gate.

Web Playwright smoke:

```bash
cd apps/dsa-web
DSA_WEB_SMOKE_PASSWORD='<local test password>' npm run test:smoke
```

`apps/dsa-web/playwright.config.ts` only starts the local backend and Vite servers when `DSA_WEB_SMOKE_PASSWORD` is set. Use a disposable local test password and do not put secrets in command logs. If the backend command must be customized, set `DSA_WEB_SMOKE_BACKEND_CMD`.

Desktop manual smoke should be called out in PR evidence when performed. Do not treat `npm run dev` or packaging as a required automated worker check unless the task specifically touches desktop startup or release behavior.

## PR Handoff

Before handoff, collect the actual diff scope:

```bash
BASE_REF=$(git merge-base HEAD origin/sacud/vps)
git diff --stat "$BASE_REF"..HEAD
git diff --name-only "$BASE_REF"..HEAD
git status --short
```

Use `origin/main` instead of `origin/sacud/vps` only when the maintainer explicitly wants a PR against the original mainline target.

PR body evidence should include:

- Changed files and file count from `git diff --name-only`.
- Commands run and pass/fail results.
- CI status links when available.
- Known validation gaps and why they are acceptable.
- Compatibility and risk assessment.
- Rollback path, usually `revert this PR` for docs-only changes.

After review approval and only when pushing/opening PRs is allowed for the current worker, push to the Sacud fork and open a draft PR:

```bash
git push -u origin "$(git branch --show-current)"
gh pr create --draft --base sacud/vps --head "$(git branch --show-current)" --title "<type>: <change summary>" --body-file <pr-body.md>
```

Known PR workflow gaps:

- `.github/workflows/ci.yml` currently runs on pull requests targeting `main`; PRs targeting `sacud/vps` may need local validation evidence or maintainer-triggered checks.
- `docker-build` is a required CI job for `main` PRs, but local Docker validation is not part of the default workspace worker checklist.
- Opening a PR requires GitHub CLI authentication and permission to push to `origin`; if unavailable, hand off the branch, diff, and validation evidence instead of bypassing the repository workflow.
