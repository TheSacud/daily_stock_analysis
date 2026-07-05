# -*- coding: utf-8 -*-
"""Tests for Issue #1390 P0 decision action taxonomy helpers."""

import pytest

from src.schemas.decision_action import (
    build_action_fields,
    localize_action_label,
    normalize_decision_action,
)
from src.schemas.decision_scale import action_for_score, decision_type_for_score, signal_key_for_score


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("strong_buy", "buy"),
        ("\u5f3a\u70c8\u4e70\u5165", "buy"),
        ("\u4e70\u5165", "buy"),
        ("\u5e03\u5c40", "buy"),
        ("\u5efa\u4ed3", "buy"),
        ("add", "add"),
        ("\u52a0\u4ed3", "add"),
        ("\u589e\u6301", "add"),
        ("accumulate", "add"),
        ("hold", "hold"),
        ("\u6301\u6709", "hold"),
        ("\u6301\u6709\u89c2\u5bdf", "hold"),
        ("\u6d17\u76d8\u89c2\u5bdf", "hold"),
        ("watch", "watch"),
        ("\u89c2\u671b", "watch"),
        ("\u7b49\u5f85", "watch"),
        ("wait", "watch"),
        ("reduce", "reduce"),
        ("\u51cf\u4ed3", "reduce"),
        ("trim", "reduce"),
        ("sell", "sell"),
        ("\u5356\u51fa", "sell"),
        ("\u6e05\u4ed3", "sell"),
        ("strong_sell", "sell"),
        ("\u5f3a\u70c8\u5356\u51fa", "sell"),
        ("avoid", "avoid"),
        ("\u56de\u907f", "avoid"),
        ("\u89c4\u907f", "avoid"),
        ("\u4e0d\u5efa\u8bae\u4e70\u5165", "avoid"),
        ("\u907f\u514d\u4e70\u5165", "avoid"),
        ("do not buy", "avoid"),
        ("alert", "alert"),
        ("\u98ce\u9669\u9884\u8b66", "alert"),
        ("\u8b66\u60d5", "alert"),
        ("\u89e6\u53d1\u544a\u8b66", "alert"),
        ("risk alert", "alert"),
    ],
)
def test_normalize_decision_action_matrix(value: str, expected: str) -> None:
    assert normalize_decision_action(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        None,
        "\u89c2\u5bdf",
        "\u7b49\u5f85\u7a81\u7834\u540e\u4e70\u5165",
        "waiting to buy",
        "\u4e70\u5165\u6216\u5356\u51fa",
        "buy or sell",
        "\u4e70\u76d8\u589e\u5f3a，\u7ee7\u7eed\u89c2\u5bdf",
        "\u5356\u538b\u7f13\u89e3，\u7ee7\u7eed\u89c2\u5bdf",
        "\u5356\u65b9\u8bc4\u7ea7\u5206\u6b67",
        "no buyback announced",
        "cannot buyback shares now",
        "share buy-back announced",
        "share buy back announced",
        "no selloff risk",
        "not selloff yet",
        "sell-off risk remains low",
        "sell off risk remains low",
        "no sell-off pressure",
        "risk alert, avoid buying",
        "\u98ce\u9669\u9884\u8b66，\u907f\u514d\u4e70\u5165",
        "\u666e\u901a\u590d\u76d8\u8bf4\u660e",
    ],
)
def test_normalize_decision_action_unknown_or_ambiguous_returns_none(value: str | None) -> None:
    assert normalize_decision_action(value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("\u6682\u4e0d\u4e70\u5165", "avoid"),
        ("\u4e0d\u8981\u4e70\u5165", "avoid"),
        ("\u4e0d\u5b9c\u4e70\u5165", "avoid"),
        ("\u5148\u4e0d\u4e70\u5165", "avoid"),
        ("\u65e0\u9700\u4e70\u5165", "avoid"),
        ("\u65e0\u987b\u4e70\u5165", "avoid"),
        ("\u4e0d\u5efa\u8bae\u5efa\u4ed3", "avoid"),
        ("\u6682\u4e0d\u5efa\u4ed3", "avoid"),
        ("\u65e0\u9700\u5efa\u4ed3", "avoid"),
        ("\u65e0\u987b\u5efa\u4ed3", "avoid"),
        ("\u4e0d\u5efa\u8bae\u5e03\u5c40", "avoid"),
        ("\u5148\u4e0d\u5e03\u5c40", "avoid"),
        ("\u65e0\u9700\u5e03\u5c40", "avoid"),
        ("\u65e0\u987b\u5e03\u5c40", "avoid"),
        ("no buy", "avoid"),
        ("no need to buy", "avoid"),
        ("need not buy", "avoid"),
        ("cannot buy", "avoid"),
        ("can't buy", "avoid"),
        ("not a buy yet", "avoid"),
        ("not to buy", "avoid"),
        ("avoid buying", "avoid"),
        ("avoid buying into weakness", "avoid"),
        ("\u4e0d\u5efa\u8bae\u52a0\u4ed3", "hold"),
        ("\u65e0\u987b\u52a0\u4ed3", "hold"),
        ("no add", "hold"),
        ("no need to add", "hold"),
        ("need not add", "hold"),
        ("cannot add", "hold"),
        ("not to add", "hold"),
        ("no accumulate", "hold"),
        ("can't accumulate", "hold"),
        ("not to accumulate", "hold"),
        ("\u4e0d\u5efa\u8bae\u5356\u51fa", "hold"),
        ("\u65e0\u9700\u5356\u51fa", "hold"),
        ("\u65e0\u987b\u5356\u51fa", "hold"),
        ("\u4e0d\u8981\u5356\u51fa", "hold"),
        ("\u6682\u4e0d\u5356\u51fa", "hold"),
        ("no sell", "hold"),
        ("no need to sell", "hold"),
        ("cannot sell", "hold"),
        ("can't sell", "hold"),
        ("not a sell yet", "hold"),
        ("not to sell", "hold"),
        ("\u65e0\u9700\u51cf\u4ed3", "hold"),
        ("\u65e0\u987b\u51cf\u4ed3", "hold"),
        ("no reduce", "hold"),
        ("no need to reduce", "hold"),
        ("cannot reduce", "hold"),
        ("not to reduce", "hold"),
        ("no trim", "hold"),
        ("can't trim", "hold"),
        ("not a trim yet", "hold"),
        ("not to trim", "hold"),
        ("avoid selling into weakness", "hold"),
        ("avoid trimming before earnings", "hold"),
        ("avoid reducing exposure before earnings", "hold"),
        ("\u4e0d\u5efa\u8bae\u6e05\u4ed3", "hold"),
    ],
)
def test_normalize_decision_action_handles_negated_trade_actions(value: str, expected: str) -> None:
    assert normalize_decision_action(value) == expected


@pytest.mark.parametrize(
    "advice",
    [
        "\u65e0\u9700\u4e70\u5165，\u7b49\u5f85\u786e\u8ba4",
        "\u65e0\u987b\u5efa\u4ed3，\u7ee7\u7eed\u89c2\u5bdf",
        "\u65e0\u9700\u5e03\u5c40，\u7b49\u5f85\u7a81\u7834",
        "no buy until breakout",
        "no need to buy before confirmation",
        "cannot buy before confirmation",
        "can't buy before confirmation",
        "not a buy yet",
        "not to buy",
    ],
)
def test_build_action_fields_prioritizes_negated_buy_advice_over_embedded_buy_phrase(advice: str) -> None:
    assert build_action_fields(operation_advice=advice) == {
        "action": "avoid",
        "action_label": "\u56de\u907f",
    }


@pytest.mark.parametrize(
    "advice",
    [
        "\u65e0\u987b\u52a0\u4ed3，\u7ef4\u6301\u4ed3\u4f4d",
        "\u65e0\u9700\u5356\u51fa，\u7ee7\u7eed\u6301\u6709",
        "\u65e0\u987b\u51cf\u4ed3，\u7b49\u5f85\u786e\u8ba4",
        "no add before confirmation",
        "cannot add before confirmation",
        "no need to accumulate here",
        "can't accumulate here",
        "no sell before earnings",
        "cannot sell before earnings",
        "no need to reduce exposure",
        "can't reduce exposure",
        "no trim while trend holds",
        "cannot trim while trend holds",
        "not a sell yet",
        "not a trim yet",
        "not to sell",
        "not to trim",
        "avoid selling into weakness",
        "avoid trimming before earnings",
        "avoid reducing exposure before earnings",
    ],
)
def test_build_action_fields_prioritizes_negated_hold_advice_over_embedded_trade_phrase(advice: str) -> None:
    assert build_action_fields(operation_advice=advice) == {
        "action": "hold",
        "action_label": "\u6301\u6709",
    }


@pytest.mark.parametrize(
    "advice",
    [
        "risk alert, avoid buying",
        "\u98ce\u9669\u9884\u8b66，\u907f\u514d\u4e70\u5165",
    ],
)
def test_build_action_fields_keeps_multi_guard_advice_empty(advice: str) -> None:
    assert build_action_fields(operation_advice=advice) == {
        "action": None,
        "action_label": None,
    }


@pytest.mark.parametrize(
    "advice",
    [
        "\u4e70\u76d8\u589e\u5f3a，\u7ee7\u7eed\u89c2\u5bdf",
        "\u5356\u538b\u7f13\u89e3，\u7ee7\u7eed\u89c2\u5bdf",
        "\u5356\u65b9\u8bc4\u7ea7\u5206\u6b67",
    ],
)
def test_build_action_fields_keeps_chinese_financial_context_empty(advice: str) -> None:
    assert build_action_fields(operation_advice=advice) == {
        "action": None,
        "action_label": None,
    }


@pytest.mark.parametrize(
    "advice",
    [
        "no buyback announced",
        "cannot buyback shares now",
        "no selloff risk",
        "not selloff yet",
    ],
)
def test_build_action_fields_keeps_financial_compound_terms_empty(advice: str) -> None:
    assert build_action_fields(operation_advice=advice) == {
        "action": None,
        "action_label": None,
    }


@pytest.mark.parametrize(
    "advice",
    [
        "share buy-back announced",
        "share buy back announced",
        "sell-off risk remains low",
        "sell off risk remains low",
        "no sell-off pressure",
    ],
)
def test_build_action_fields_keeps_hyphenated_financial_compound_terms_empty(advice: str) -> None:
    assert build_action_fields(operation_advice=advice) == {
        "action": None,
        "action_label": None,
    }


@pytest.mark.parametrize(
    ("advice", "expected_action", "expected_label"),
    [
        ("buy after sell-off", "buy", "\u4e70\u5165"),
        ("sell after buy-back rumor", "sell", "\u5356\u51fa"),
    ],
)
def test_financial_compound_mask_preserves_separate_action_terms(
    advice: str,
    expected_action: str,
    expected_label: str,
) -> None:
    assert normalize_decision_action(advice) == expected_action
    assert build_action_fields(operation_advice=advice) == {
        "action": expected_action,
        "action_label": expected_label,
    }


def test_localize_action_label_uses_report_language() -> None:
    assert localize_action_label("avoid", "zh") == "\u56de\u907f"
    assert localize_action_label("avoid", "en") == "Avoid"


def test_build_action_fields_respects_market_review_exclusion() -> None:
    fields = build_action_fields(
        operation_advice="\u4e70\u5165",
        explicit_action="buy",
        report_type="market_review",
    )

    assert fields == {"action": None, "action_label": None}


def test_build_action_fields_prefers_explicit_action_over_advice() -> None:
    fields = build_action_fields(
        operation_advice="\u4e70\u5165",
        explicit_action="watch",
        report_language="zh",
    )

    assert fields == {"action": "watch", "action_label": "\u89c2\u671b"}


def test_build_action_fields_keeps_empty_action_without_advice_or_explicit_action() -> None:
    fields = build_action_fields(
        operation_advice=None,
        report_language="zh",
    )

    assert fields == {"action": None, "action_label": None}


@pytest.mark.parametrize(
    ("score", "expected_signal", "expected_action", "expected_decision_type"),
    [
        (28, "reduce", "reduce", "sell"),
        (38, "reduce", "reduce", "sell"),
        (42, "watch", "watch", "hold"),
        (55, "watch", "watch", "hold"),
        (60, "buy", "buy", "buy"),
        (66, "buy", "buy", "buy"),
        (72, "buy", "buy", "buy"),
    ],
)
def test_canonical_score_scale_boundaries(
    score: int,
    expected_signal: str,
    expected_action: str,
    expected_decision_type: str,
) -> None:
    assert signal_key_for_score(score) == expected_signal
    assert action_for_score(score) == expected_action
    assert decision_type_for_score(score) == expected_decision_type


def test_build_action_fields_can_align_neutral_action_with_directional_score() -> None:
    assert build_action_fields(
        operation_advice="\u6301\u6709",
        sentiment_score=72,
        align_with_score=True,
    ) == {"action": "buy", "action_label": "\u4e70\u5165"}

    assert build_action_fields(
        operation_advice="\u89c2\u671b",
        sentiment_score=28,
        align_with_score=True,
    ) == {"action": "reduce", "action_label": "\u51cf\u4ed3"}


def test_build_action_fields_keeps_neutral_score_conflict_when_guardrail_is_explicit() -> None:
    assert build_action_fields(
        operation_advice="\u6301\u6709/\u89c2\u671b\u5f85\u56de\u8e29",
        sentiment_score=72,
        guardrail_reason="\u7b49\u5f85\u56de\u8e29\u786e\u8ba4",
        align_with_score=True,
    ) == {"action": "watch", "action_label": "\u89c2\u671b"}
