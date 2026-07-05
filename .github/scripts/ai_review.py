#!/usr/bin/env python3
"""
AI code review script used by GitHub Actions PR Review workflow.
"""
import json
import os
import subprocess
import traceback


MAX_DIFF_LENGTH = 18000
REVIEW_PATHS = [
    '*.py',
    '*.md',
    'README.md',
    'AGENTS.md',
    'docs/**',
    '.github/PULL_REQUEST_TEMPLATE.md',
    'requirements.txt',
    '.github/requirements-ci.txt',
    'pyproject.toml',
    'setup.cfg',
    '.github/workflows/*.yml',
    '.github/scripts/*.py',
    'apps/dsa-web/**',
]


def run_git(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"warning: git command failed: {' '.join(args)}")
        print(result.stderr.strip())
        return ''
    return result.stdout.strip()


def get_diff():
    """Get PR diff content for review-relevant files."""
    base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
    diff = run_git(['git', 'diff', f'origin/{base_ref}...HEAD', '--', *REVIEW_PATHS])
    truncated = len(diff) > MAX_DIFF_LENGTH
    return diff[:MAX_DIFF_LENGTH], truncated


def get_changed_files():
    """Get changed file list for review-relevant files."""
    base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
    output = run_git(['git', 'diff', '--name-only', f'origin/{base_ref}...HEAD', '--', *REVIEW_PATHS])
    return output.split('\n') if output else []


def get_pr_context():
    """Read PR title/body from GitHub event payload when available."""
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path or not os.path.exists(event_path):
        return '', ''
    try:
        with open(event_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        pr = payload.get('pull_request', {})
        return (pr.get('title') or '').strip(), (pr.get('body') or '').strip()
    except Exception:
        return '', ''


def classify_files(files):
    py_files = [f for f in files if f.endswith('.py')]
    doc_files = [f for f in files if f.endswith('.md') or f.startswith('docs/') or f in ('README.md', 'AGENTS.md')]
    frontend_files = [f for f in files if f.startswith('apps/dsa-web/') or f.endswith(('.tsx', '.ts'))]
    ci_files = [f for f in files if f.startswith('.github/workflows/')]
    config_files = [
        f for f in files if f in ('requirements.txt', '.github/requirements-ci.txt', 'pyproject.toml', 'setup.cfg', '.github/PULL_REQUEST_TEMPLATE.md')
    ]
    return py_files, doc_files, frontend_files, ci_files, config_files


def _build_ci_context():
    """Build CI context section from environment variables set by the workflow."""
    auto_check_result = os.environ.get('CI_AUTO_CHECK_RESULT', '')
    syntax_ok = os.environ.get('CI_SYNTAX_OK', '')
    has_py = os.environ.get('CI_HAS_PY_CHANGES', 'false')

    if not auto_check_result:
        return """
## CI Check Status
> Warning: CI check results were not available. Do not assume CI passed; mark validation-related conclusions as unable to confirm.
"""

    lines = ["\n## CI Check Status (from this PR automation run)"]
    lines.append(f"- Static check overall result: **{'pass' if auto_check_result == 'success' else 'fail'}**")
    if has_py == 'true':
        lines.append(f"- Python syntax check (py_compile): **{'pass' if syntax_ok == 'true' else 'fail' if syntax_ok == 'false' else 'not run'}**")
        lines.append("- Flake8 fatal error check (E9/F63/F7/F82): **pass** if the overall static check passed")
    else:
        lines.append("- Python files: no changes; syntax check skipped")
    lines.append("")
    lines.append("> This CI section only covers syntax correctness (py_compile) and fatal lint errors (flake8 E9/F63/F7/F82). `./scripts/ci_gate.sh` is not included in this PR review job. For Python backend changes, if the PR description does not state whether that gate was run or why it was skipped, mention it as a suggestion, not a blocker. If syntax/flake8 passed here, do not ask for duplicate local syntax output.")
    lines.append("")
    return '\n'.join(lines)


def build_prompt(diff_content, files, truncated, pr_title, pr_body):
    """Build AI review prompt aligned with AGENTS.md requirements."""
    truncate_notice = ''
    if truncated:
        truncate_notice = "\n\n> Warning: the diff is long and has been truncated. Review the visible content and mark uncertain points.\n"

    py_files, doc_files, frontend_files, ci_files, config_files = classify_files(files)
    ci_context = _build_ci_context()
    return f"""You are this repository's PR review assistant. Review code, docs, and CI evidence together based on the diff and PR description.

## PR Information
- Title: {pr_title or '(empty)'}
- Description:
{pr_body or '(empty)'}

## Changed File Summary
- Python: {len(py_files)}
- Docs/Markdown: {len(doc_files)}
- Frontend (apps/dsa-web): {len(frontend_files)}
- CI Workflow: {len(ci_files)}
- Config/Template: {len(config_files)}

Changed files:
{', '.join(files)}{truncate_notice}

## Code Changes (diff)
```diff
{diff_content}
```
{ci_context}
## Required Review Rules (from repository AGENTS.md)
1. Necessity: does the PR solve a clear problem or deliver clear value, without pointless refactoring?
2. Traceability: is there a linked issue (Fixes/Refs)? Natural-language links such as "related issue #xxx" are acceptable; do not fail only for format. If there is no issue, is motivation and acceptance criteria provided?
3. Type: does the PR type match fix/feat/refactor/docs/chore/test?
4. Description completeness: does it include background, scope, verification commands/results, compatibility risk, and rollback plan? When judging validation, use the CI Check Status above: (a) if py_compile and flake8 passed, the PR may cite CI instead of pasting duplicate local output; (b) `./scripts/ci_gate.sh` is not covered by this CI job, so for Python backend changes, check whether the PR says if that gate ran or why it was skipped; if missing, list it as a suggestion; (c) if CI results are missing, do not assume CI passed and mark validation as unable to confirm.
5. Merge readiness: return Ready to Merge or Not Ready and list blockers.
6. If user-visible capability changed, check whether README.md and docs/CHANGELOG.md were updated appropriately.

## Blocker vs Suggestion Rules
Only these can make the PR Not Ready:
- Correctness or security issue in code, such as logic errors, swallowed exceptions, or vulnerabilities.
- CI checks failed.
- Material contradiction between PR description and actual diff.
- Missing rollback plan.

These belong in suggestions and should not block merge by themselves:
- Non-standard issue-link formatting.
- Missing syntax/flake8 validation evidence when CI Check Status shows py_compile and flake8 both passed.
- Python backend changes whose PR description does not state whether `./scripts/ci_gate.sh` ran or why it was skipped.
- Non-critical wording or formatting issues in the description.
- Comment language style or unrelated lockfile churn.

## Review Output Requirements
- Use English.
- Start with Conclusion: `Ready to Merge` or `Not Ready`.
- Then provide structured results:
  - Necessity: pass/fail + reason.
  - Traceability: pass/fail + evidence.
  - Type: suggested type.
  - Description completeness: complete/incomplete + missing items.
  - Risk level: low/medium/high + key risk.
  - Must-fix items: at most 5, blockers only, in priority order.
  - Suggestions: at most 5.
- Must-fix items must only include blocker-rule issues. Put formatting, traceability, and non-blocking validation-evidence gaps in suggestions.
- For findings, include file paths where possible and explain impact.
- If information is insufficient, write "Unable to confirm from the current diff/PR description.".
"""


def review_with_gemini(prompt):
    """Run review with Gemini API."""
    api_key = os.environ.get('GEMINI_API_KEY')
    model = os.environ.get('GEMINI_MODEL') or os.environ.get('GEMINI_MODEL_FALLBACK') or 'gemini-2.5-flash'

    if not api_key:
        print("Gemini API key is not configured. Check GitHub Secrets: GEMINI_API_KEY")
        return None

    print(f"Using model: {model}")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        print(f"Gemini ({model}) review succeeded")
        return response.text
    except ImportError as e:
        print(f"Gemini dependency is not installed: {e}")
        print("   Install google-genai: pip install google-genai")
        return None
    except Exception as e:
        print(f"Gemini review failed: {e}")
        traceback.print_exc()
        return None


def review_with_openai(prompt):
    """Run review with OpenAI-compatible API as fallback."""
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    if not api_key:
        print("OpenAI API key is not configured. Check GitHub Secrets: OPENAI_API_KEY")
        return None

    print(f"Base URL: {base_url}")
    print(f"Using model: {model}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        print(f"OpenAI-compatible review ({model}) succeeded")
        return response.choices[0].message.content
    except ImportError as e:
        print(f"OpenAI dependency is not installed: {e}")
        print("   Install openai: pip install openai")
        return None
    except Exception as e:
        print(f"OpenAI-compatible review failed: {e}")
        traceback.print_exc()
        return None


def ai_review(diff_content, files, truncated):
    """Run AI review: Gemini first, then OpenAI fallback."""
    pr_title, pr_body = get_pr_context()
    prompt = build_prompt(diff_content, files, truncated, pr_title, pr_body)

    result = review_with_gemini(prompt)
    if result:
        return result

    print("Trying OpenAI-compatible API...")
    result = review_with_openai(prompt)
    if result:
        return result

    return None


def main():
    diff, truncated = get_diff()
    files = get_changed_files()

    if not diff or not files:
        print("No reviewable code/docs/config changes; skipping AI review")
        summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write("## AI Code Review\n\nNo reviewable changes\n")
        return

    print(f"Review files: {files}")
    if truncated:
        print(f"Diff content was truncated to {MAX_DIFF_LENGTH} characters")

    review = ai_review(diff, files, truncated)

    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')

    strict_mode = os.environ.get('AI_REVIEW_STRICT', 'false').lower() == 'true'

    if review:
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write(f"## AI Code Review\n\n{review}\n")

        with open('ai_review_result.txt', 'w', encoding='utf-8') as f:
            f.write(review)

        print("AI review complete")
    else:
        print("All AI interfaces are unavailable")
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write("## AI Code Review\n\nAI interface unavailable; check configuration\n")
        if strict_mode:
            raise SystemExit("AI_REVIEW_STRICT=true and no AI review result is available")


if __name__ == '__main__':
    main()