# -*- coding: utf-8 -*-
"""Tests for #1389 P3 AnalysisContextPack prompt summaries."""

from __future__ import annotations

from src.analysis_context_pack_prompt import format_analysis_context_pack_prompt_section
from src.schemas.analysis_context_pack import (
    AnalysisContextBlock,
    AnalysisContextItem,
    AnalysisContextPack,
    AnalysisSubject,
    ContextFieldStatus,
    DataQuality,
)
from src.services.analysis_context_builder import (
    AnalysisContextBuilder,
    PipelineAnalysisArtifacts,
)


def _pack() -> AnalysisContextPack:
    return AnalysisContextPack(
        subject=AnalysisSubject(code="600519", stock_name="\u8d35\u5dde\u8305\u53f0", market="cn"),
        blocks={
            "quote": AnalysisContextBlock(
                status=ContextFieldStatus.FALLBACK,
                source="fallback",
                warnings=["realtime_provider_fallback"],
                items={
                    "price": AnalysisContextItem(
                        status=ContextFieldStatus.FALLBACK,
                        value=1880.0,
                        source="fallback",
                        fallback_from="primary_realtime_provider",
                    )
                },
            ),
            "technical": AnalysisContextBlock(
                status=ContextFieldStatus.PARTIAL,
                warnings=["intraday_realtime_overlay"],
                items={
                    "trend_result": AnalysisContextItem(
                        status=ContextFieldStatus.AVAILABLE,
                        value={"trend_status": "\u591a\u5934\u6392\u5217", "ma5": 1800.0},
                    ),
                    "intraday_overlay": AnalysisContextItem(
                        status=ContextFieldStatus.ESTIMATED,
                        value={"close": 1880.0},
                    ),
                },
            ),
            "news": AnalysisContextBlock(
                status=ContextFieldStatus.MISSING,
                items={
                    "content": AnalysisContextItem(
                        status=ContextFieldStatus.MISSING,
                        value="\u5b8c\u6574\u65b0\u95fb\u6b63\u6587\u4e0d\u5e94\u8fdb\u5165\u6458\u8981",
                        missing_reason="news_context_missing",
                    )
                },
            ),
            "fundamentals": AnalysisContextBlock(
                status=ContextFieldStatus.AVAILABLE,
                metadata={
                    "coverage": {
                        "valuation": "ok",
                        "access_token": "secret-token",
                    }
                },
                items={
                    "coverage": AnalysisContextItem(
                        status=ContextFieldStatus.AVAILABLE,
                        value={"valuation": "ok", "access_token": "secret-token"},
                    )
                },
            ),
        },
        data_quality=DataQuality(
            overall_score=76,
            level="usable",
            block_scores={
                "quote": 65,
                "daily_bars": 100,
                "technical": 75,
                "news": 35,
                "fundamentals": 100,
                "chip": 100,
            },
            limitations=["quote: fallback", "technical: partial"],
            warnings=["intraday_realtime_overlay"],
        ),
        metadata={
            "query_id": "q-1",
            "trigger_source": "api",
            "news_result_count": 3,
            "webhook_url": "https://hooks.example.test/secret",
        },
    )


def _pack_with_phase(phase: str) -> AnalysisContextPack:
    return _pack().model_copy(
        update={"phase": {"phase": phase, "is_partial_bar": phase != "premarket"}}
    )


def _core_available_pack(*, phase: str) -> AnalysisContextPack:
    return AnalysisContextPack(
        subject=AnalysisSubject(code="600519", stock_name="\u8d35\u5dde\u8305\u53f0", market="cn"),
        phase={"phase": phase, "is_partial_bar": False},
        blocks={
            "quote": AnalysisContextBlock(status=ContextFieldStatus.AVAILABLE),
            "daily_bars": AnalysisContextBlock(status=ContextFieldStatus.AVAILABLE),
            "technical": AnalysisContextBlock(status=ContextFieldStatus.AVAILABLE),
            "news": AnalysisContextBlock(status=ContextFieldStatus.AVAILABLE),
            "fundamentals": AnalysisContextBlock(status=ContextFieldStatus.AVAILABLE),
            "chip": AnalysisContextBlock(status=ContextFieldStatus.AVAILABLE),
        },
        data_quality=DataQuality(
            overall_score=100,
            level="good",
            block_scores={
                "quote": 100,
                "daily_bars": 100,
                "technical": 100,
                "news": 100,
                "fundamentals": 100,
                "chip": 100,
            },
            limitations=[],
        ),
    )


def _builder_artifacts(*, fundamental_context: dict) -> PipelineAnalysisArtifacts:
    return PipelineAnalysisArtifacts(
        code="600519",
        stock_name="\u8d35\u5dde\u8305\u53f0",
        market="cn",
        phase=None,
        base_context={
            "today": {"close": 1880.0},
            "yesterday": {"close": 1870.0},
            "date": "2026-03-26",
        },
        enhanced_context={},
        realtime_quote={"price": 1880.0, "source": "mock_quote"},
        trend_result={"trend_status": "available"},
        chip_data={"source": "mock_chip", "date": "2026-03-26"},
        fundamental_context=fundamental_context,
        news_context="\u65b0\u95fb\u6458\u8981",
        news_result_count=1,
        metadata={"trigger_source": "api"},
    )


def test_empty_or_invalid_pack_returns_empty_section() -> None:
    assert format_analysis_context_pack_prompt_section(None) == ""
    assert format_analysis_context_pack_prompt_section({}) == ""
    assert format_analysis_context_pack_prompt_section("not-pack") == ""


def test_chinese_summary_renders_low_sensitivity_pack_statuses() -> None:
    section = format_analysis_context_pack_prompt_section(_pack())

    assert "\u5206\u6790\u4e0a\u4e0b\u6587\u5305\u6458\u8981" in section
    assert "600519" in section
    assert "\u8d35\u5dde\u8305\u53f0" in section
    assert "\u884c\u60c5: fallback" in section
    assert "\u6280\u672f: partial" in section
    assert "\u544a\u8b66=realtime_provider_fallback" in section
    assert "\u65b0\u95fb: missing" in section
    assert "news_context_missing" in section
    assert "\u65b0\u95fb\u7ed3\u679c\u6570：3" in section
    assert "intraday_realtime_overlay" in section
    assert "\u6570\u636e\u9650\u5236" in section
    assert "\u6570\u636e\u8d28\u91cf\u8bc4\u5206：76/100（\u53ef\u7528）" in section
    assert "\u5df2\u77e5\u9650\u5236：\u884c\u60c5：\u964d\u7ea7、\u6280\u672f：\u90e8\u5206\u53ef\u7528" in section
    assert "confidence_level \u4e0d\u5f97\u4e3a\u9ad8" in section
    assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" not in section


def test_english_summary_renders_readable_statuses() -> None:
    section = format_analysis_context_pack_prompt_section(
        _pack(),
        report_language="en",
    )

    assert "Analysis Context Pack Summary" in section
    assert "Subject: 600519 (\u8d35\u5dde\u8305\u53f0)" in section
    assert "quote: fallback" in section
    assert "news: missing" in section
    assert "News result count: 3" in section
    assert "Data Limitations" in section
    assert "Data quality score: 76/100 (usable)" in section
    assert "Known limitations: quote: fallback, technical: partial" in section
    assert "confidence_level must not be High" in section
    assert "Phase/data rule" not in section


def test_intraday_phase_degraded_core_adds_phase_data_quality_guard() -> None:
    section = format_analysis_context_pack_prompt_section(_pack_with_phase("intraday"))

    assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" in section
    assert "\u76d8\u4e2d\u5224\u65ad\u53d7" in section
    assert "\u6570\u636e\u8d28\u91cf\u9650\u5236" in section
    assert "confidence_level \u4e0d\u5f97\u4e3a\u9ad8" in section
    assert "\u5f53\u524d\u4e0d\u662f\u76d8\u540e\u590d\u76d8" not in section


def test_intraday_phase_data_quality_guard_renders_in_english() -> None:
    section = format_analysis_context_pack_prompt_section(
        _pack_with_phase("intraday"),
        report_language="en",
    )

    assert "Phase/data rule" in section
    assert "intraday judgment is limited" in section
    assert "data quality" in section
    assert "confidence_level must not be High" in section
    assert "This is not a post-market recap" not in section


def test_lunch_break_and_closing_auction_degraded_core_add_data_guard_only() -> None:
    for phase in ("lunch_break", "closing_auction"):
        section = format_analysis_context_pack_prompt_section(_pack_with_phase(phase))

        assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" in section
        assert "\u76d8\u4e2d\u5224\u65ad\u53d7" in section
        assert "\u5f53\u524d\u4e0d\u662f\u76d8\u540e\u590d\u76d8" not in section


def test_premarket_degraded_quote_limits_opening_plan_without_phase_repetition() -> None:
    section = format_analysis_context_pack_prompt_section(_pack_with_phase("premarket"))

    assert "\u5f00\u76d8\u8ba1\u5212\u53d7\u6570\u636e\u65b0\u9c9c\u5ea6\u6216\u964d\u7ea7\u72b6\u6001\u9650\u5236" in section
    assert "\u4e0d\u5f97\u628a\u964d\u7ea7\u884c\u60c5\u63cf\u8ff0\u6210\u4eca\u65e5\u8d70\u52bf\u5df2\u7ecf\u53d1\u751f" in section
    assert "\u5f53\u524d\u5c1a\u672a\u5f00\u76d8" not in section


def test_non_trading_and_unknown_degraded_core_are_conservative() -> None:
    for phase in ("non_trading", "unknown"):
        section = format_analysis_context_pack_prompt_section(_pack_with_phase(phase))

        assert "\u53ea\u80fd\u4fdd\u5b88\u4f7f\u7528\u5f53\u524d\u53ef\u7528\u6570\u636e" in section
        assert "\u4e0d\u5f97\u8865\u5168\u4e0d\u5b58\u5728\u7684\u76d8\u4e2d\u4e8b\u5b9e" in section


def test_phase_cross_guard_is_skipped_for_postmarket_invalid_or_non_dict_phase() -> None:
    postmarket_degraded = format_analysis_context_pack_prompt_section(
        _pack_with_phase("postmarket")
    )
    postmarket_available = format_analysis_context_pack_prompt_section(
        _core_available_pack(phase="postmarket")
    )
    invalid = format_analysis_context_pack_prompt_section(
        _pack().model_copy(update={"phase": {"phase": "not_a_phase"}})
    )
    non_dict = _pack().model_dump(mode="json")
    non_dict["phase"] = "intraday"
    non_dict_section = format_analysis_context_pack_prompt_section(non_dict)

    assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" not in postmarket_degraded
    assert "\u76d8\u4e2d\u5224\u65ad\u53d7" not in postmarket_degraded
    assert "confidence_level \u4e0d\u5f97\u4e3a\u9ad8" in postmarket_degraded
    assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" not in postmarket_available
    assert "\u76d8\u4e2d\u5224\u65ad\u53d7" not in postmarket_available
    assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" not in invalid
    assert "confidence_level \u4e0d\u5f97\u4e3a\u9ad8" in invalid
    assert "\u9636\u6bb5\u6570\u636e\u89c4\u5219" not in non_dict_section
    assert "confidence_level \u4e0d\u5f97\u4e3a\u9ad8" in non_dict_section


def test_summary_does_not_dump_values_or_sensitive_payloads() -> None:
    section = format_analysis_context_pack_prompt_section(_pack())

    assert "analysis_context_pack" not in section
    assert "\u5b8c\u6574\u65b0\u95fb\u6b63\u6587\u4e0d\u5e94\u8fdb\u5165\u6458\u8981" not in section
    assert "\u591a\u5934\u6392\u5217" not in section
    assert "secret-token" not in section
    assert "hooks.example.test" not in section
    assert "webhook_url" not in section
    assert "access_token" not in section
    assert "N/A" not in section
    assert "None" not in section


def test_builder_to_prompt_renders_aux_fetch_failed_without_confidence_cap() -> None:
    pack = AnalysisContextBuilder.build(
        _builder_artifacts(
            fundamental_context={
                "status": "failed",
                "coverage": {"valuation": "failed"},
                "source_chain": [
                    {"provider": "fundamental_pipeline", "result": "failed"}
                ],
            }
        )
    )

    section = format_analysis_context_pack_prompt_section(pack)

    assert pack.data_quality.limitations == ["fundamentals: fetch_failed"]
    assert "\u6570\u636e\u9650\u5236" in section
    assert "\u6570\u636e\u8d28\u91cf\u8bc4\u5206：92/100（\u826f\u597d）" in section
    assert "\u5df2\u77e5\u9650\u5236：\u57fa\u672c\u9762：\u6293\u53d6\u5931\u8d25" in section
    assert "\u7f6e\u4fe1\u5ea6\u89c4\u5219" not in section
    assert "confidence_level" not in section
