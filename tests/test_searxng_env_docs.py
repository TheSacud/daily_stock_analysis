from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_env_example_documents_searxng_actions_variable_mapping() -> None:
    env_example = (ROOT_DIR / ".env.example").read_text(encoding="utf-8")

    start = env_example.index("# SearXNG \u5b9e\u4f8b\u5730\u5740")
    end = env_example.index("SEARXNG_PUBLIC_INSTANCES_ENABLED=true", start)
    searxng_block = env_example[start:end]

    assert "GitHub Actions" in searxng_block
    assert "Variables \u4f18\u5148" in searxng_block
    assert "Secrets" in searxng_block
    assert "\u9700\u914d\u7f6e\u4e3a Secret" not in searxng_block


def test_daily_analysis_workflow_matches_documented_searxng_variable_mapping() -> None:
    workflow = (
        ROOT_DIR / ".github" / "workflows" / "00-daily-analysis.yml"
    ).read_text(encoding="utf-8")

    assert (
        "SEARXNG_BASE_URLS: ${{ vars.SEARXNG_BASE_URLS || secrets.SEARXNG_BASE_URLS }}"
        in workflow
    )
    assert "SEARXNG_BASE_URLS: ${{ secrets.SEARXNG_BASE_URLS }}" not in workflow


def test_changelog_mentions_searxng_actions_variable_mapping() -> None:
    changelog = (ROOT_DIR / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert (
        "- [\u4fee\u590d] GitHub Actions \u6bcf\u65e5\u5206\u6790\u5de5\u4f5c\u6d41\u8bfb\u53d6 SearXNG \u81ea\u5efa\u5b9e\u4f8b\u5730\u5740\u65f6"
        "\u652f\u6301 Variables \u4f18\u5148、Secrets \u56de\u9000，\u4fee\u590d\u4ec5\u914d\u7f6e Variables \u65f6 URL \u4e0d\u751f\u6548\u7684\u95ee\u9898。"
    ) in changelog
