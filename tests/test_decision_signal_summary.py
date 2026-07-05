# -*- coding: utf-8 -*-
"""Tests for low-sensitive DecisionSignal summary helpers."""

from __future__ import annotations

from src.services.decision_signal_summary import (
    format_decision_signal_excerpt,
    summarize_decision_signal,
)


def test_summarize_decision_signal_keeps_only_low_sensitive_fields() -> None:
    summary = summarize_decision_signal({
        "id": 42,
        "stock_code": "600519",
        "stock_name": "\u8d35\u5dde\u8305\u53f0",
        "market": "cn",
        "action": "sell",
        "action_label": "\u5356\u51fa",
        "horizon": "3d",
        "status": "active",
        "source_type": "alert",
        "source_agent": "alert_worker",
        "source_report_id": 88,
        "reason": "token=secret-value \u89e6\u53d1\u6b62\u635f",
        "watch_conditions": ["\u89c2\u5bdf\u91cf\u80fd", "password=hidden"],
        "risk_summary": {"drawdown": "webhook=https://hooks.slack.com/services/T/B/C"},
        "created_at": "2026-06-18T10:00:00+08:00",
        "expires_at": "2026-06-25T10:00:00+08:00",
        "metadata": {"webhook_url": "https://hooks.slack.com/services/T/B/C"},
        "evidence": {"secret": "raw"},
        "diagnostics": "authorization=Bearer raw",
    })

    assert summary is not None
    assert set(summary) == {
        "id",
        "stock_code",
        "stock_name",
        "market",
        "action",
        "action_label",
        "horizon",
        "status",
        "source_type",
        "source_report_id",
        "reason",
        "watch_conditions",
        "risk_summary",
        "created_at",
        "expires_at",
    }
    assert summary["reason"] == "token=[REDACTED] \u89e6\u53d1\u6b62\u635f"
    assert summary["watch_conditions"] == ["\u89c2\u5bdf\u91cf\u80fd", "password=[REDACTED]"]
    assert summary["risk_summary"] == {"drawdown": "webhook=[REDACTED_URL]"}


def test_summarize_decision_signal_rejects_non_dict_and_empty_payload() -> None:
    assert summarize_decision_signal(None) is None
    assert summarize_decision_signal(["not", "a", "dict"]) is None
    assert summarize_decision_signal({"metadata": {"token": "secret"}, "evidence": {"raw": True}}) is None
    assert summarize_decision_signal({"stock_code": "", "reason": None}) is None


def test_format_decision_signal_excerpt_formats_chinese_list_and_dict_fields() -> None:
    excerpt = format_decision_signal_excerpt({
        "action_label": "\u5356\u51fa",
        "horizon": "3d",
        "source_report_id": 88,
        "reason": "\u8dcc\u7834\u6b62\u635f\u7ebf",
        "watch_conditions": ["\u89c2\u5bdf 1660 \u652f\u6491", "\u7b49\u5f85\u6210\u4ea4\u91cf\u6536\u7f29"],
        "risk_summary": {"drawdown": "\u7ec4\u5408\u56de\u64a4\u6269\u5927"},
    })

    assert excerpt.startswith("**AI \u51b3\u7b56\u4fe1\u53f7**")
    assert "\u52a8\u4f5c: \u5356\u51fa | \u5468\u671f: 3d | \u62a5\u544a: #88" in excerpt
    assert "- \u7406\u7531: \u8dcc\u7834\u6b62\u635f\u7ebf" in excerpt
    assert "- \u89c2\u5bdf\u6761\u4ef6: \u89c2\u5bdf 1660 \u652f\u6491；\u7b49\u5f85\u6210\u4ea4\u91cf\u6536\u7f29" in excerpt
    assert "- \u98ce\u9669: drawdown: \u7ec4\u5408\u56de\u64a4\u6269\u5927" in excerpt


def test_format_decision_signal_excerpt_formats_english_and_redacts_text() -> None:
    excerpt = format_decision_signal_excerpt({
        "action": "alert",
        "horizon": "5d",
        "reason": "authorization: Bearer raw-token",
        "watch_conditions": "Check price",
        "risk_summary": "token=hidden",
    }, report_language="en")

    assert excerpt.startswith("**AI decision signal**")
    assert "Action: alert | Horizon: 5d" in excerpt
    assert "- Reason: authorization: [REDACTED]" in excerpt
    assert "- Watch: Check price" in excerpt
    assert "- Risk: token=[REDACTED]" in excerpt


def test_format_decision_signal_excerpt_returns_empty_for_invalid_input() -> None:
    assert format_decision_signal_excerpt(None) == ""
    assert format_decision_signal_excerpt({}) == ""
    assert format_decision_signal_excerpt(["not", "a", "dict"]) == ""
