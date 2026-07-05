# -*- coding: utf-8 -*-
"""Tests for Issue #1386 P5 phase decision guardrails."""

from types import SimpleNamespace

from src.analyzer import AnalysisResult
from src.phase_decision_guardrail import apply_phase_decision_guardrails


def _result(**kwargs) -> AnalysisResult:
    defaults = {
        "code": "600519",
        "name": "\u8d35\u5dde\u8305\u53f0",
        "trend_prediction": "\u770b\u591a",
        "sentiment_score": 76,
        "operation_advice": "\u7acb\u5373\u4e70\u5165",
        "decision_type": "buy",
        "confidence_level": "\u9ad8",
        "analysis_summary": "\u76d8\u4e2d\u504f\u5f3a",
        "dashboard": {
            "core_conclusion": {"one_sentence": "\u7acb\u5373\u4e70\u5165"},
            "phase_decision": {
                "action_window": "\u76d8\u4e2d\u8ddf\u8e2a",
                "immediate_action": "\u7acb\u5373\u4e70\u5165",
                "watch_conditions": ["\u653e\u91cf\u7a81\u7834"],
                "next_check_time": "14:30",
                "confidence_reason": "\u8d8b\u52bf\u504f\u5f3a",
                "data_limitations": [],
            },
        },
    }
    defaults.update(kwargs)
    return AnalysisResult(**defaults)


def _phase(phase: str = "intraday") -> dict:
    return {
        "phase": phase,
        "market": "cn",
        "market_local_time": "2026-06-02T10:30:00+08:00",
        "is_trading_day": True,
        "is_market_open_now": phase == "intraday",
        "is_partial_bar": phase in {"intraday", "lunch_break", "closing_auction"},
        "warnings": ["calendar_unavailable"],
    }


def _overview(status: str = "stale") -> dict:
    return {
        "subject": {"code": "600519", "stock_name": "\u8d35\u5dde\u8305\u53f0", "market": "cn"},
        "blocks": [
            {
                "key": "quote",
                "label": "\u884c\u60c5",
                "status": status,
                "source": "tencent",
                "warnings": [],
                "missing_reasons": [],
            },
            {
                "key": "daily_bars",
                "label": "\u65e5\u7ebf",
                "status": "available",
                "source": "akshare",
                "warnings": [],
                "missing_reasons": [],
            },
            {
                "key": "technical",
                "label": "\u6280\u672f",
                "status": "available",
                "source": "local",
                "warnings": [],
                "missing_reasons": [],
            },
        ],
        "data_quality": {
            "overall_score": 65,
            "level": "limited",
            "limitations": ["quote: stale"],
        },
    }


def test_degraded_core_data_caps_high_confidence_buy() -> None:
    result = _result()

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("intraday"),
        analysis_context_pack_overview=_overview("stale"),
        report_language="zh",
    )

    assert "confidence_capped_core_data_degraded" in adjustments
    assert result.confidence_level == "\u4e2d"
    pd = result.dashboard["phase_decision"]
    assert pd["phase_context"]["phase"] == "intraday"
    assert "quote: stale" in pd["data_limitations"]
    assert "\u6838\u5fc3\u884c\u60c5" in pd["confidence_reason"]


def test_degraded_core_data_caps_high_confidence_hold_advice() -> None:
    result = _result(
        operation_advice="\u6682\u4e0d\u52a0\u4ed3，\u89c2\u671b",
        decision_type="hold",
        confidence_level="\u9ad8",
        dashboard={
            "core_conclusion": {"one_sentence": "\u6682\u4e0d\u52a0\u4ed3，\u89c2\u671b"},
            "phase_decision": {
                "action_window": "\u76d8\u4e2d\u8ddf\u8e2a",
                "immediate_action": "\u6682\u4e0d\u52a0\u4ed3，\u89c2\u671b",
                "watch_conditions": ["\u653e\u91cf\u7a81\u7834"],
                "next_check_time": "14:30",
                "confidence_reason": "\u8d8b\u52bf\u672a\u786e\u8ba4",
                "data_limitations": [],
            },
        },
    )

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("intraday"),
        analysis_context_pack_overview=_overview("stale"),
        report_language="zh",
    )

    assert "confidence_capped_core_data_degraded" in adjustments
    assert result.confidence_level == "\u4e2d"
    assert "\u6838\u5fc3\u884c\u60c5" in result.dashboard["phase_decision"]["confidence_reason"]
    assert "quote: stale" in result.dashboard["phase_decision"]["data_limitations"]


def test_premarket_high_confidence_immediate_action_is_conservative() -> None:
    result = _result()

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("premarket"),
        analysis_context_pack_overview=_overview("available"),
        report_language="zh",
    )

    assert "confidence_capped_non_intraday_action" in adjustments
    assert result.confidence_level == "\u4f4e"
    assert result.dashboard["phase_decision"]["immediate_action"] == "\u7b49\u5f85\u76d8\u4e2d\u786e\u8ba4，\u7981\u6b62\u8ffd\u9ad8。"


def test_premarket_medium_confidence_immediate_action_rewrites_action_only() -> None:
    result = _result(
        operation_advice="Hold unless confirmed",
        decision_type="hold",
        confidence_level="Medium",
        report_language="en",
        dashboard={
            "core_conclusion": {"one_sentence": "Wait"},
            "phase_decision": {
                "action_window": "Premarket plan",
                "immediate_action": "buy now",
                "watch_conditions": ["breakout with volume"],
                "next_check_time": "market open",
                "confidence_reason": "Setup is forming",
                "data_limitations": [],
            },
        },
    )

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("premarket"),
        analysis_context_pack_overview=_overview("available"),
        report_language="en",
    )

    assert "non_intraday_action_adjusted" in adjustments
    assert "confidence_capped_non_intraday_action" not in adjustments
    assert result.confidence_level == "Medium"
    assert result.dashboard["phase_decision"]["immediate_action"] == (
        "Wait for intraday confirmation; do not chase."
    )
    assert "buy now" not in result.dashboard["phase_decision"]["immediate_action"].lower()


def test_unknown_low_confidence_immediate_action_rewrites_action_only() -> None:
    result = _result(
        operation_advice="\u89c2\u5bdf\u4e3a\u4e3b",
        decision_type="hold",
        confidence_level="\u4f4e",
        dashboard={
            "core_conclusion": {"one_sentence": "\u89c2\u5bdf\u4e3a\u4e3b"},
            "phase_decision": {
                "action_window": "\u672a\u77e5\u9636\u6bb5\u89c2\u5bdf",
                "immediate_action": "\u7acb\u5373\u4e70\u5165",
                "watch_conditions": ["\u786e\u8ba4\u5f00\u5e02\u72b6\u6001"],
                "next_check_time": "\u9636\u6bb5\u786e\u8ba4\u540e",
                "confidence_reason": "\u9636\u6bb5\u672a\u77e5",
                "data_limitations": [],
            },
        },
    )

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("unknown"),
        analysis_context_pack_overview=_overview("available"),
        report_language="zh",
    )

    assert "non_intraday_action_adjusted" in adjustments
    assert "confidence_capped_non_intraday_action" not in adjustments
    assert result.confidence_level == "\u4f4e"
    assert result.dashboard["phase_decision"]["immediate_action"] == "\u7b49\u5f85\u76d8\u4e2d\u786e\u8ba4，\u7981\u6b62\u8ffd\u9ad8。"


def test_premarket_degraded_immediate_action_uses_strongest_cap() -> None:
    result = _result()

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("premarket"),
        analysis_context_pack_overview=_overview("stale"),
        report_language="zh",
    )

    assert "confidence_capped_core_data_degraded" in adjustments
    assert "confidence_capped_non_intraday_action" in adjustments
    assert result.confidence_level == "\u4f4e"
    assert result.dashboard["phase_decision"]["immediate_action"] == "\u7b49\u5f85\u76d8\u4e2d\u786e\u8ba4，\u7981\u6b62\u8ffd\u9ad8。"


def test_intraday_postmarket_recap_wording_is_adjusted_in_zh_and_en() -> None:
    zh_result = _result(
        operation_advice="\u4eca\u65e5\u6536\u76d8\u540e\u590d\u76d8\u663e\u793a\u53ef\u4e70\u5165",
        analysis_summary="\u660e\u65e5\u91cd\u70b9\u5173\u6ce8\u7a81\u7834",
        dashboard={
            "core_conclusion": {"one_sentence": "\u4eca\u65e5\u6536\u76d8\u540e\u590d\u76d8\u663e\u793a\u504f\u5f3a"},
            "phase_decision": {"immediate_action": "\u660e\u65e5\u91cd\u70b9\u5173\u6ce8\u7a81\u7834", "watch_conditions": []},
        },
    )

    zh_adjustments = apply_phase_decision_guardrails(
        zh_result,
        market_phase_summary=_phase("intraday"),
        analysis_context_pack_overview=_overview("available"),
        report_language="zh",
    )

    assert "postmarket_recap_wording_adjusted" in zh_adjustments
    assert "\u4eca\u65e5\u6536\u76d8\u540e" not in zh_result.dashboard["core_conclusion"]["one_sentence"]
    assert "\u660e\u65e5\u91cd\u70b9" not in zh_result.analysis_summary

    en_result = _result(
        operation_advice="Buy after today's close",
        analysis_summary="Focus tomorrow on the breakout",
        confidence_level="High",
        report_language="en",
        dashboard={
            "core_conclusion": {"one_sentence": "After today's close, buy"},
            "phase_decision": {"immediate_action": "focus tomorrow", "watch_conditions": []},
        },
    )

    en_adjustments = apply_phase_decision_guardrails(
        en_result,
        market_phase_summary=_phase("intraday"),
        analysis_context_pack_overview=_overview("available"),
        report_language="en",
    )

    assert "postmarket_recap_wording_adjusted" in en_adjustments
    assert "after today's close" not in en_result.dashboard["core_conclusion"]["one_sentence"].lower()
    assert "focus tomorrow" not in en_result.analysis_summary.lower()


def test_postmarket_recap_and_missing_inputs_are_fail_open() -> None:
    postmarket = _result(
        operation_advice="\u4eca\u65e5\u6536\u76d8\u540e\u590d\u76d8\u663e\u793a\u53ef\u6301\u6709",
        dashboard={
            "core_conclusion": {"one_sentence": "\u4eca\u65e5\u6536\u76d8\u540e\u590d\u76d8\u663e\u793a\u53ef\u6301\u6709"},
            "phase_decision": {"watch_conditions": ["\u4e0d\u7834\u652f\u6491"]},
        },
    )

    adjustments = apply_phase_decision_guardrails(
        postmarket,
        market_phase_summary=_phase("postmarket"),
        analysis_context_pack_overview=None,
        report_language="zh",
    )

    assert adjustments == []
    assert "\u4eca\u65e5\u6536\u76d8\u540e" in postmarket.dashboard["core_conclusion"]["one_sentence"]
    assert postmarket.dashboard["phase_decision"]["watch_conditions"] == ["\u4e0d\u7834\u652f\u6491"]

    missing = _result(dashboard={})
    adjustments = apply_phase_decision_guardrails(
        missing,
        market_phase_summary=None,
        analysis_context_pack_overview=None,
        report_language="zh",
    )

    assert adjustments == []
    assert missing.dashboard["phase_decision"]["watch_conditions"] == []
    assert missing.dashboard["phase_decision"]["data_limitations"] == []


def test_guardrail_creates_dashboard_for_agent_compatible_result_object() -> None:
    result = SimpleNamespace(
        confidence_level="\u9ad8",
        decision_type="hold",
        operation_advice="\u6301\u6709",
        analysis_summary="\u6d4b\u8bd5\u6458\u8981",
    )

    adjustments = apply_phase_decision_guardrails(
        result,
        market_phase_summary=_phase("intraday"),
        analysis_context_pack_overview=_overview("available"),
        report_language="zh",
    )

    assert adjustments == []
    assert result.dashboard["phase_decision"]["phase_context"]["phase"] == "intraday"
    assert result.dashboard["phase_decision"]["watch_conditions"] == []
