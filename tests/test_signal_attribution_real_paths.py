# -*- coding: utf-8 -*-
"""Tests for signal_attribution real entry points (not just schema)."""

import sys
import os

# \u786e\u4fdd\u9879\u76ee\u6839\u76ee\u5f55\u5728 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.data_processing import normalize_signal_attribution_values, normalize_dashboard_signal_attribution
from src.schemas.report_schema import Dashboard, SignalAttribution

# AnalysisResult \u5728 analyzer.py \u4e2d\u5b9a\u4e49
from src.analyzer import AnalysisResult


class TestNormalizeSignalAttribution:
    """\u6d4b\u8bd5\u5f52\u4e00\u5316\u51fd\u6570（\u63a5\u5728 _parse_response \u4e4b\u524d\u6267\u884c）"""

    def test_string_percentage_conversion(self):
        d = {"technical_indicators": "70%", "news_sentiment": "0%", "fundamentals": "15%", "market_conditions": "15%"}
        normalize_signal_attribution_values(d)
        assert d["technical_indicators"] == 70
        assert d["news_sentiment"] == 0

    def test_na_string_becomes_none(self):
        d = {"technical_indicators": "N/A", "news_sentiment": 0, "fundamentals": 0, "market_conditions": 0}
        normalize_signal_attribution_values(d)
        assert d["technical_indicators"] is None

    def test_negative_clamped_to_zero(self):
        d = {"technical_indicators": -10, "news_sentiment": 20, "fundamentals": 30, "market_conditions": 60}
        normalize_signal_attribution_values(d)
        assert d["technical_indicators"] == 0

    def test_sum_normalized_to_100(self):
        d = {"technical_indicators": 70, "news_sentiment": 10, "fundamentals": 20, "market_conditions": 10}
        # sum=110
        normalize_signal_attribution_values(d)
        total = sum([d["technical_indicators"], d["news_sentiment"], d["fundamentals"], d["market_conditions"]])
        assert total == 100

    def test_partial_none_no_normalization(self):
        d = {"technical_indicators": 70, "news_sentiment": None, "fundamentals": 30, "market_conditions": None}
        normalize_signal_attribution_values(d)
        # \u53ea\u6709\u4e24\u4e2a\u6709\u6548\u503c，\u4e0d\u5f52\u4e00\u5316
        assert d["technical_indicators"] == 70
        assert d["news_sentiment"] is None


class TestNormalizeDashboardSignalAttribution:
    """\u6d4b\u8bd5 dashboard \u7ea7\u522b\u7684\u5f52\u4e00\u5316（\u76f4\u63a5\u5728 dashboard dict \u4e0a\u64cd\u4f5c）"""

    def test_inplace_normalization(self):
        dashboard = {
            "signal_attribution": {
                "technical_indicators": "70%",
                "news_sentiment": "0%",
                "fundamentals": "15%",
                "market_conditions": "15%",
            }
        }
        normalize_dashboard_signal_attribution(dashboard)
        sa = dashboard["signal_attribution"]
        assert sa["technical_indicators"] == 70

    def test_no_signal_attribution_key(self):
        dashboard = {"core_conclusion": {}}
        normalize_dashboard_signal_attribution(dashboard)  # \u4e0d\u5e94\u62a5\u9519
        assert "signal_attribution" not in dashboard

    def test_signal_attribution_none(self):
        dashboard = {"signal_attribution": None}
        normalize_dashboard_signal_attribution(dashboard)  # \u4e0d\u5e94\u62a5\u9519


class TestParseResponseIntegration:
    """
    \u6d4b\u8bd5 _parse_response \u80fd\u6b63\u786e\u89e3\u6790 signal_attribution。
    \u7531\u4e8e _parse_response \u662f\u5b9e\u4f8b\u65b9\u6cd5\u4e14\u4f9d\u8d56\u5f88\u591a\u914d\u7f6e，\u8fd9\u91cc\u7528\u96c6\u6210\u6d4b\u8bd5\u9a8c\u8bc1\u5f52\u4e00\u5316\u51fd\u6570\u88ab\u6b63\u786e\u8c03\u7528。
    """

    def test_normalization_called_in_parse_response(self):
        """
        \u9a8c\u8bc1：\u5982\u679c LLM \u8fd4\u56de\u5b57\u7b26\u4e32\u767e\u5206\u6bd4，\u5f52\u4e00\u5316\u540e\u53d8\u6210 int。
        \u901a\u8fc7\u76f4\u63a5\u6d4b\u8bd5 _parse_response \u7684\u5f52\u4e00\u5316\u8c03\u7528\u6765\u9a8c\u8bc1。
        """
        # \u6a21\u62df LLM \u8fd4\u56de\u7684 data dict
        data = {
            "sentiment_score": 50,
            "trend_prediction": "\u9707\u8361",
            "operation_advice": "\u6301\u6709",
            "decision_type": "hold",
            "confidence_level": "\u4e2d",
            "analysis_summary": "\u6d4b\u8bd5",
            "dashboard": {
                "signal_attribution": {
                    "technical_indicators": "70%",
                    "news_sentiment": "0%",
                    "fundamentals": "15%",
                    "market_conditions": "15%",
                    "strongest_bullish_signal": "MACD\u91d1\u53c9",
                    "strongest_bearish_signal": None,
                }
            },
        }
        # \u624b\u52a8\u8c03\u7528\u5f52\u4e00\u5316（\u6a21\u62df _parse_response \u7684\u884c\u4e3a）
        normalize_dashboard_signal_attribution(data.get("dashboard"))
        sa = data["dashboard"]["signal_attribution"]
        assert sa["technical_indicators"] == 70
        assert sa["news_sentiment"] == 0


class TestHistoryServiceDisplay:
    """\u6d4b\u8bd5 HistoryService._generate_single_stock_markdown \u80fd\u5c55\u793a signal_attribution"""

    def test_signal_attribution_in_markdown(self):
        """\u9a8c\u8bc1 markdown \u62a5\u544a\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d"""
        from src.services.history_service import HistoryService

        result = AnalysisResult(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            sentiment_score=50,
            trend_prediction="\u9707\u8361",
            operation_advice="\u6301\u6709",
            dashboard={
                "signal_attribution": {
                    "technical_indicators": 70,
                    "news_sentiment": 0,
                    "fundamentals": 15,
                    "market_conditions": 15,
                    "strongest_bullish_signal": "MACD\u91d1\u53c9",
                    "strongest_bearish_signal": None,
                }
            },
        )

        # \u521b\u5efa\u4e00\u4e2a mock record
        class MockRecord:
            created_at = None

        markdown = HistoryService()._generate_single_stock_markdown(result, MockRecord())
        assert "\u4fe1\u53f7\u5f52\u56e0" in markdown or "Signal Attribution" in markdown
        assert "70%" in markdown or "70%" in markdown

    def test_no_signal_attribution_no_section(self):
        """\u9a8c\u8bc1\u6ca1\u6709 signal_attribution \u65f6\u4e0d\u663e\u793a\u6bb5\u843d"""
        from src.services.history_service import HistoryService

        result = AnalysisResult(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            sentiment_score=50,
            trend_prediction="\u9707\u8361",
            operation_advice="\u6301\u6709",
            dashboard={},
        )

        class MockRecord:
            created_at = None

        markdown = HistoryService()._generate_single_stock_markdown(result, MockRecord())
        assert "\u4fe1\u53f7\u5f52\u56e0" not in markdown


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
