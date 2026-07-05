# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Schema parsing and fallback tests
===================================

Tests for AnalysisReportSchema validation and analyzer fallback behavior.
"""

import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mock litellm before importing analyzer (optional runtime dep)
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.schemas.report_schema import AnalysisReportSchema
from src.analyzer import GeminiAnalyzer, AnalysisResult


class TestAnalysisReportSchema(unittest.TestCase):
    """Schema parsing tests."""

    def test_valid_dashboard_parses(self) -> None:
        """Valid LLM-like JSON parses successfully."""
        data = {
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": 75,
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u6301\u6709",
            "decision_type": "hold",
            "confidence_level": "\u4e2d",
            "dashboard": {
                "core_conclusion": {"one_sentence": "\u6301\u6709\u89c2\u671b"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110\u5143"}},
            },
            "analysis_summary": "\u57fa\u672c\u9762\u7a33\u5065",
        }
        schema = AnalysisReportSchema.model_validate(data)
        self.assertEqual(schema.stock_name, "\u8d35\u5dde\u8305\u53f0")
        self.assertEqual(schema.sentiment_score, 75)
        self.assertIsNotNone(schema.dashboard)

    def test_schema_allows_optional_fields_missing(self) -> None:
        """Schema accepts minimal valid structure."""
        data = {
            "stock_name": "\u6d4b\u8bd5",
            "sentiment_score": 50,
            "trend_prediction": "\u9707\u8361",
            "operation_advice": "\u89c2\u671b",
        }
        schema = AnalysisReportSchema.model_validate(data)
        self.assertIsNone(schema.dashboard)
        self.assertIsNone(schema.analysis_summary)

    def test_schema_accepts_phase_decision_and_defaults_lists(self) -> None:
        """Dashboard accepts the optional phase_decision contract."""
        data = {
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": 70,
            "trend_prediction": "\u9707\u8361",
            "operation_advice": "\u6301\u6709",
            "dashboard": {
                "core_conclusion": {"one_sentence": "\u7b49\u5f85\u786e\u8ba4"},
                "phase_decision": {
                    "phase_context": {"phase": "intraday", "market": "cn"},
                    "action_window": "\u76d8\u4e2d\u8ddf\u8e2a",
                    "immediate_action": "\u7b49\u5f85\u786e\u8ba4",
                    "next_check_time": "14:30",
                    "confidence_reason": "\u6570\u636e\u8d28\u91cf\u53ef\u7528",
                },
            },
        }

        schema = AnalysisReportSchema.model_validate(data)

        self.assertIsNotNone(schema.dashboard)
        phase_decision = schema.dashboard and schema.dashboard.phase_decision
        self.assertIsNotNone(phase_decision)
        if phase_decision:
            self.assertEqual(phase_decision.watch_conditions, [])
            self.assertEqual(phase_decision.data_limitations, [])
            self.assertEqual(phase_decision.phase_context["phase"], "intraday")

    def test_schema_allows_numeric_strings(self) -> None:
        """Schema accepts string values for numeric fields (LLM may return N/A)."""
        data = {
            "stock_name": "\u6d4b\u8bd5",
            "sentiment_score": 60,
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u4e70\u5165",
            "dashboard": {
                "data_perspective": {
                    "price_position": {
                        "current_price": "N/A",
                        "bias_ma5": "2.5",
                    }
                }
            },
        }
        schema = AnalysisReportSchema.model_validate(data)
        self.assertIsNotNone(schema.dashboard)
        pp = schema.dashboard and schema.dashboard.data_perspective and schema.dashboard.data_perspective.price_position
        self.assertIsNotNone(pp)
        if pp:
            self.assertEqual(pp.current_price, "N/A")
            self.assertEqual(pp.bias_ma5, "2.5")

    def test_schema_fails_on_invalid_sentiment_score(self) -> None:
        """Schema validation fails when sentiment_score out of range."""
        data = {
            "stock_name": "\u6d4b\u8bd5",
            "sentiment_score": 150,  # out of 0-100
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u4e70\u5165",
        }
        with self.assertRaises(Exception):
            AnalysisReportSchema.model_validate(data)


class TestAnalyzerSchemaFallback(unittest.TestCase):
    """Analyzer fallback when schema validation fails."""

    def test_parse_response_continues_when_schema_fails(self) -> None:
        """When schema validation fails, analyzer continues with raw dict."""
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": 150,  # invalid for schema
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u6301\u6709",
            "analysis_summary": "\u6d4b\u8bd5\u6458\u8981",
        })
        result = analyzer._parse_response(response, "600519", "\u8d35\u5dde\u8305\u53f0")
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.code, "600519")
        self.assertEqual(result.sentiment_score, 150)  # from raw dict
        self.assertTrue(result.success)

    def test_parse_response_valid_json_succeeds(self) -> None:
        """Valid JSON produces correct AnalysisResult."""
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": 72,
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u6301\u6709",
            "decision_type": "hold",
            "confidence_level": "\u9ad8",
            "analysis_summary": "\u6280\u672f\u9762\u5411\u597d",
        })
        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.name, "\u8d35\u5dde\u8305\u53f0")
        self.assertEqual(result.sentiment_score, 72)
        self.assertEqual(result.analysis_summary, "\u6280\u672f\u9762\u5411\u597d")
        self.assertEqual(result.action, "hold")
        self.assertEqual(result.action_label, "\u6301\u6709")

    def test_parse_response_preserves_explicit_action_in_raw_result(self) -> None:
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": 58,
            "trend_prediction": "\u9707\u8361",
            "operation_advice": "\u6301\u6709\u89c2\u5bdf",
            "decision_type": "hold",
            "action": "watch",
            "analysis_summary": "\u7b49\u5f85\u786e\u8ba4",
        })

        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")
        raw_result = result.to_dict()

        self.assertEqual(result.action, "watch")
        self.assertEqual(result.action_label, "\u89c2\u671b")
        self.assertEqual(result.decision_type, "hold")
        self.assertEqual(raw_result["action"], "watch")
        self.assertEqual(raw_result["action_label"], "\u89c2\u671b")

    def test_parse_response_keeps_unknown_dashboard_fields(self) -> None:
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": 72,
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u6301\u6709",
            "decision_type": "hold",
            "analysis_summary": "\u6280\u672f\u9762\u5411\u597d",
            "dashboard": {
                "core_conclusion": {
                    "one_sentence": "\u5148\u89c2\u5bdf",
                    "signal_type": "🟡\u6301\u6709\u89c2\u671b",
                },
                "decision_stability": {
                    "applied": True,
                    "reason": "\u56de\u6d4b\u9a8c\u8bc1",
                },
            },
        })
        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")
        self.assertEqual(result.dashboard["decision_stability"]["applied"], True)
        self.assertEqual(result.dashboard["decision_stability"]["reason"], "\u56de\u6d4b\u9a8c\u8bc1")

    def test_parse_response_repairs_single_json_candidate(self) -> None:
        analyzer = GeminiAnalyzer()
        response = """```json
{
  "stock_name": "\u8d35\u5dde\u8305\u53f0",
  "sentiment_score": 68,
  "trend_prediction": "\u770b\u591a",
  "operation_advice": "\u6301\u6709",
}
```"""

        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")

        self.assertTrue(result.success)
        self.assertEqual(result.name, "\u8d35\u5dde\u8305\u53f0")
        self.assertEqual(result.sentiment_score, 68)

    def test_parse_response_accepts_single_generic_json_fence(self) -> None:
        analyzer = GeminiAnalyzer()
        response = """```
{
  "stock_name": "\u8d35\u5dde\u8305\u53f0",
  "sentiment_score": 67,
  "trend_prediction": "\u770b\u591a",
  "operation_advice": "\u6301\u6709",
  "analysis_summary": "\u6280\u672f\u9762\u5411\u597d"
}
```"""

        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")

        self.assertTrue(result.success)
        self.assertEqual(result.name, "\u8d35\u5dde\u8305\u53f0")
        self.assertEqual(result.sentiment_score, 67)

    def test_parse_response_repairs_nested_single_json_candidate(self) -> None:
        analyzer = GeminiAnalyzer()
        response = """```json
{
  "stock_name": "\u8d35\u5dde\u8305\u53f0",
  "sentiment_score": 69,
  "trend_prediction": "\u770b\u591a",
  "operation_advice": "\u6301\u6709",
  "dashboard": {"core_conclusion": {"one_sentence": "\u7ee7\u7eed\u89c2\u5bdf",},},
}
```"""

        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")

        self.assertTrue(result.success)
        self.assertEqual(result.sentiment_score, 69)
        self.assertEqual(result.dashboard["core_conclusion"]["one_sentence"], "\u7ee7\u7eed\u89c2\u5bdf")

    def test_validate_json_response_accepts_single_generic_json_fence(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        analyzer._validate_json_response("""```
{
  "stock_name": "\u8d35\u5dde\u8305\u53f0",
  "sentiment_score": 66,
  "trend_prediction": "\u770b\u591a",
  "operation_advice": "\u6301\u6709",
  "analysis_summary": "\u6280\u672f\u9762\u5411\u597d"
}
```""")

    def test_validate_json_response_accepts_single_json_fence(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        analyzer._validate_json_response("""```json
{
  "stock_name": "\u8d35\u5dde\u8305\u53f0",
  "sentiment_score": 65,
  "trend_prediction": "\u770b\u591a",
  "operation_advice": "\u6301\u6709",
  "analysis_summary": "\u6280\u672f\u9762\u5411\u597d"
}
```""")

    def test_validate_json_response_rejects_ambiguous_json_before_repair(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        with self.assertRaises(Exception) as context:
            analyzer._validate_json_response('{"sentiment_score": 70} {"sentiment_score": 80}')

        self.assertEqual(getattr(context.exception, "details", {}).get("reason"), "ambiguous_json")

    def test_validate_json_response_rejects_generic_fence_with_outside_text(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        with self.assertRaises(Exception) as context:
            analyzer._validate_json_response("""Here is the JSON:
```
{"sentiment_score": 70, "trend_prediction": "\u770b\u591a"}
```""")

        self.assertEqual(getattr(context.exception, "details", {}).get("reason"), "ambiguous_json")

    def test_validate_json_response_rejects_multiple_json_fences(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        with self.assertRaises(Exception) as context:
            analyzer._validate_json_response("""```json
{"sentiment_score": 70}
```
```json
{"sentiment_score": 80}
```""")

        self.assertEqual(getattr(context.exception, "details", {}).get("reason"), "ambiguous_json")

    def test_validate_json_response_rejects_non_json_language_fence(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        with self.assertRaises(Exception) as context:
            analyzer._validate_json_response("""```text
{"sentiment_score": 70, "trend_prediction": "\u770b\u591a"}
```""")

        self.assertEqual(getattr(context.exception, "details", {}).get("reason"), "ambiguous_json")

    def test_validate_json_response_rejects_missing_minimal_contract(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        with self.assertRaises(Exception) as context:
            analyzer._validate_json_response('{"stock_name": "\u8d35\u5dde\u8305\u53f0"}')

        self.assertEqual(getattr(context.exception, "details", {}).get("reason"), "minimal_contract_failed")

    def test_validate_json_response_rejects_parser_unconstructable_sentiment(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._config_override = SimpleNamespace(generation_backend="litellm")

        with self.assertRaises(Exception) as context:
            analyzer._validate_json_response(json.dumps({
                "stock_name": "\u8d35\u5dde\u8305\u53f0",
                "sentiment_score": "not-a-number",
                "trend_prediction": "\u770b\u591a",
                "operation_advice": "\u6301\u6709",
                "analysis_summary": "\u6d4b\u8bd5\u6458\u8981",
            }))

        self.assertEqual(getattr(context.exception, "details", {}).get("reason"), "parser_contract_failed")

    def test_parse_response_falls_back_when_parser_contract_fails(self) -> None:
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "sentiment_score": "not-a-number",
            "trend_prediction": "\u770b\u591a",
            "operation_advice": "\u6301\u6709",
            "analysis_summary": "\u6d4b\u8bd5\u6458\u8981",
        })

        result = analyzer._parse_response(response, "600519", "\u80a1\u7968600519")

        self.assertFalse(result.success)
        self.assertEqual(result.sentiment_score, 50)
        self.assertIn("JSON", result.error_message)

    def test_parse_text_response_honors_injected_runtime_report_language(self) -> None:
        """Fallback text parsing should use the analyzer's injected config, not the global singleton."""
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(config=SimpleNamespace(report_language="en"))

        result = analyzer._parse_text_response("bullish buy setup", "AAPL", "Apple")

        self.assertEqual(result.report_language, "en")
        self.assertEqual(result.trend_prediction, "Bullish")
        self.assertEqual(result.operation_advice, "Buy")
        self.assertEqual(result.confidence_level, "Low")
