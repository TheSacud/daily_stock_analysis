# -*- coding: utf-8 -*-
"""Tests for structure-aware decision stability calibration."""

from types import SimpleNamespace

from src.analyzer import AnalysisResult, _capital_flow_bias, stabilize_decision_with_structure


def _result(
    *,
    decision_type: str,
    operation_advice: str,
    score: int,
    current_price: float,
    change_pct: float = 0.0,
) -> AnalysisResult:
    return AnalysisResult(
        code="002812",
        name="\u6069\u6377\u80a1\u4efd",
        sentiment_score=score,
        trend_prediction="\u770b\u591a" if decision_type == "buy" else "\u770b\u7a7a",
        operation_advice=operation_advice,
        decision_type=decision_type,
        report_language="zh",
        current_price=current_price,
        change_pct=change_pct,
        dashboard={
            "core_conclusion": {"one_sentence": "\u539f\u59cb\u7ed3\u8bba"},
            "data_perspective": {
                "price_position": {
                    "current_price": current_price,
                    "support_level": 30.0,
                    "resistance_level": 34.0,
                }
            },
        },
    )


def _fund_flow(main: float, five_day: float = 0.0, ten_day: float = 0.0) -> dict:
    return {
        "capital_flow": {
            "status": "ok",
            "data": {
                "stock_flow": {
                    "main_net_inflow": main,
                    "inflow_5d": five_day,
                    "inflow_10d": ten_day,
                }
            },
        }
    }


def _unsupported_fund_flow() -> dict:
    return {"capital_flow": {"status": "not_supported", "data": {}}}


def _unsupported_fund_flow_caps() -> dict:
    return {"capital_flow": {"status": "NOT_SUPPORTED", "data": {"stock_flow": {"main_net_inflow": 0}}}}


def test_capital_flow_bias_is_unavailable_when_stock_flow_data_is_missing() -> None:
    assert _capital_flow_bias(_unsupported_fund_flow()) == "unavailable"
    assert _capital_flow_bias({"capital_flow": {"status": "ok", "data": {}}}) == "unavailable"


def test_capital_flow_bias_is_neutral_when_missing_main_windows_conflict() -> None:
    context = {
        "capital_flow": {
            "data": {
                "stock_flow": {
                    "inflow_5d": 2_000_000,
                    "inflow_10d": -1_000_000,
                }
            }
        }
    }

    assert _capital_flow_bias(context) == "neutral"


def test_capital_flow_bias_is_neutral_when_main_conflicts_with_windows() -> None:
    context = _fund_flow(main=-500_000, five_day=1_200_000, ten_day=2_000_000)

    assert _capital_flow_bias(context) == "neutral"


def test_downgrades_buy_near_resistance_without_fund_confirmation() -> None:
    result = _result(
        decision_type="buy",
        operation_advice="\u4e70\u5165",
        score=65,
        current_price=33.4,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=-1_000_000, five_day=-2_000_000),
    )

    assert result.decision_type == "hold"
    assert result.sentiment_score <= 59
    assert result.operation_advice == "\u9707\u8361\u89c2\u671b"
    assert result.dashboard["decision_stability"]["applied"] is True
    assert "\u4e0d\u5b9c\u4ec5\u56e0\u77ed\u7ebf\u53cd\u5f39\u8ffd\u4e70" in result.risk_warning
    assert result.dashboard["core_conclusion"]["signal_type"] == "🟡\u6301\u6709\u89c2\u671b"


def test_downgrades_buy_mid_range_with_neutral_fund_flow() -> None:
    result = _result(
        decision_type="buy",
        operation_advice="\u4e70\u5165",
        score=66,
        current_price=32.0,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=0, five_day=0, ten_day=0),
    )

    assert result.decision_type == "hold"
    assert result.sentiment_score <= 59
    assert result.operation_advice == "\u9707\u8361\u89c2\u671b"
    assert "\u8d44\u91d1\u6d41\u4e0d\u660e\u786e" in result.risk_warning


def test_downgrades_buy_when_capital_flow_is_unavailable() -> None:
    buy_result = _result(
        decision_type="buy",
        operation_advice="\u4e70\u5165",
        score=66,
        current_price=32.0,
    )
    sell_result = _result(
        decision_type="sell",
        operation_advice="\u5356\u51fa",
        score=30,
        current_price=30.4,
        change_pct=-2.1,
    )

    stabilize_decision_with_structure(
        buy_result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _unsupported_fund_flow(),
    )
    stabilize_decision_with_structure(
        sell_result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _unsupported_fund_flow(),
    )

    assert buy_result.decision_type == "hold"
    assert buy_result.operation_advice == "\u6301\u6709\u89c2\u5bdf"
    assert buy_result.confidence_level == "\u4f4e"
    assert buy_result.sentiment_score <= 59
    assert buy_result.dashboard["decision_stability"]["applied"] is True
    assert "\u4e70\u5165\u7ed3\u8bba\u7f3a\u5c11\u8d44\u91d1\u9762\u786e\u8ba4" in buy_result.dashboard["decision_stability"]["reason"]
    assert buy_result.dashboard["core_conclusion"]["signal_type"] == "🟡\u6301\u6709\u89c2\u671b"
    assert sell_result.decision_type == "sell"
    assert sell_result.operation_advice == "\u5356\u51fa"
    assert sell_result.dashboard["decision_stability"]["applied"] is False
    assert "\u672a\u4f7f\u7528\u8d44\u91d1\u6d41\u6821\u51c6" in sell_result.dashboard["decision_stability"]["reason"]


def test_downgrades_buy_when_capital_flow_values_are_na() -> None:
    result = _result(
        decision_type="buy",
        operation_advice="\u4e70\u5165",
        score=66,
        current_price=33.0,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        {
            "capital_flow": {
                "status": "ok",
                "data": {
                    "stock_flow": {
                        "main_net_inflow": "N/A",
                        "inflow_5d": "N/A",
                        "inflow_10d": "N/A",
                    }
                },
            }
        },
    )

    assert result.decision_type == "hold"
    assert result.operation_advice == "\u6301\u6709\u89c2\u5bdf"
    assert result.dashboard["decision_stability"]["applied"] is True
    assert "\u8d44\u91d1\u6d41\u6570\u636e\u7f3a\u5931" in result.dashboard["decision_stability"]["capital_flow_status"]


def test_downgrades_buy_advice_when_decision_type_is_hold_and_capital_flow_unavailable() -> None:
    result = _result(
        decision_type="hold",
        operation_advice="\u5efa\u8bae\u4e70\u5165",
        score=68,
        current_price=32.0,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _unsupported_fund_flow(),
    )

    assert result.decision_type == "hold"
    assert result.operation_advice == "\u6301\u6709\u89c2\u5bdf"
    assert result.sentiment_score <= 59
    assert result.dashboard["decision_stability"]["applied"] is True
    assert "\u4e70\u5165\u7ed3\u8bba\u7f3a\u5c11\u8d44\u91d1\u9762\u786e\u8ba4" in result.dashboard["decision_stability"]["reason"]


def test_downgrades_buy_when_capital_flow_status_is_unavailable_case_insensitive() -> None:
    buy_result = _result(
        decision_type="buy",
        operation_advice="\u4e70\u5165",
        score=66,
        current_price=32.0,
    )

    stabilize_decision_with_structure(
        buy_result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _unsupported_fund_flow_caps(),
    )

    assert buy_result.decision_type == "hold"
    assert buy_result.operation_advice == "\u6301\u6709\u89c2\u5bdf"
    assert buy_result.dashboard["decision_stability"]["applied"] is True
    assert "\u6682\u4e0d\u652f\u6301" in str(buy_result.dashboard["decision_stability"]["capital_flow_status"])


def test_skips_downgrade_when_only_generic_risk_warning_and_sell_near_support() -> None:
    result = _result(
        decision_type="sell",
        operation_advice="\u5356\u51fa",
        score=30,
        current_price=30.4,
        change_pct=1.0,
    )
    result.risk_warning = "\u6ce8\u610f\u5e38\u89c1\u56de\u64a4\u98ce\u9669，\u5efa\u8bae\u5173\u6ce8\u4ed3\u4f4d。"

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=500_000, five_day=300_000),
    )

    assert result.decision_type == "hold"
    assert result.operation_advice == "\u6d17\u76d8\u89c2\u5bdf"
    assert "\u4ef7\u683c\u8d34\u8fd1\u652f\u6491\u4e14\u672a\u89c1\u8d44\u91d1\u6301\u7eed\u6d41\u51fa" in result.risk_warning


def test_stability_can_infer_decision_from_natural_chinese_phrases_in_analyzer_path() -> None:
    result = _result(
        decision_type="\u5efa\u8bae\u5356\u51fa",
        operation_advice="\u5efa\u8bae\u5356\u51fa",
        score=30,
        current_price=30.4,
        change_pct=1.0,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=500_000, five_day=300_000),
    )

    assert result.decision_type == "hold"
    assert result.operation_advice == "\u6d17\u76d8\u89c2\u5bdf"
    assert result.dashboard["decision_stability"]["applied"] is True


def test_downgrades_sell_near_support_without_sustained_outflow() -> None:
    result = _result(
        decision_type="sell",
        operation_advice="\u5356\u51fa",
        score=30,
        current_price=30.4,
        change_pct=-2.1,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=800_000, five_day=1_200_000),
    )

    assert result.decision_type == "hold"
    assert result.sentiment_score >= 45
    assert result.operation_advice == "\u6d17\u76d8\u89c2\u5bdf"
    assert "\u4e0d\u5b9c\u4ec5\u56e0\u5355\u65e5\u4e0b\u8dcc\u76f4\u63a5\u5356\u51fa" in result.risk_warning


def test_preserves_sell_signal_when_significant_risk_exists_near_support() -> None:
    result = _result(
        decision_type="sell",
        operation_advice="\u5356\u51fa",
        score=30,
        current_price=30.4,
        change_pct=-2.1,
    )
    result.risk_warning = "\u91cd\u5927\u5229\u7a7a\u6d88\u606f：\u516c\u53f8\u53d1\u5e03\u91cd\u5927\u51cf\u6301\u8ba1\u5212"
    result.dashboard["intelligence"] = {"risk_alerts": ["\u80a1\u4e1c\u9ad8\u4f4d\u51cf\u6301\u9884\u544a"]}

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=800_000, five_day=1_200_000),
    )

    assert result.decision_type == "sell"
    assert result.operation_advice == "\u5356\u51fa"


def test_refines_hold_pullback_near_support_as_shakeout_watch() -> None:
    result = _result(
        decision_type="hold",
        operation_advice="\u6301\u6709",
        score=52,
        current_price=30.5,
        change_pct=-1.6,
    )

    stabilize_decision_with_structure(
        result,
        SimpleNamespace(support_levels=[30.0], resistance_levels=[34.0]),
        _fund_flow(main=0, five_day=500_000),
    )

    assert result.decision_type == "hold"
    assert result.operation_advice == "\u6d17\u76d8\u89c2\u5bdf"
    assert "\u66f4\u9002\u5408\u6309\u6d17\u76d8\u89c2\u5bdf\u5904\u7406" in result.risk_warning
