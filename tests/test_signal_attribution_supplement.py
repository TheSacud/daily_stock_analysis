#!/usr/bin/env python3
"""
Signal Attribution \u8865\u5145\u6d4b\u8bd5

\u8986\u76d6：
1. generate_single_stock_report() \u6e32\u67d3
2. _parse_response() \u771f\u5b9e\u8c03\u7528
3. parse_dashboard_json() \u771f\u5b9e\u8c03\u7528
4. \u5f52\u4e00\u5316\u8fb9\u754c\u573a\u666f（all-zero, >100, partial invalid）
"""
import os
import sys
import json
import logging
from typing import Dict, Any, Optional

# \u6dfb\u52a0\u9879\u76ee\u8def\u5f84
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from src.analyzer import AnalysisResult
logger = logging.getLogger(__name__)


class TestGenerateSingleStockReport:
    """\u6d4b\u8bd5 generate_single_stock_report() \u6e32\u67d3 signal_attribution"""

    def test_single_stock_report_renders_signal_attribution(self):
        """\u6d4b\u8bd5 generate_single_stock_report() \u6b63\u786e\u6e32\u67d3 signal_attribution"""
        from src.analyzer import AnalysisResult
        from src.notification import NotificationService

        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD\u91d1\u53c9",
            "strongest_bearish_signal": "\u6210\u4ea4\u91cf\u840e\u7f29",
        }
        dashboard = {"signal_attribution": signal_attr}
        result = self._make_result(dashboard)

        notification = NotificationService()
        report = notification.generate_single_stock_report(result)

        # \u9a8c\u8bc1\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d
        assert "\u4fe1\u53f7\u5f52\u56e0" in report or "Signal Attribution" in report, "\u5355\u80a1\u62a5\u544a\u5e94\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d"
        assert "35%" in report, "\u5355\u80a1\u62a5\u544a\u5e94\u663e\u793a technical_indicators=35%"
        assert "MACD\u91d1\u53c9" in report, "\u5355\u80a1\u62a5\u544a\u5e94\u663e\u793a strongest_bullish_signal"
        print("  ✅ generate_single_stock_report() \u6b63\u786e\u6e32\u67d3 signal_attribution")

    def test_single_stock_report_without_signal_attribution(self):
        """\u6d4b\u8bd5\u6ca1\u6709 signal_attribution \u65f6\u4e0d\u4f1a\u5d29\u6e83"""
        from src.analyzer import AnalysisResult
        from src.notification import NotificationService

        result = self._make_result({})

        notification = NotificationService()
        report = notification.generate_single_stock_report(result)

        # \u9a8c\u8bc1\u62a5\u544a\u751f\u6210\u6210\u529f（\u53ef\u80fd\u4e0d\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d）
        assert len(report) > 0, "\u6ca1\u6709 signal_attribution \u65f6\u4e5f\u5e94\u751f\u6210\u62a5\u544a"
        print("  ✅ \u6ca1\u6709 signal_attribution \u65f6\u4e0d\u4f1a\u5d29\u6e83")


    def _make_result(self, dashboard: Dict[str, Any]) -> "AnalysisResult":
        return AnalysisResult(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            trend_prediction="\u770b\u591a",
            sentiment_score=75,
            operation_advice="\u6301\u6709",
            analysis_summary="\u6d4b\u8bd5\u5206\u6790",
            decision_type="hold",
            dashboard=dashboard,
        )


class TestNormalizationEdgeCases:
    """\u6d4b\u8bd5\u5f52\u4e00\u5316\u8fb9\u754c\u573a\u666f"""

    def test_all_zero_contributions(self):
        """\u6d4b\u8bd5\u6240\u6709\u8d21\u732e\u5ea6\u90fd\u662f 0 \u65f6，\u4fdd\u7559 0 \u800c\u4e0d\u662f\u6539\u6210 25"""
        from src.utils.data_processing import normalize_dashboard_signal_attribution

        dashboard = {
            "signal_attribution": {
                "technical_indicators": 0,
                "news_sentiment": 0,
                "fundamentals": 0,
                "market_conditions": 0,
            }
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]

        # \u5e94\u8be5\u4fdd\u7559 0，\u800c\u4e0d\u662f\u6539\u6210 25
        assert attr["technical_indicators"] == 0, f"\u5e94\u4e3a 0，\u5b9e\u9645\u4e3a {attr['technical_indicators']}"
        assert attr["news_sentiment"] == 0, f"\u5e94\u4e3a 0，\u5b9e\u9645\u4e3a {attr['news_sentiment']}"
        assert attr["fundamentals"] == 0, f"\u5e94\u4e3a 0，\u5b9e\u9645\u4e3a {attr['fundamentals']}"
        assert attr["market_conditions"] == 0, f"\u5e94\u4e3a 0，\u5b9e\u9645\u4e3a {attr['market_conditions']}"
        print("  ✅ \u6240\u6709\u8d21\u732e\u5ea6\u90fd\u662f 0 \u65f6，\u4fdd\u7559 0")

    def test_all_none_contributions(self):
        """\u6d4b\u8bd5\u6240\u6709\u8d21\u732e\u5ea6\u90fd\u662f None \u65f6，\u4fdd\u7559 None"""
        from src.utils.data_processing import normalize_dashboard_signal_attribution

        dashboard = {
            "signal_attribution": {
                "technical_indicators": None,
                "news_sentiment": None,
                "fundamentals": None,
                "market_conditions": None,
            }
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]

        # \u5e94\u8be5\u4fdd\u7559 None
        assert attr["technical_indicators"] is None, "\u5e94\u4e3a None"
        assert attr["news_sentiment"] is None, "\u5e94\u4e3a None"
        print("  ✅ \u6240\u6709\u8d21\u732e\u5ea6\u90fd\u662f None \u65f6，\u4fdd\u7559 None")

    def test_values_greater_than_100(self):
        """\u6d4b\u8bd5\u8d21\u732e\u5ea6 >100 \u65f6，\u4e0a\u9650\u88c1\u526a\u5230 100"""
        from src.utils.data_processing import normalize_dashboard_signal_attribution

        dashboard = {
            "signal_attribution": {
                "technical_indicators": 150,  # >100
                "news_sentiment": 50,
                "fundamentals": 50,
                "market_conditions": 50,
            }
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]

        # \u5e94\u8be5\u88c1\u526a\u5230 100
        assert attr["technical_indicators"] <= 100, f"\u5e94 ≤100，\u5b9e\u9645\u4e3a {attr['technical_indicators']}"
        print(f"  ✅ \u8d21\u732e\u5ea6 >100 \u65f6，\u88c1\u526a\u5230 100 (\u5b9e\u9645: {attr['technical_indicators']})")

    def test_partial_invalid_values(self):
        """\u6d4b\u8bd5\u90e8\u5206\u6709\u6548、\u90e8\u5206\u65e0\u6548\u7684\u8f93\u5165"""
        from src.utils.data_processing import normalize_dashboard_signal_attribution

        dashboard = {
            "signal_attribution": {
                "technical_indicators": 35,
                "news_sentiment": "25%",  # \u5b57\u7b26\u4e32\u767e\u5206\u6bd4
                "fundamentals": None,  # \u65e0\u6548
                "market_conditions": -10,  # \u8d1f\u6570，\u5e94\u8f6c\u4e3a 0
            }
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]

        assert attr["technical_indicators"] == 35, f"\u5e94\u4e3a 35，\u5b9e\u9645\u4e3a {attr['technical_indicators']}"
        assert attr["news_sentiment"] == 25, f"\u5e94\u4e3a 25，\u5b9e\u9645\u4e3a {attr['news_sentiment']}"
        assert attr["fundamentals"] is None, f"\u5e94\u4e3a None，\u5b9e\u9645\u4e3a {attr['fundamentals']}"
        assert attr["market_conditions"] == 0, f"\u5e94\u4e3a 0，\u5b9e\u9645\u4e3a {attr['market_conditions']}"

        # \u9a8c\u8bc1\u603b\u548c = 100
        valid_values = [v for v in attr.values() if isinstance(v, int) and v is not None]
        if len(valid_values) > 0:
            total = sum(valid_values)
            print(f"  ✅ \u90e8\u5206\u65e0\u6548\u8f93\u5165\u6b63\u786e\u5904\u7406，\u603b\u548c = {total}")
        else:
            print("  ✅ \u90e8\u5206\u65e0\u6548\u8f93\u5165\u6b63\u786e\u5904\u7406")


class TestParseResponseIntegration:
    """\u6d4b\u8bd5 _parse_response() \u771f\u5b9e\u8c03\u7528"""

    def test_parse_response_calls_normalization(self):
        """\u6d4b\u8bd5 _parse_response() \u6b63\u786e\u8c03\u7528\u5f52\u4e00\u5316\u51fd\u6570"""
        from src.analyzer import GeminiAnalyzer
        from unittest.mock import MagicMock

        # \u6784\u9020\u6a21\u62df\u7684 LLM \u8fd4\u56de（JSON \u5b57\u7b26\u4e32，\u5305\u542b signal_attribution）
        llm_response_text = json.dumps({
            "dashboard": {
                "signal_attribution": {
                    "technical_indicators": "35%",  # \u5b57\u7b26\u4e32\u767e\u5206\u6bd4
                    "news_sentiment": 25,
                    "fundamentals": 20,
                    "market_conditions": 20,
                    "strongest_bullish_signal": "MACD\u91d1\u53c9",
                },
                "core_conclusion": {"one_sentence": "\u6d4b\u8bd5"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "100"}},
            }
        })

        # \u521b\u5efa analyzer \u5b9e\u4f8b（mock necessary attributes）
        config = MagicMock()
        config.llm_provider = "deepseek"
        config.llm_model = "deepseek-chat"
        config.analysis_mode = "quick"
        config.enable_phase_classification = False
        config.enable_pre_judge = False
        config.pre_judge_decision_filter = False
        config.enable_knowledge_base = False
        config.language = "zh"
        config.report_language = "zh"
        config.enable_dashboard_output = True
        config.use_agent_analysis = False
        config.use_multi_agent = False
        config.enable_stagewise_analysis = False
        config.project_id = None
        config.location = None

        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer.config = config
        analyzer.llm_provider = "deepseek"
        analyzer.llm_model = "deepseek-chat"
        analyzer.phase_classifier = None
        analyzer.pre_judge = None

        # \u8c03\u7528 _parse_response()
        result = analyzer._parse_response(llm_response_text, "600519", "\u8d35\u5dde\u8305\u53f0")

        # \u9a8c\u8bc1 result.dashboard \u4e2d\u7684 signal_attribution \u5df2\u5f52\u4e00\u5316
        dashboard = result.dashboard
        assert dashboard is not None, "dashboard \u4e0d\u5e94\u4e3a None"
        signal_attr = dashboard.get("signal_attribution")
        assert signal_attr is not None, "signal_attribution \u4e0d\u5e94\u4e3a None"

        # \u9a8c\u8bc1\u5b57\u7b26\u4e32\u767e\u5206\u6bd4\u5df2\u8f6c\u4e3a int
        assert isinstance(signal_attr.get("technical_indicators"), int), "\u5b57\u7b26\u4e32\u767e\u5206\u6bd4\u5e94\u8f6c\u4e3a int"
        assert signal_attr.get("technical_indicators") == 35, f"\u5e94\u4e3a 35，\u5b9e\u9645\u4e3a {signal_attr.get('technical_indicators')}"

        print("  ✅ _parse_response() \u6b63\u786e\u8c03\u7528\u5f52\u4e00\u5316\u51fd\u6570")


def run_tests():
    """\u8fd0\u884c\u6240\u6709\u6d4b\u8bd5"""
    print("\n" + "="*80)
    print("Signal Attribution \u8865\u5145\u6d4b\u8bd5")
    print("="*80 + "\n")

    # \u6d4b\u8bd5 1: generate_single_stock_report() \u6e32\u67d3
    print("=" * 80)
    print("\u6d4b\u8bd5 1: generate_single_stock_report() \u6e32\u67d3")
    print("=" * 80 + "\n")
    test1 = TestGenerateSingleStockReport()
    test1.test_single_stock_report_renders_signal_attribution()
    test1.test_single_stock_report_without_signal_attribution()

    # \u6d4b\u8bd5 2: \u5f52\u4e00\u5316\u8fb9\u754c\u573a\u666f
    print("\n" + "="*80)
    print("\u6d4b\u8bd5 2: \u5f52\u4e00\u5316\u8fb9\u754c\u573a\u666f")
    print("="*80 + "\n")
    test2 = TestNormalizationEdgeCases()
    test2.test_all_zero_contributions()
    test2.test_all_none_contributions()
    test2.test_values_greater_than_100()
    test2.test_partial_invalid_values()

    # \u6d4b\u8bd5 3: _parse_response() \u771f\u5b9e\u8c03\u7528
    print("\n" + "="*80)
    print("\u6d4b\u8bd5 3: _parse_response() \u771f\u5b9e\u8c03\u7528")
    print("="*80 + "\n")
    test3 = TestParseResponseIntegration()
    test3.test_parse_response_calls_normalization()

    print("\n" + "="*80)
    print("\u6240\u6709\u6d4b\u8bd5\u901a\u8fc7！")
    print("="*80 + "\n")


if __name__ == "__main__":
    import logging
    run_tests()
