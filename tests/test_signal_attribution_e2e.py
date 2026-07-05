"""
\u7aef\u5230\u7aef\u6d4b\u8bd5：signal_attribution \u5b8c\u6574\u5951\u7ea6\u6536\u655b\u6d4b\u8bd5。

\u9a8c\u8bc1\u4ee5\u4e0b\u8def\u5f84：
1. LLM raw JSON → _parse_response() → AnalysisResult.dashboard (\u5f52\u4e00\u5316\u751f\u6548)
2. AnalysisResult.dashboard → notification (\u5c55\u793a\u6b63\u786e)
3. AnalysisResult.dashboard → Jinja2 template (\u6e32\u67d3\u6b63\u786e)
4. AnalysisResult.dashboard → HistoryService markdown (\u6e32\u67d3\u6b63\u786e)
5. check_content_integrity() (\u5951\u7ea6\u68c0\u67e5)
"""
import sys
import os
import pytest
import json

# \u6dfb\u52a0 src \u5230 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.analyzer import AnalysisResult, check_content_integrity
from src.utils.data_processing import normalize_dashboard_signal_attribution
from src.agent.runner import parse_dashboard_json
from src.services.report_renderer import render


class TestSignalAttributionE2E:
    """\u7aef\u5230\u7aef\u6d4b\u8bd5：\u9a8c\u8bc1 signal_attribution \u5728\u6240\u6709\u8def\u5f84\u4e2d\u6b63\u786e\u5de5\u4f5c"""

    def _make_dashboard_with_signal_attr(self, signal_attr):
        """\u521b\u5efa\u5305\u542b signal_attribution \u7684 dashboard dict"""
        return {
            "core_conclusion": {
                "one_sentence": "\u6d4b\u8bd5\u7ed3\u8bba",
                "signal": "buy",
                "confidence": "\u4e2d",
            },
            "intelligence": {
                "risk_alerts": ["\u6d4b\u8bd5\u98ce\u9669"],
            },
            "signal_attribution": signal_attr,
        }

    def _make_result(self, dashboard):
        """\u521b\u5efa AnalysisResult"""
        return AnalysisResult(
            code="600519",
            name="\u6d4b\u8bd5\u80a1\u7968",
            sentiment_score=50,
            trend_prediction="\u9707\u8361",
            operation_advice="\u6301\u6709",
            decision_type="hold",
            confidence_level="\u4e2d",
            dashboard=dashboard,
            analysis_summary="\u6d4b\u8bd5\u6458\u8981",
        )

    # ========== \u6d4b\u8bd5 1: _parse_response() \u5f52\u4e00\u5316 ==========
    def test_normalize_called_in_parse_response(self):
        """
        \u6d4b\u8bd5 _parse_response() \u4e2d\u5f52\u4e00\u5316\u51fd\u6570\u88ab\u8c03\u7528。

        \u9a8c\u8bc1：
        1. \u8f93\u5165\u8d21\u732e\u5ea6\u4e3a\u5b57\u7b26\u4e32 "30%" → \u5f52\u4e00\u5316\u540e\u53d8\u4e3a int 30
        2. \u8f93\u5165\u8d21\u732e\u5ea6\u4e4b\u548c\u4e0d\u4e3a 100 → \u5f52\u4e00\u5316\u540e\u53d8\u4e3a\u4e4b\u548c=100
        """
        from src.analyzer import GeminiAnalyzer

        # \u521b\u5efa analyzer \u5b9e\u4f8b
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)

        # \u6a21\u62df LLM \u8fd4\u56de\u7684 JSON（\u8d21\u732e\u5ea6\u4e3a\u5b57\u7b26\u4e32，\u603b\u548c≠100）
        response_text = json.dumps({
            "sentiment_score": 50,
            "trend_prediction": "\u9707\u8361",
            "operation_advice": "\u6301\u6709",
            "decision_type": "hold",
            "confidence_level": "\u4e2d",
            "analysis_summary": "\u6d4b\u8bd5",
            "dashboard": {
                "core_conclusion": {"one_sentence": "\u6d4b\u8bd5", "signal": "hold", "confidence": "\u4e2d"},
                "intelligence": {"risk_alerts": []},
                "signal_attribution": {
                    "technical_indicators": "30%",
                    "news_sentiment": 20,
                    "fundamentals": 30,
                    "market_conditions": 10,  # \u603b\u548c=90，\u4e14\u6709\u4e00\u4e2a\u662f\u5b57\u7b26\u4e32
                    "strongest_bullish_signal": "\u6d4b\u8bd5\u770b\u6da8",
                    "strongest_bearish_signal": "\u6d4b\u8bd5\u770b\u7a7a",
                },
            },
        })

        # \u8c03\u7528 _parse_response()
        result = analyzer._parse_response(response_text, "600519", "\u6d4b\u8bd5")

        # \u9a8c\u8bc1\u5f52\u4e00\u5316\u5df2\u6267\u884c
        dash = result.dashboard
        assert isinstance(dash, dict), "dashboard \u5e94\u8be5\u662f dict"

        signal_attr = dash.get("signal_attribution")
        assert signal_attr is not None, "signal_attribution \u5e94\u8be5\u5b58\u5728"

        # \u9a8c\u8bc1\u5b57\u7b26\u4e32\u5df2\u8f6c\u4e3a int
        assert isinstance(signal_attr.get("technical_indicators"), int), "technical_indicators \u5e94\u8be5\u662f int"

        # \u9a8c\u8bc1\u603b\u548c=100
        total = sum([
            signal_attr.get("technical_indicators", 0),
            signal_attr.get("news_sentiment", 0),
            signal_attr.get("fundamentals", 0),
            signal_attr.get("market_conditions", 0),
        ])
        assert total == 100, f"\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u8be5=100，\u5b9e\u9645={total}"

    # ========== \u6d4b\u8bd5 2: notification \u6e32\u67d3 ==========
    def test_notification_renders_signal_attribution(self):
        """
        \u6d4b\u8bd5 notification.py \u4e2d generate_dashboard_report() \u6b63\u786e\u6e32\u67d3 signal_attribution。

        \u9a8c\u8bc1：
        1. signal_attribution \u5b58\u5728\u65f6，\u901a\u77e5\u4e2d\u5305\u542b"\u4fe1\u53f7\u5f52\u56e0"\u6bb5\u843d
        2. \u56db\u4e2a\u8d21\u732e\u5ea6\u90fd\u6b63\u786e\u663e\u793a
        """
        from src.notification import NotificationService

        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD\u91d1\u53c9",
            "strongest_bearish_signal": "\u6210\u4ea4\u91cf\u840e\u7f29",
        }
        dashboard = self._make_dashboard_with_signal_attr(signal_attr)
        result = self._make_result(dashboard)

        # \u8c03\u7528 generate_dashboard_report()
        notification = NotificationService()
        report = notification.generate_dashboard_report([result], [dashboard])

        # \u9a8c\u8bc1\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d
        assert "\u4fe1\u53f7\u5f52\u56e0" in report or "Signal Attribution" in report, "\u901a\u77e5\u5e94\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d"
        assert "35%" in report, "\u901a\u77e5\u5e94\u663e\u793a technical_indicators=35%"
        assert "25%" in report, "\u901a\u77e5\u5e94\u663e\u793a news_sentiment=25%"
        assert "20%" in report, "\u901a\u77e5\u5e94\u663e\u793a fundamentals=20%"
        assert "20%" in report, "\u901a\u77e5\u5e94\u663e\u793a market_conditions=20%"
        assert "MACD\u91d1\u53c9" in report, "\u901a\u77e5\u5e94\u663e\u793a strongest_bullish_signal"

    # ========== \u6d4b\u8bd5 3: Jinja2 \u6a21\u677f\u6e32\u67d3 ==========
    def test_jinja2_template_renders_signal_attribution(self):
        """
        \u6d4b\u8bd5 templates/report_markdown.j2 \u6b63\u786e\u6e32\u67d3 signal_attribution。

        \u9a8c\u8bc1：
        1. signal_attribution \u5b58\u5728\u65f6，\u6a21\u677f\u8f93\u51fa\u4e2d\u5305\u542b\u5f52\u56e0\u6743\u91cd
        2. \u56db\u4e2a\u8d21\u732e\u5ea6\u90fd\u6b63\u786e\u663e\u793a
        """
        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD\u91d1\u53c9",
        }
        result = self._make_result(self._make_dashboard_with_signal_attr(signal_attr))

        out = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        assert out is not None
        assert "35%" in out
        assert "MACD\u91d1\u53c9" in out

    def test_parse_dashboard_json_normalizes_nested_dashboard_payload(self):
        """Agent JSON can return a full report object with nested dashboard."""
        payload = json.dumps({
            "dashboard": {
                "signal_attribution": {
                    "technical_indicators": "70%",
                    "news_sentiment": "10%",
                    "fundamentals": "10%",
                    "market_conditions": "10%",
                }
            }
        })

        parsed = parse_dashboard_json(payload)

        assert parsed is not None
        signal_attr = parsed["dashboard"]["signal_attribution"]
        assert signal_attr["technical_indicators"] == 70
        assert isinstance(signal_attr["technical_indicators"], int)

    def test_non_dict_signal_attribution_is_removed_before_rendering(self):
        """Invalid non-dict signal_attribution must not survive into renderers."""
        dashboard = {"signal_attribution": "bad payload"}

        normalize_dashboard_signal_attribution(dashboard)

        assert "signal_attribution" not in dashboard

    def test_partial_signal_attribution_uses_same_display_contract(self):
        """Partial weights should not render N/A% or None% in any report path."""
        from src.notification import NotificationService
        from src.services.history_service import HistoryService

        dashboard = self._make_dashboard_with_signal_attr({
            "technical_indicators": 35,
            "news_sentiment": None,
            "fundamentals": None,
            "market_conditions": 0,
            "strongest_bullish_signal": "MACD\u91d1\u53c9",
        })
        result = self._make_result(dashboard)
        notification = NotificationService()

        dashboard_report = notification.generate_dashboard_report([result], [dashboard])
        single_report = notification.generate_single_stock_report(result)

        class MockRecord:
            created_at = None

        history_report = HistoryService.__new__(HistoryService)._generate_single_stock_markdown(result, MockRecord())
        template_report = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        for output in [dashboard_report, single_report, history_report, template_report]:
            assert output is not None
            assert "N/A%" not in output
            assert "None%" not in output
            assert "35%" in output

    def test_all_zero_signal_attribution_is_hidden_without_signals(self):
        """All-zero weights without strongest signals should not render attribution."""
        from src.notification import NotificationService
        from src.services.history_service import HistoryService

        dashboard = self._make_dashboard_with_signal_attr({
            "technical_indicators": 0,
            "news_sentiment": 0,
            "fundamentals": 0,
            "market_conditions": 0,
            "strongest_bullish_signal": None,
            "strongest_bearish_signal": None,
        })
        result = self._make_result(dashboard)
        notification = NotificationService()

        dashboard_report = notification.generate_dashboard_report([result], [dashboard])
        single_report = notification.generate_single_stock_report(result)

        class MockRecord:
            created_at = None

        history_report = HistoryService.__new__(HistoryService)._generate_single_stock_markdown(result, MockRecord())
        template_report = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        for output in [dashboard_report, single_report, history_report, template_report]:
            assert output is not None
            assert "\u4fe1\u53f7\u5f52\u56e0" not in output
            assert "Signal Attribution" not in output

    def test_non_finite_signal_attribution_is_hidden_across_real_paths(self):
        """NaN/Infinity weights are missing values, not confident attribution."""
        from src.analyzer import GeminiAnalyzer
        from src.notification import NotificationService
        from src.services.history_service import HistoryService

        def non_finite_signal_attr():
            return {
                "technical_indicators": float("nan"),
                "news_sentiment": "NaN",
                "fundamentals": float("inf"),
                "market_conditions": "-Infinity",
                "strongest_bullish_signal": None,
                "strongest_bearish_signal": "",
            }

        response_text = json.dumps({
            "sentiment_score": 50,
            "trend_prediction": "\u9707\u8361",
            "operation_advice": "\u6301\u6709",
            "decision_type": "hold",
            "confidence_level": "\u4e2d",
            "analysis_summary": "\u6d4b\u8bd5",
            "dashboard": {
                "core_conclusion": {"one_sentence": "\u6d4b\u8bd5", "signal": "hold", "confidence": "\u4e2d"},
                "intelligence": {"risk_alerts": []},
                "signal_attribution": non_finite_signal_attr(),
            },
        })

        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        result = analyzer._parse_response(response_text, "600519", "\u6d4b\u8bd5")
        dashboard = result.dashboard
        signal_attr = dashboard["signal_attribution"]

        for key in ("technical_indicators", "news_sentiment", "fundamentals", "market_conditions"):
            assert signal_attr[key] is None
        assert signal_attr["strongest_bearish_signal"] is None

        parsed = parse_dashboard_json(json.dumps({
            "dashboard": {
                "signal_attribution": non_finite_signal_attr(),
            }
        }))
        assert parsed is not None
        parsed_attr = parsed["dashboard"]["signal_attribution"]
        for key in ("technical_indicators", "news_sentiment", "fundamentals", "market_conditions"):
            assert parsed_attr[key] is None

        notification = NotificationService()
        dashboard_report = notification.generate_dashboard_report([result], [dashboard])
        single_report = notification.generate_single_stock_report(result)

        class MockRecord:
            created_at = None

        history_report = HistoryService.__new__(HistoryService)._generate_single_stock_markdown(result, MockRecord())
        template_report = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        for output in [dashboard_report, single_report, history_report, template_report]:
            assert output is not None
            assert "\u4fe1\u53f7\u5f52\u56e0" not in output
            assert "Signal Attribution" not in output
            assert "NaN" not in output
            assert "Infinity" not in output

    # ========== \u6d4b\u8bd5 4: HistoryService markdown \u6e32\u67d3 ==========
    def test_history_service_renders_signal_attribution(self):
        """
        \u6d4b\u8bd5 HistoryService._generate_single_stock_markdown() \u6b63\u786e\u6e32\u67d3 signal_attribution。

        \u9a8c\u8bc1：
        1. signal_attribution \u5b58\u5728\u65f6，markdown \u4e2d\u5305\u542b"\u4fe1\u53f7\u5f52\u56e0\u5206\u6790"\u6bb5\u843d
        2. \u56db\u4e2a\u8d21\u732e\u5ea6\u90fd\u6b63\u786e\u663e\u793a
        """
        from src.services.history_service import HistoryService

        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD\u91d1\u53c9",
            "strongest_bearish_signal": "\u6210\u4ea4\u91cf\u840e\u7f29",
        }
        dashboard = self._make_dashboard_with_signal_attr(signal_attr)
        result = self._make_result(dashboard)

        # \u521b\u5efa mock record
        class MockRecord:
            created_at = None

        # \u8c03\u7528 _generate_single_stock_markdown()
        history_service = HistoryService.__new__(HistoryService)
        markdown = history_service._generate_single_stock_markdown(result, MockRecord())

        # \u9a8c\u8bc1\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d
        assert "\u4fe1\u53f7\u5f52\u56e0" in markdown or "Signal Attribution" in markdown, "Markdown \u5e94\u5305\u542b\u4fe1\u53f7\u5f52\u56e0\u6bb5\u843d"
        assert "35%" in markdown, "Markdown \u5e94\u663e\u793a technical_indicators=35%"
        assert "MACD\u91d1\u53c9" in markdown, "Markdown \u5e94\u663e\u793a strongest_bullish_signal"

    # ========== \u6d4b\u8bd5 5: check_content_integrity() optional \u5951\u7ea6 ==========
    def test_check_content_integrity_treats_signal_attribution_as_optional(self):
        """
        \u6d4b\u8bd5 check_content_integrity() \u5c06 signal_attribution \u4f5c\u4e3a\u53ef\u9009\u5c55\u793a\u5b57\u6bb5。

        \u9a8c\u8bc1：
        1. signal_attribution \u5b58\u5728\u65f6，\u4e0d\u6dfb\u52a0\u5230 missing
        2. signal_attribution \u7f3a\u5931\u65f6，\u4e0d\u6dfb\u52a0\u5230 missing
        3. signal_attribution \u8d21\u732e\u5ea6\u7f3a\u5931\u65f6，\u4e0d\u6dfb\u52a0\u5230 missing
        """
        # \u60c5\u51b5 1: signal_attribution \u5b8c\u6574
        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
        }
        dashboard = self._make_dashboard_with_signal_attr(signal_attr)
        result = self._make_result(dashboard)

        passed, missing = check_content_integrity(result)
        signal_attr_missing = [m for m in missing if "signal_attribution" in m]
        assert len(signal_attr_missing) == 0, f"signal_attribution \u5b8c\u6574\u65f6\u4e0d\u5e94\u51fa\u73b0\u5728 missing \u4e2d，\u5b9e\u9645: {signal_attr_missing}"

        # \u60c5\u51b5 2: signal_attribution \u7f3a\u5931
        dashboard_no_attr = self._make_dashboard_with_signal_attr(None)
        dashboard_no_attr["battle_plan"] = {"sniper_points": {"stop_loss": "100"}}
        result_no_attr = self._make_result(dashboard_no_attr)

        passed, missing = check_content_integrity(result_no_attr)
        assert passed is True
        signal_attr_missing = [m for m in missing if "signal_attribution" in m]
        assert len(signal_attr_missing) == 0, "signal_attribution \u7f3a\u5931\u65f6\u4e0d\u5e94\u51fa\u73b0\u5728 missing \u4e2d"

        # \u60c5\u51b5 3: signal_attribution \u8d21\u732e\u5ea6\u7f3a\u5931
        signal_attr_incomplete = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            # \u7f3a\u5c11 fundamentals \u548c market_conditions
        }
        dashboard_incomplete = self._make_dashboard_with_signal_attr(signal_attr_incomplete)
        dashboard_incomplete["battle_plan"] = {"sniper_points": {"stop_loss": "100"}}
        result_incomplete = self._make_result(dashboard_incomplete)

        passed, missing = check_content_integrity(result_incomplete)
        assert passed is True
        signal_attr_missing = [m for m in missing if "signal_attribution" in m]
        assert len(signal_attr_missing) == 0, "signal_attribution \u8d21\u732e\u5ea6\u7f3a\u5931\u65f6\u4e0d\u5e94\u51fa\u73b0\u5728 missing \u4e2d"

    # ========== \u6d4b\u8bd5 6: \u5f52\u4e00\u5316\u51fd\u6570\u6d4b\u8bd5 ==========
    def test_normalize_dashboard_signal_attribution_direct(self):
        """
        \u76f4\u63a5\u6d4b\u8bd5 normalize_dashboard_signal_attribution() \u51fd\u6570。

        \u9a8c\u8bc1：
        1. \u5b57\u7b26\u4e32\u767e\u5206\u6bd4\u8f6c\u4e3a int
        2. \u8d1f\u6570\u8f6c\u4e3a 0
        3. \u603b\u548c≠100 \u65f6\u5f52\u4e00\u5316\u4e3a 100
        4. None \u503c\u5904\u7406
        """
        # \u60c5\u51b5 1: \u5b57\u7b26\u4e32\u767e\u5206\u6bd4
        dashboard = {
            "signal_attribution": {
                "technical_indicators": "30%",
                "news_sentiment": 20,
                "fundamentals": "30",
                "market_conditions": 10,
                "strongest_bullish_signal": "\u6d4b\u8bd5",
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        # \u9a8c\u8bc1\u5b57\u7b26\u4e32\u5df2\u8f6c\u4e3a int（\u5177\u4f53\u503c\u53ef\u80fd\u56e0\u5f52\u4e00\u5316\u800c\u6539\u53d8，\u4f46\u5e94\u8be5\u662f int）
        assert isinstance(attr["technical_indicators"], int), f"\u5b57\u7b26\u4e32\u767e\u5206\u6bd4\u5e94\u8f6c\u4e3a int: {attr['technical_indicators']}"
        assert isinstance(attr["fundamentals"], int), f"\u5b57\u7b26\u4e32\u5e94\u8f6c\u4e3a int: {attr['fundamentals']}"

        # \u9a8c\u8bc1\u603b\u548c=100
        total = sum([
            attr.get("technical_indicators", 0),
            attr.get("news_sentiment", 0),
            attr.get("fundamentals", 0),
            attr.get("market_conditions", 0),
        ])
        assert total == 100, f"\u5f52\u4e00\u5316\u540e\u603b\u548c\u5e94\u4e3a 100: {total}"

        # \u60c5\u51b5 2: \u8d1f\u6570
        dashboard = {
            "signal_attribution": {
                "technical_indicators": -10,
                "news_sentiment": 20,
                "fundamentals": 30,
                "market_conditions": 40,
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        assert attr["technical_indicators"] == 0, f"\u8d1f\u6570\u5e94\u8f6c\u4e3a 0: {attr['technical_indicators']}"

        # \u60c5\u51b5 3: \u603b\u548c=100，\u4e0d\u9700\u8981\u5f52\u4e00\u5316
        dashboard = {
            "signal_attribution": {
                "technical_indicators": 25,
                "news_sentiment": 25,
                "fundamentals": 25,
                "market_conditions": 25,
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        total = sum([attr["technical_indicators"], attr["news_sentiment"], attr["fundamentals"], attr["market_conditions"]])
        assert total == 100, f"\u603b\u548c\u5e94\u4e3a 100: {total}"

        # \u60c5\u51b5 4: \u603b\u548c≠100（\u9700\u8981\u5f52\u4e00\u5316）
        dashboard = {
            "signal_attribution": {
                "technical_indicators": 10,
                "news_sentiment": 20,
                "fundamentals": 30,
                "market_conditions": 30,  # \u603b\u548c=90
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        total = sum([attr["technical_indicators"], attr["news_sentiment"], attr["fundamentals"], attr["market_conditions"]])
        assert total == 100, f"\u5f52\u4e00\u5316\u540e\u603b\u548c\u5e94\u4e3a 100: {total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
