# -*- coding: utf-8 -*-
"""Contract checks for the AnalysisContextPack P0/P1 contract doc."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "analysis-context-pack.md"
FULL_GUIDE_PATH = PROJECT_ROOT / "docs" / "full-guide.md"
FULL_GUIDE_EN_PATH = PROJECT_ROOT / "docs" / "full-guide_EN.md"


def _read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _section(doc: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in doc
    return doc.split(marker, 1)[1].split("\n## ", 1)[0]


def test_analysis_context_pack_doc_has_required_sections() -> None:
    doc = _read_doc()

    for heading in (
        "## \u672f\u8bed\u4e0e\u8fb9\u754c",
        "## P0 \u8303\u56f4\u4e0e\u975e\u76ee\u6807",
        "## P1 \u5185\u90e8\u5951\u7ea6",
        "## P2 Builder \u5951\u7ea6",
        "## P3 Runtime Consumption",
        "## P4 \u5386\u53f2\u8bb0\u5f55、\u4efb\u52a1\u72b6\u6001\u4e0e Web \u53ef\u89c1\u6027",
        "## P5 \u6570\u636e\u8d28\u91cf\u8bc4\u5206\u4e0e Prompt \u6570\u636e\u9650\u5236",
        "## P6 \u6587\u6863、\u8fc1\u79fb\u4e0e\u56de\u6eda",
        "## \u5b57\u6bb5\u8d28\u91cf\u72b6\u6001",
        "## \u73b0\u6709\u72b6\u6001\u6620\u5c04",
        "## \u4e03\u8def\u5f84\u76d8\u70b9",
        "## \u6e90\u7801\u951a\u70b9",
        "## \u517c\u5bb9\u4e0e\u5b89\u5168\u8fb9\u754c",
    ):
        assert heading in doc


def test_analysis_context_pack_doc_disambiguates_context_surfaces() -> None:
    section = _section(_read_doc(), "\u672f\u8bed\u4e0e\u8fb9\u754c")

    for token in (
        "`storage.get_analysis_context()`",
        "`enhanced_context`",
        "`analysis_history.context_snapshot`",
        "Agent executor message context",
        "Agent orchestrator `AgentContext`",
        "`AGENT_ARCH=single`",
        "`AGENT_ARCH=multi`",
    ):
        assert token in section


def test_analysis_context_pack_doc_defines_p0_quality_states() -> None:
    section = _section(_read_doc(), "\u5b57\u6bb5\u8d28\u91cf\u72b6\u6001")

    for state in (
        "`available`",
        "`missing`",
        "`not_supported`",
        "`fallback`",
        "`stale`",
        "`estimated`",
        "`partial`",
        "`fetch_failed`",
    ):
        assert state in section
    assert "P0 \u5148\u56fa\u5b9a\u4e03\u8bcd" in section
    assert "P5 \u5728\u540c\u4e00 1.0 umbrella \u5185\u8ffd\u52a0 `fetch_failed`" in section


def test_analysis_context_pack_doc_covers_seven_paths() -> None:
    section = _section(_read_doc(), "\u4e03\u8def\u5f84\u76d8\u70b9")

    for heading in (
        "### \u666e\u901a\u5206\u6790",
        "### Agent",
        "### \u544a\u8b66",
        "### \u6301\u4ed3",
        "### \u56de\u6d4b",
        "### \u5386\u53f2",
        "### \u901a\u77e5",
    ):
        assert heading in section


def test_analysis_context_pack_doc_records_agent_context_visibility() -> None:
    section = _section(_read_doc(), "\u4e03\u8def\u5f84\u76d8\u70b9")

    for token in (
        "`initial_context`",
        "`fundamental_context`",
        "\u4e0d\u663e\u5f0f\u6ce8\u5165 `fundamental_context` \u6216 `trend_result`",
        "pre-fetched data",
        "\u4e0d\u9884\u6ce8\u5165 `fundamental_context`",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_non_goals_and_safety_boundaries() -> None:
    doc = _read_doc()

    for token in (
        "P1 \u5df2\u65b0\u589e `AnalysisContextPack` \u5185\u90e8 schema",
        "\u4e0d\u65b0\u589e builder",
        "\u4e0d\u63a5\u5165 runtime",
        "\u4e0d\u516c\u5f00\u5b8c\u6574 pack",
        "\u4e0d pack \u5316 `market_review`",
        "`market_light`",
        "P5 \u5df2\u5728\u540c\u4e00 1.0 umbrella \u5185\u8ffd\u52a0\u8be5\u72b6\u6001",
        "`analysis_history.context_snapshot.enhanced_context.date`",
        "\u5b8c\u6574 pack \u4e0d\u9ed8\u8ba4\u516c\u5f00",
        "API key",
        "token",
        "cookie",
        "\u5b8c\u6574 webhook URL",
        "\u90ae\u7bb1\u5bc6\u7801",
    ):
        assert token in doc


def test_analysis_context_pack_doc_defines_p1_schema_contract() -> None:
    section = _section(_read_doc(), "P1 \u5185\u90e8\u5951\u7ea6")

    for token in (
        "`src/schemas/analysis_context_pack.py`",
        "`PACK_VERSION = \"1.0\"`",
        "`ContextFieldStatus`",
        "`AnalysisSubject`",
        "`AnalysisContextItem`",
        "`AnalysisContextBlock`",
        "`DataQuality`",
        "`AnalysisContextPack`",
        "`MarketPhaseContext.to_dict()`",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_p1_block_catalog() -> None:
    section = _section(_read_doc(), "P1 \u5185\u90e8\u5951\u7ea6")

    for token in (
        "P1 Block Catalog",
        "`quote`",
        "`daily_bars`",
        "`technical`",
        "`fundamentals`",
        "`news`",
        "`portfolio`",
        "`chip` / `capital_flow`",
        "`events` / `market_context`",
        "\u4e0d\u91cd\u590d\u65b0\u589e `identity` block",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_p1_time_and_status_semantics() -> None:
    section = _section(_read_doc(), "P1 \u5185\u90e8\u5951\u7ea6")

    for token in (
        "`AnalysisContextPack.created_at` \u4f7f\u7528 `datetime`",
        "`model_dump(mode=\"json\")` \u8f93\u51fa ISO 8601",
        "`AnalysisContextItem.timestamp`",
        "`AnalysisContextBlock.timestamp`",
        "Optional[str]",
        "\u6784\u9020\u65f6\u6821\u9a8c",
        "date-only",
        "`block.status` \u8868\u793a\u6574\u5757\u53ef\u7528\u6027",
        "`item.status` \u8868\u793a\u5b57\u6bb5\u7ea7\u8d28\u91cf",
        "\u4e0d\u5b9e\u73b0 `item.status` \u5230 `block.status` \u7684\u81ea\u52a8\u805a\u5408\u63a8\u5bfc",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_p1_redaction_contract() -> None:
    section = _section(_read_doc(), "P1 \u5185\u90e8\u5951\u7ea6")

    for token in (
        "`AnalysisContextPack.to_safe_dict()`",
        "`redact_sensitive_mapping()`",
        "`api_key`",
        "`access_token`",
        "`authorization_header`",
        "`webhook_url`",
        "`license_key`",
        "[REDACTED]",
        "`data_api`",
        "\u4e0d\u626b\u63cf\u666e\u901a\u5b57\u7b26\u4e32\u503c",
        "\u4e0d\u505a URL \u6b63\u5219\u8131\u654f",
    ):
        assert token in section


def test_analysis_context_pack_doc_keeps_later_phases_out_of_p1() -> None:
    section = _section(_read_doc(), "P1 \u5185\u90e8\u5951\u7ea6")

    for token in (
        "\u4e0d\u586b\u5145\u8fd0\u884c\u65f6\u6570\u636e",
        "\u4e0d\u65b0\u589e fetcher",
        "\u4e0d\u6539\u53d8 Prompt",
        "\u4e0d\u5199\u5165 history/task/report metadata",
        "\u4e0d\u628a\u5b8c\u6574 pack \u66b4\u9732\u5230 API、Web、Bot、Desktop \u6216\u901a\u77e5",
        "P2 builder",
        "P3 runtime",
    ):
        assert token in section


def test_analysis_context_pack_doc_defines_p2_builder_boundaries() -> None:
    section = _section(_read_doc(), "P2 Builder \u5951\u7ea6")

    for token in (
        "`AnalysisContextBuilder`",
        "assembler",
        "pipeline \u5df2 fetch",
        "zero-fetch",
        "`PipelineAnalysisArtifacts`",
        "`code`、`stock_name`、`market`",
        "`price_stale`",
        "`quote_stale`",
        "`intraday_realtime_overlay`",
        "`fetch_failed`",
        "P3 runtime",
        "\u4e0d\u6539\u53d8 Prompt",
        "\u4e0d\u5199\u5165 history/task/report metadata",
    ):
        assert token in section


def test_analysis_context_pack_docs_record_issue_1386_p3_quality_boundaries() -> None:
    section = _section(_read_doc(), "P2 Builder \u5951\u7ea6")

    for token in (
        "`fetched_at`",
        "`provider_timestamp`",
        "`is_stale`",
        "`stale_seconds`",
        "`fallback_from`",
        "`STALE > FALLBACK > AVAILABLE`",
        "builder \u53ea\u6620\u5c04\u4e0a\u6e38 artifact，\u4e0d\u505a\u8d28\u91cf\u8bc4\u5206",
        "`is_partial_bar`、`is_estimated`、`estimated_fields`",
        "`daily_bars` \u4e0d\u627f\u8f7d partial/estimated",
    ):
        assert token in section

    full_guide = FULL_GUIDE_PATH.read_text(encoding="utf-8")
    full_guide_en = FULL_GUIDE_EN_PATH.read_text(encoding="utf-8")
    assert "\u76d8\u4e2d\u6570\u636e\u5305\u4e0e\u5b9e\u65f6\u8d28\u91cf\u63a7\u5236（Issue #1386 P3）" in full_guide
    assert "source` \u4fdd\u7559\u5b9e\u9645\u6210\u529f\u7684\u6570\u636e\u6e90 token" in full_guide
    assert "`AnalysisContextBuilder` \u53ea\u6620\u5c04\u8fd9\u4e9b\u4e0a\u6e38 artifact" in full_guide
    assert "daily_bars` block \u4ecd\u8868\u793a storage \u4e2d\u5b8c\u6574\u65e5\u7ebf\u7a97\u53e3" in full_guide
    assert "Intraday Data Packet and Realtime Quality Control (Issue #1386 P3)" in full_guide_en
    assert "source` keeps the actual successful provider token" in full_guide_en


def test_analysis_context_pack_doc_defines_p3_runtime_consumption_boundaries() -> None:
    section = _section(_read_doc(), "P3 Runtime Consumption")

    for token in (
        "`StockAnalysisPipeline` \u662f summary \u7684\u552f\u4e00\u751f\u4ea7\u8005",
        "`PipelineAnalysisArtifacts` -> `AnalysisContextBuilder.build()`",
        "`format_analysis_context_pack_prompt_section()`",
        "`analysis_context_pack_summary`",
        "\u57fa\u7840\u4fe1\u606f -> #1386 `market_phase_context` \u6e32\u67d3\u533a\u5757 -> `analysis_context_pack_summary`",
        "`news.content`、`trend_result`、`chip`、`fundamental_context` \u7b49\u539f\u59cb payload",
        "`AgentExecutor._build_user_message()`",
        "`AgentOrchestrator._build_context()`",
        "`ctx.meta[\"analysis_context_pack_summary\"]`",
        "\u7981\u6b62\u5199\u5165 `ctx.data`",
        "`BaseAgent._build_messages()`",
        "`_inject_cached_data()`",
        "`news` block \u4e3a `missing` \u662f\u5f53\u524d P3 \u7684\u9884\u671f\u72b6\u6001",
        "`analysis_history.context_snapshot`",
        "`analysis_context_pack`",
        "`analysis_context_pack_summary`",
        "Agent \u5de5\u5177\u7ea7 pack cache \u590d\u7528",
        "P4 \u5728\u6b64\u57fa\u7840\u4e0a\u65b0\u589e\u4f4e\u654f overview",
        "P5 \u7ee7\u7eed\u590d\u7528 summary \u6d88\u8d39\u8def\u5f84",
    ):
        assert token in section

    assert "P3-min" not in section


def test_analysis_context_pack_doc_defines_p4_visibility_contract() -> None:
    section = _section(_read_doc(), "P4 \u5386\u53f2\u8bb0\u5f55、\u4efb\u52a1\u72b6\u6001\u4e0e Web \u53ef\u89c1\u6027")

    for token in (
        "`analysis_context_pack_overview`",
        "\u4e13\u7528 renderer",
        "`AnalysisContextPack.to_safe_dict()`",
        "`report.details.analysis_context_pack_overview`",
        "`analysisContextPackOverview`",
        "`GET /api/v1/history/{record_id}`",
        "\u540c\u6b65 `POST /api/v1/analysis/analyze`",
        "overview \u4f9d\u8d56\u5df2\u6301\u4e45\u5316\u7684 `analysis_history.context_snapshot`",
        "completed `GET /api/v1/analysis/status/{task_id}`",
        "`sanitize_context_snapshot_for_api()`",
        "`extract_analysis_context_pack_overview()`",
        "`items.value`",
        "`trend_result`",
        "`fundamental_context`",
        "`SAVE_CONTEXT_SNAPSHOT=false`",
        "\u4e0d\u6301\u4e45\u5316\u6574\u4efd `analysis_history.context_snapshot`",
        "`market_phase_summary`",
        "`enhanced_context`",
        "`AnalysisContextSummary`",
        "\u4f4d\u7f6e\u5728\u7b56\u7565\u70b9\u4f4d\u548c\u8d44\u8baf\u4e4b\u540e、\u8fd0\u884c\u8bca\u65ad\u4e4b\u524d",
        "\u9ed8\u8ba4\u6298\u53e0",
        "\u975e\u96f6\u7684\u5176\u4ed6\u72b6\u6001\u8ba1\u6570",
        "\u4e0d\u8986\u76d6 pending/processing TaskPanel",
        "\u4e0d\u6539\u901a\u77e5\u6458\u8981",
        "\u8d28\u91cf\u5206/\u7b49\u7ea7",
        "`fetch_failed` \u72b6\u6001",
    ):
        assert token in section

    assert "\u8fd0\u884c\u8bca\u65ad\u4e4b\u540e、\u7b56\u7565\u70b9\u4f4d\u4e4b\u524d" not in section


def test_analysis_context_pack_doc_defines_p5_data_quality_contract() -> None:
    section = _section(_read_doc(), "P5 \u6570\u636e\u8d28\u91cf\u8bc4\u5206\u4e0e Prompt \u6570\u636e\u9650\u5236")

    for token in (
        "`PACK_VERSION`",
        "`fetch_failed`",
        "`fundamental_context.status == \"failed\"`",
        "`overall_score`",
        "`level`",
        "`block_scores`",
        "`limitations`",
        "`quote=25`",
        "`fetch_failed=25`",
        "`Data Limitations`",
        "`confidence_level` \u4e0d\u5f97\u4e3a `\u9ad8` / `High`",
        "`phase × degraded data`",
        "fail-open",
        "\u4e0d\u66ff\u4ee3 P5 \u7684 confidence/safety \u89c4\u5219",
        "`analysis_context_pack_overview.data_quality`",
        "`details.context_snapshot`",
        "\u4e0d\u65b0\u589e fetcher",
        "\u4e0d\u6539\u53d8 LLM \u8f93\u51fa JSON schema",
        "`dashboard.phase_decision`",
    ):
        assert token in section


def test_analysis_context_pack_doc_defines_p6_migration_and_rollback_contract() -> None:
    section = _section(_read_doc(), "P6 \u6587\u6863、\u8fc1\u79fb\u4e0e\u56de\u6eda")

    for token in (
        "\u56db\u4e2a\u6570\u636e\u9762",
        "\u5185\u90e8\u5b8c\u6574 pack",
        "`analysis_context_pack_summary`",
        "`analysis_context_pack_overview`",
        "`analysis_history.context_snapshot`",
        "\u6458\u8981\u53ef\u89c1\u6027\u77e9\u9635",
        "`SAVE_CONTEXT_SNAPSHOT=true`",
        "`SAVE_CONTEXT_SNAPSHOT=false`",
        "`--no-context-snapshot`",
        "\u4e0d\u6301\u4e45\u5316\u6574\u4efd `analysis_history.context_snapshot`",
        "\u672c\u6b21\u5386\u53f2\u5df2\u6301\u4e45\u5316 `analysis_history.context_snapshot`",
        "`enhanced_context`",
        "`market_phase_summary`",
        "`diagnostics`",
        "`realtime_quote_raw`",
        "\u4e0d\u5f71\u54cd\u5f53\u6b21 `AnalysisContextPack` \u6784\u5efa",
        "\u4e0d\u5f71\u54cd\u5185\u5b58\u4e2d\u7684 `result.diagnostic_context_snapshot`",
        "\u5f53\u524d\u4e0d\u5b58\u5728",
        "\u8fd0\u884c\u65f6 pack \u603b\u5f00\u5173",
        "\u53d1\u5e03\u6216\u4ee3\u7801\u56de\u6eda",
        "secret",
        "token",
        "webhook",
    ):
        assert token in section


def test_analysis_context_pack_doc_maps_existing_status_terms() -> None:
    section = _section(_read_doc(), "\u73b0\u6709\u72b6\u6001\u6620\u5c04")

    for token in (
        "`degraded`",
        "`insufficient_data`",
        "`partial_failed`",
        "`data_missing`",
        "`price_stale`",
        "`data_quality=ok/partial/unavailable`",
        "\u4e0d\u6620\u5c04",
    ):
        assert token in section


def test_analysis_context_pack_doc_lists_source_anchors() -> None:
    section = _section(_read_doc(), "\u6e90\u7801\u951a\u70b9")

    for path in (
        "src/core/pipeline.py",
        "src/storage.py",
        "src/analyzer.py",
        "src/agent/orchestrator.py",
        "src/agent/executor.py",
        "src/agent/tools/data_tools.py",
        "src/services/alert_worker.py",
        "src/services/portfolio_service.py",
        "src/services/backtest_service.py",
        "src/repositories/backtest_repo.py",
        "src/services/history_service.py",
        "api/v1/endpoints/history.py",
        "api/v1/endpoints/analysis.py",
        "api/v1/schemas/history.py",
        "api/v1/schemas/portfolio.py",
        "src/notification.py",
        "docs/alerts.md",
        "docs/notifications.md",
    ):
        assert path in section


def test_analysis_context_pack_doc_updates_indexes_and_changelog() -> None:
    index = (PROJECT_ROOT / "docs" / "INDEX.md").read_text(encoding="utf-8")
    index_en = (PROJECT_ROOT / "docs" / "INDEX_EN.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "[\u5206\u6790\u4e0a\u4e0b\u6587\u5305\u5951\u7ea6、\u8fd0\u884c\u6001\u6d88\u8d39\u4e0e\u53ef\u89c1\u6027](analysis-context-pack.md)" in index
    assert "P1/P2 \u5185\u90e8\u5951\u7ea6、P3 Prompt \u6458\u8981\u6d88\u8d39、P4 \u5386\u53f2/API/Web \u4f4e\u654f\u53ef\u89c1\u6027、P5 \u6570\u636e\u8d28\u91cf\u8bc4\u5206、P6 \u8fc1\u79fb\u56de\u6eda" in index
    assert "#1386 \u9636\u6bb5\u611f\u77e5\u5206\u6790、\u8fc1\u79fb\u4e0e\u56de\u6eda\u5165\u53e3" in index
    assert (
        "[Analysis Context Pack Contract, Runtime Consumption, And Visibility](analysis-context-pack.md) "
        "<sub><sub>![P6 Badge](https://img.shields.io/badge/P6-orange?style=flat)</sub></sub> "
        "(Chinese-only)"
    ) in index_en
    assert "P1/P2 internal contracts, P3 prompt-summary consumption, P4 history/API/Web low-sensitivity visibility, P5 data-quality scoring, and P6 migration/rollback notes" in index_en
    assert "#1386 market-phase analysis, migration, and rollback entry points" in index_en
    assert "\u65b0\u589e AnalysisContextPack P0 \u4e0a\u4e0b\u6587\u76d8\u70b9" in changelog
    assert "\u65b0\u589e AnalysisContextPack P1 \u5185\u90e8\u5951\u7ea6\u4e0e\u8131\u654f\u5e8f\u5217\u5316\u6d4b\u8bd5" in changelog
    assert "\u65b0\u589e AnalysisContextPack P2 builder" in changelog
    assert "\u666e\u901a\u5206\u6790\u4e0e Agent \u8fd0\u884c\u65f6 Prompt \u63a5\u5165 AnalysisContextPack \u4f4e\u654f\u6458\u8981" in changelog
    assert "AnalysisContextPack P4 \u4f4e\u654f overview \u63a5\u5165\u5386\u53f2\u8be6\u60c5" in changelog
    assert "AnalysisContextPack P5 \u589e\u52a0\u6570\u636e\u8d28\u91cf\u8bc4\u5206" in changelog
    assert "\u660e\u786e AnalysisContextPack P6 \u6587\u6863、\u8fc1\u79fb\u4e0e\u56de\u6eda\u8fb9\u754c" in changelog
    assert "#1386 P7 \u76d8\u524d/\u76d8\u4e2d/\u76d8\u540e\u5206\u6790\u7684\u5165\u53e3、\u8fc1\u79fb、\u56de\u6eda\u548c\u7528\u6237\u53ef\u89c1\u8bf4\u660e" in changelog
    assert "#1386 P5 \u4e3a\u4e2a\u80a1\u5206\u6790\u62a5\u544a\u65b0\u589e `dashboard.phase_decision`" in changelog
    assert "\u4f18\u5316 Web \u62a5\u544a\u8be6\u60c5\u9875\u4fe1\u606f\u5c42\u7ea7" in changelog


def test_full_guides_cover_issue_1386_p7_user_migration_closeout() -> None:
    guide = (PROJECT_ROOT / "docs" / "full-guide.md").read_text(encoding="utf-8")
    guide_en = (PROJECT_ROOT / "docs" / "full-guide_EN.md").read_text(encoding="utf-8")

    for token in (
        "\u6587\u6863、\u914d\u7f6e\u4e0e\u8fc1\u79fb\u8bf4\u660e（Issue #1386 P7）",
        "\u76d8\u524d / \u76d8\u4e2d / \u76d8\u540e\u5206\u6790",
        "\u751f\u6210\u5f00\u76d8\u8ba1\u5212\u548c\u89c2\u5bdf\u6761\u4ef6",
        "\u76d8\u4e2d / \u5348\u95f4 / \u4e34\u8fd1\u6536\u76d8",
        "\u505a\u5b9e\u65f6\u72b6\u6001\u5224\u65ad、\u98ce\u9669\u548c\u673a\u4f1a\u63d0\u9192",
        "`analysis_phase=auto|premarket|intraday|postmarket`",
        "\u6700\u7ec8\u62a5\u544a\u9636\u6bb5\u4ecd\u4ee5 `report.meta.market_phase_summary.phase` \u4e3a\u51c6",
        "Web \u4e3b\u5206\u6790 / \u91cd\u65b0\u5206\u6790 / \u6301\u4ed3\u624b\u52a8\u5206\u6790",
        "\u5f53\u524d\u6ca1\u6709\u9636\u6bb5\u8986\u76d6 selector",
        "\u8fdb\u884c\u4e2d\u4efb\u52a1\u9762\u677f\u5c55\u793a\u8bf7\u6c42\u9636\u6bb5",
        "\u6700\u7ec8\u62a5\u544a\u9875\u5c55\u793a\u6700\u7ec8\u9636\u6bb5\u6807\u7b7e",
        "Bot / CLI / schedule / \u9ed8\u8ba4 GitHub Actions",
        "\u53ea\u6d88\u8d39\u516c\u5f00 `market_phase_summary` \u548c\u4f4e\u654f `analysis_context_pack_overview`",
        "\u4e0d\u516c\u5f00\u5b8c\u6574 pack、Prompt summary、\u65b0\u95fb\u6b63\u6587\u6216\u6301\u4ed3\u654f\u611f\u660e\u7ec6",
        "\u65e7\u8c03\u7528\u4e0d\u4f20 `analysis_phase` \u65f6\u4fdd\u6301\u517c\u5bb9",
        "\u56de\u6d4b\u67e5\u8be2\u652f\u6301 `analysis_phase=premarket|intraday|postmarket|unknown`",
        "`SAVE_CONTEXT_SNAPSHOT=false`",
        "\u4e0d\u5173\u95ed\u5f53\u6b21 `AnalysisContextPack` \u6784\u5efa",
        "\u4f4e\u654f `analysis_context_pack_summary`",
        "`analysis_phase=postmarket`",
        "\u9700\u8981\u53d1\u5e03\u56de\u6eda\u6216\u4ee3\u7801\u56de\u6eda",
    ):
        assert token in guide

    for token in (
        "Documentation, Configuration, And Migration Notes (Issue #1386 P7)",
        "pre-market / intraday / post-market analysis",
        "opening plan and watch conditions",
        "Intraday / lunch break / near close",
        "live state, risk, and opportunity alerts",
        "`analysis_phase=auto|premarket|intraday|postmarket`",
        "final report phase remains `report.meta.market_phase_summary.phase`",
        "Web main analysis / re-analysis / portfolio manual analysis",
        "no phase override selector",
        "the in-progress task panel shows the requested phase",
        "the final report page shows the final phase label",
        "Bot / CLI / schedule / default GitHub Actions",
        "Only consume public `market_phase_summary` and low-sensitivity `analysis_context_pack_overview`",
        "do not expose the full pack, prompt summary, news body text, or sensitive portfolio details",
        "Older callers that omit `analysis_phase` remain compatible",
        "Backtest queries support `analysis_phase=premarket|intraday|postmarket|unknown`",
        "`SAVE_CONTEXT_SNAPSHOT=false`",
        "does not disable current-run `AnalysisContextPack` construction",
        "low-sensitivity `analysis_context_pack_summary`",
        "`analysis_phase=postmarket`",
        "requires a release rollback or code rollback",
    ):
        assert token in guide_en


def test_full_guides_clarify_pack_summary_does_not_replace_legacy_payload_channels() -> None:
    guide = (PROJECT_ROOT / "docs" / "full-guide.md").read_text(encoding="utf-8")
    guide_en = (PROJECT_ROOT / "docs" / "full-guide_EN.md").read_text(encoding="utf-8")

    assert "\u5728\u8fd9\u4e2a\u65b0\u589e\u7684 pack \u6458\u8981\u533a\u5757\u4e2d" in guide
    assert "\u4e0d\u4f1a\u901a\u8fc7\u8be5\u533a\u5757\u770b\u5230\u5b8c\u6574 `news.content`" in guide
    assert "\u65e2\u6709 `news_context`、Agent pre-fetched JSON \u548c `enhanced_context` \u539f\u59cb\u6570\u636e\u901a\u9053\u4fdd\u6301 P3 \u524d\u884c\u4e3a" in guide
    assert "`report.details.analysis_context_pack_overview`" in guide
    assert "completed `/api/v1/analysis/status/{task_id}`" in guide
    assert "Web \u7aef\u62a5\u544a\u9875\u5728“\u7b56\u7565\u70b9\u4f4d”\u548c“\u8d44\u8baf”\u4e4b\u540e\u5c55\u793a\u9ed8\u8ba4\u6298\u53e0\u7684\u6570\u636e\u5757\u6458\u8981" in guide
    assert "\u6298\u53e0\u5934\u90e8\u5c55\u793a\u53ef\u7528\u6570、\u7f3a\u5931\u6570、\u975e\u96f6\u7684\u5176\u4ed6\u72b6\u6001\u8ba1\u6570\u548c\u89e6\u53d1\u6765\u6e90" in guide
    assert "Web \u62a5\u544a\u9875\u5728\u7b56\u7565\u70b9\u4f4d\u548c\u8d44\u8baf\u4e4b\u540e\u9ed8\u8ba4\u6298\u53e0\u5c55\u793a\u6570\u636e\u5757\u72b6\u6001" in guide
    assert "`details.context_snapshot` \u4f1a\u5265\u79bb\u9876\u5c42 `analysis_context_pack_overview`" in guide
    assert "\u540c\u6b65\u5206\u6790\u54cd\u5e94\u4e5f\u4f1a\u8bfb\u53d6\u672c\u6b21\u5df2\u843d\u5e93\u7684 `analysis_history.context_snapshot` \u63d0\u53d6 overview" in guide
    assert "`SAVE_CONTEXT_SNAPSHOT=false` \u65f6\u65b0\u8bb0\u5f55\u4e0d\u4fdd\u8bc1\u8fd4\u56de\u8be5\u5b57\u6bb5" in guide
    assert "AnalysisContextPack \u6570\u636e\u8d28\u91cf\u8bc4\u5206\u4e0e Prompt \u6570\u636e\u9650\u5236（Issue #1389 P5）" in guide
    assert "\u76d8\u4e2d\u51b3\u7b56\u62a4\u680f\u4e0e\u8d28\u91cf\u6821\u9a8c（Issue #1386 P5）" in guide
    assert "`dashboard.phase_decision`" in guide
    assert "`fetch_failed`" in guide
    assert "\u6298\u53e0\u5934\u90e8\u65b0\u589e\u8d28\u91cf\u5206/\u7b49\u7ea7" in guide
    assert "`report.meta.market_phase_summary`" in guide
    assert "`details.context_snapshot` \u4f1a\u5265\u79bb\u9876\u5c42 `market_phase_summary`" in guide
    assert "AnalysisContextPack \u6587\u6863、\u8fc1\u79fb\u4e0e\u56de\u6eda（Issue #1389 P6）" in guide
    assert "`SAVE_CONTEXT_SNAPSHOT` \u662f\u65e2\u6709\u73af\u5883\u53d8\u91cf" in guide
    assert "\u4e0d\u6301\u4e45\u5316\u6574\u4efd `analysis_history.context_snapshot`" in guide
    assert "\u4e0d\u5173\u95ed\u5f53\u6b21 `AnalysisContextPack` \u6784\u5efa" in guide
    assert "\u5f53\u524d\u6ca1\u6709\u8fd0\u884c\u65f6 pack \u603b\u5f00\u5173" in guide

    assert "in this new pack-summary section" in guide_en
    assert "not full `news.content`" in guide_en
    assert "Existing `news_context`, Agent pre-fetched JSON, and `enhanced_context` raw-payload channels keep their pre-P3 behavior" in guide_en
    assert "`report.details.analysis_context_pack_overview`" in guide_en
    assert "completed `/api/v1/analysis/status/{task_id}`" in guide_en
    assert "The Web report page renders a collapsed data-block summary after Strategy and News" in guide_en
    assert "available/missing counts, non-zero other status counts, and trigger source" in guide_en
    assert "the Web report page shows the data-block summary collapsed after Strategy and News" in guide_en
    assert "API `details.context_snapshot` strips the top-level `analysis_context_pack_overview`" in guide_en
    assert "sync analysis responses also extract the overview from the just-persisted `analysis_history.context_snapshot`" in guide_en
    assert "new records do not guarantee this field when `SAVE_CONTEXT_SNAPSHOT=false`" in guide_en
    assert "AnalysisContextPack Data Quality Scoring and Prompt Limitations (Issue #1389 P5)" in guide_en
    assert "Intraday Decision Guardrails and Quality Checks (Issue #1386 P5)" in guide_en
    assert "`dashboard.phase_decision`" in guide_en
    assert "`fetch_failed`" in guide_en
    assert "adds quality score/level to the header" in guide_en
    assert "`report.meta.market_phase_summary`" in guide_en
    assert "API `details.context_snapshot` strips the top-level `market_phase_summary`" in guide_en
    assert "AnalysisContextPack Documentation, Migration, and Rollback (Issue #1389 P6)" in guide_en
    assert "`SAVE_CONTEXT_SNAPSHOT` is an existing environment variable" in guide_en
    assert "the full `analysis_history.context_snapshot` is not persisted" in guide_en
    assert "does not disable current-run `AnalysisContextPack` construction" in guide_en
    assert "There is no runtime pack master switch" in guide_en
