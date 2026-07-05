# -*- coding: utf-8 -*-
"""Tests for Issue #1381 daily market context decision guardrail."""

from __future__ import annotations

from src.analyzer import AnalysisResult
from src.daily_market_context_guardrail import apply_daily_market_context_guardrail


def _result() -> AnalysisResult:
    return AnalysisResult(
        code="600519",
        name="\u8d35\u5dde\u8305\u53f0",
        sentiment_score=82,
        trend_prediction="\u770b\u591a",
        operation_advice="\u7acb\u5373\u4e70\u5165\u5e76\u79ef\u6781\u52a0\u4ed3",
        decision_type="buy",
        confidence_level="\u9ad8",
        analysis_summary="\u4e2a\u80a1\u4fe1\u53f7\u5f3a\u52bf",
        dashboard={
            "operation_advice": "\u7acb\u5373\u4e70\u5165\u5e76\u79ef\u6781\u52a0\u4ed3",
            "decision_type": "buy",
            "core_conclusion": {
                "one_sentence": "\u7acb\u5373\u4e70\u5165\u5e76\u79ef\u6781\u52a0\u4ed3",
                "position_advice": {
                    "no_position": "\u7acb\u5373\u4e70\u5165\u5e76\u79ef\u6781\u52a0\u4ed3",
                    "has_position": "\u7ee7\u7eed\u52a0\u4ed3",
                },
            },
            "battle_plan": {
                "position_strategy": {
                    "suggested_position": "\u6ee1\u4ed3\u4e70\u5165",
                    "entry_plan": "\u7a81\u7834\u540e\u7acb\u5373\u4e70\u5165",
                    "risk_control": "\u56de\u8e29\u7ee7\u7eed\u52a0\u4ed3",
                },
            },
            "phase_decision": {
                "data_limitations": [],
                "confidence_reason": "\u8d8b\u52bf\u5f3a",
            },
        },
    )


def test_conservative_market_context_softens_aggressive_buy() -> None:
    result = _result()

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="zh",
    )

    assert "daily_market_context_buy_softened" in adjustments
    assert result.decision_type == "hold"
    assert result.operation_advice == "\u89c2\u671b"
    assert len(result.operation_advice) <= 20
    assert result.confidence_level == "\u4e2d"
    assert result.sentiment_score == 52
    assert result.dashboard["operation_advice"] == result.operation_advice
    assert result.dashboard["decision_type"] == "hold"
    assert result.dashboard["sentiment_score"] == 52
    core = result.dashboard["core_conclusion"]
    assert core["one_sentence"] == result.operation_advice
    assert core["position_advice"] == {
        "no_position": "\u5927\u76d8\u73af\u5883\u504f\u8c28\u614e，\u6682\u4e0d\u5f00\u65b0\u4ed3，\u7b49\u5f85\u98ce\u9669\u7f13\u89e3\u6216\u786e\u8ba4\u4fe1\u53f7。",
        "has_position": "\u4ec5\u4fdd\u7559\u5c0f\u4ed3\u89c2\u5bdf，\u6682\u4e0d\u6269\u5927\u4ed3\u4f4d；\u82e5\u8dcc\u7834\u98ce\u63a7\u4f4d\u4f18\u5148\u964d\u4f4e\u4ed3\u4f4d。",
    }
    position_strategy = result.dashboard["battle_plan"]["position_strategy"]
    assert position_strategy == {
        "suggested_position": "\u5c0f\u4ed3/\u4f4e\u4ed3\u4f4d",
        "entry_plan": "\u5927\u76d8\u73af\u5883\u504f\u8c28\u614e，\u6682\u4e0d\u5f00\u65b0\u4ed3，\u7b49\u5f85\u98ce\u9669\u7f13\u89e3\u6216\u786e\u8ba4\u4fe1\u53f7。",
        "risk_control": "\u5927\u76d8\u98ce\u9669\u672a\u7f13\u89e3\u524d\u4e0d\u6269\u5927\u4ed3\u4f4d，\u4e25\u683c\u63a7\u5236\u56de\u64a4。",
    }
    phase_decision = result.dashboard["phase_decision"]
    assert any("\u5927\u76d8\u73af\u5883" in item for item in phase_decision["data_limitations"])
    assert "\u5927\u76d8\u73af\u5883" in phase_decision["confidence_reason"]


def test_position_cap_only_market_context_softens_aggressive_buy() -> None:
    cases = [
        ("zh", "\u5e02\u573a\u9707\u8361，\u4ed3\u4f4d\u4e0d\u8d85\u8fc730%。", "\u7acb\u5373\u4e70\u5165\u5e76\u79ef\u6781\u52a0\u4ed3", "\u9ad8", "\u89c2\u671b"),
        ("en", "Major indices are mixed. Position limit 30%.", "Buy now and add aggressively.", "High", "Watch"),
    ]
    for language, summary, advice, confidence, expected_advice in cases:
        result = _result()
        result.operation_advice = advice
        result.confidence_level = confidence

        adjustments = apply_daily_market_context_guardrail(
            result,
            daily_market_context={
                "region": "us" if language == "en" else "cn",
                "trade_date": "2026-06-06",
                "summary": summary,
                "risk_tags": [],
                "position_cap": "30%",
            },
            report_language=language,
        )

        assert "daily_market_context_buy_softened" in adjustments
        assert result.decision_type == "hold"
        assert result.operation_advice == expected_advice


def test_neutral_market_context_leaves_hold_unchanged() -> None:
    result = _result()
    result.decision_type = "hold"
    result.operation_advice = "\u6301\u6709\u89c2\u5bdf"
    result.confidence_level = "\u4e2d"

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5e02\u573a\u9707\u8361，\u7ed3\u6784\u5206\u5316。",
            "risk_tags": [],
        },
        report_language="zh",
    )

    assert adjustments == []
    assert result.decision_type == "hold"
    assert result.operation_advice == "\u6301\u6709\u89c2\u5bdf"


def test_conservative_market_context_does_not_soften_negative_buy_language() -> None:
    result = _result()
    result.decision_type = "buy"
    result.operation_advice = "\u6682\u4e0d\u52a0\u4ed3，\u7ee7\u7eed\u6301\u6709\u89c2\u5bdf。"
    result.confidence_level = "\u9ad8"

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="zh",
    )

    assert adjustments == []
    assert result.decision_type == "buy"
    assert result.operation_advice == "\u6682\u4e0d\u52a0\u4ed3，\u7ee7\u7eed\u6301\u6709\u89c2\u5bdf。"


def test_conservative_market_context_does_not_soften_no_action_in_english() -> None:
    result = _result()
    result.decision_type = "hold"
    result.operation_advice = "No add now; keep watching for confirmation."

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "us",
            "trade_date": "2026-06-06",
            "summary": "Market cooling and elevated risk. Cautious on new positions."
        },
        report_language="en",
    )

    assert adjustments == []
    assert result.decision_type == "hold"
    assert result.operation_advice == "No add now; keep watching for confirmation."


def test_conservative_market_context_does_not_soften_explicit_negative_add_position() -> None:
    result = _result()
    result.decision_type = "buy"
    result.operation_advice = "\u4e0d\u5efa\u8bae\u52a0\u4ed3，\u7b49\u5f85\u7a97\u53e3\u66f4\u6e05\u6670。"
    result.confidence_level = "\u9ad8"

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="zh",
    )

    assert adjustments == []
    assert result.decision_type == "buy"
    assert result.operation_advice == "\u4e0d\u5efa\u8bae\u52a0\u4ed3，\u7b49\u5f85\u7a97\u53e3\u66f4\u6e05\u6670。"


def test_conservative_market_context_softens_generic_buy_advice_phrase() -> None:
    result = _result()
    result.operation_advice = "\u56de\u8e29\u4e70\u5165，\u5f3a\u652f\u6491\u4e0a\u653b。"
    result.confidence_level = "\u9ad8"

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="zh",
    )

    assert "daily_market_context_buy_softened" in adjustments
    assert result.decision_type == "hold"
    assert result.operation_advice == "\u89c2\u671b"


def test_conservative_market_context_softens_when_risk_warning_then_recommend_buy() -> None:
    result = _result()
    result.decision_type = "buy"
    result.operation_advice = "\u98ce\u9669\u4e0d\u80fd\u5ffd\u89c6，\u4f46\u5efa\u8bae\u4e70\u5165\u7b49\u5f85\u786e\u8ba4\u4fe1\u53f7。"
    result.confidence_level = "\u9ad8"

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="zh",
    )

    assert "daily_market_context_buy_softened" in adjustments
    assert result.decision_type == "hold"
    assert result.operation_advice == "\u89c2\u671b"


def test_conservative_market_context_softens_when_negated_chase_then_recommend_buy() -> None:
    result = _result()
    result.decision_type = "buy"
    result.operation_advice = "\u4e0d\u5efa\u8bae\u8ffd\u9ad8，\u4f46\u5efa\u8bae\u5206\u6279\u4e70\u5165。"
    result.confidence_level = "\u9ad8"

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="zh",
    )

    assert "daily_market_context_buy_softened" in adjustments
    assert result.decision_type == "hold"
    assert result.operation_advice == "\u89c2\u671b"


def test_conservative_market_context_does_not_soften_buy_when_negated_explicitly_in_english() -> None:
    result = _result()
    result.decision_type = "buy"
    result.operation_advice = "No buy now; avoid adding."

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "cn",
            "trade_date": "2026-06-06",
            "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
            "risk_tags": ["high_risk", "low_position_cap"],
        },
        report_language="en",
    )

    assert adjustments == []
    assert result.decision_type == "buy"
    assert result.operation_advice == "No buy now; avoid adding."


def test_conservative_market_context_does_not_soften_do_not_buy_in_english() -> None:
    result = _result()
    result.decision_type = "buy"
    result.operation_advice = "Do not buy now; sell into strength."

    adjustments = apply_daily_market_context_guardrail(
        result,
        daily_market_context={
            "region": "us",
            "trade_date": "2026-06-06",
            "summary": "Market cooling and elevated risk. Cautious on new positions.",
        },
        report_language="en",
    )

    assert adjustments == []
    assert result.decision_type == "buy"
    assert result.operation_advice == "Do not buy now; sell into strength."
