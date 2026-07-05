# -*- coding: utf-8 -*-
"""Tests for market strategy blueprints."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.market_strategy import get_market_strategy_blueprint
from src.market_analyzer import MarketAnalyzer, MarketOverview


class TestMarketStrategyBlueprint(unittest.TestCase):
    """Validate CN/US strategy blueprint basics."""

    def test_cn_blueprint_contains_action_framework(self):
        blueprint = get_market_strategy_blueprint("cn")
        block = blueprint.to_prompt_block()

        self.assertIn("A\u80a1\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565", block)
        self.assertIn("Action Framework", block)
        self.assertIn("\u8fdb\u653b", block)

    def test_us_blueprint_contains_regime_strategy(self):
        blueprint = get_market_strategy_blueprint("us")
        block = blueprint.to_prompt_block()

        self.assertIn("US Market Regime Strategy", block)
        self.assertIn("Risk-on", block)
        self.assertIn("Macro & Flows", block)


class TestMarketAnalyzerStrategyPrompt(unittest.TestCase):
    """Validate strategy section is injected into prompt/report."""

    def test_cn_prompt_contains_strategy_plan_section(self):
        analyzer = MarketAnalyzer(region="cn")
        prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

        self.assertIn("\u660e\u65e5\u4ea4\u6613\u8ba1\u5212", prompt)
        self.assertIn("A\u80a1\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565", prompt)

    def test_us_prompt_contains_strategy_plan_section(self):
        with patch("src.market_analyzer.get_config", return_value=SimpleNamespace(report_language="en")):
            analyzer = MarketAnalyzer(region="us")

        prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

        self.assertIn("Strategy Plan", prompt)
        self.assertIn("US Market Regime Strategy", prompt)

    def test_jp_kr_prompt_uses_region_aware_english_shell(self):
        cases = [
            ("jp", "Japan market"),
            ("kr", "Korea market"),
        ]

        for region, market_scope_name in cases:
            with self.subTest(region=region), patch(
                "src.market_analyzer.get_config",
                return_value=SimpleNamespace(report_language="en"),
            ):
                analyzer = MarketAnalyzer(region=region)
                prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

            self.assertIn(f"professional {market_scope_name} analyst", prompt)
            self.assertIn("## Data Limits", prompt)
            self.assertIn("### 3. News Catalysts", prompt)
            self.assertNotIn("### 3. Fund Flows", prompt)
            self.assertNotIn("### 4. Sector Highlights", prompt)
            self.assertNotIn("Interpret what turnover, participation, and flow signals imply", prompt)
            self.assertNotIn("professional US/A/H market analyst", prompt)

    def test_us_prompt_localizes_strategy_markdown_when_report_language_is_zh(self):
        with patch("src.market_analyzer.get_config", return_value=SimpleNamespace(report_language="zh")):
            analyzer = MarketAnalyzer(region="us")

        prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

        self.assertIn("\u7f8e\u80a1\u5e02\u573a", prompt)
        self.assertNotIn("US Market Regime Strategy", prompt)
        self.assertNotIn("Strategy Blueprint", prompt)
        self.assertIn("\u98ce\u9669\u504f\u597d", prompt)

    def test_jp_kr_prompt_uses_region_aware_chinese_shell(self):
        cases = [
            ("jp", "\u65e5\u672c\u5e02\u573a", "\u65e5\u672c\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565"),
            ("kr", "\u97e9\u56fd\u5e02\u573a", "\u97e9\u56fd\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565"),
        ]

        for region, market_scope_name, strategy_title in cases:
            with self.subTest(region=region), patch(
                "src.market_analyzer.get_config",
                return_value=SimpleNamespace(report_language="zh"),
            ):
                analyzer = MarketAnalyzer(region=region)
                prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

            self.assertIn(f"\u4e13\u4e1a\u7684{market_scope_name}\u5206\u6790\u5e08", prompt)
            self.assertIn(f"\u7ed3\u6784\u5316\u7684{market_scope_name}\u5927\u76d8\u590d\u76d8\u62a5\u544a", prompt)
            self.assertIn(f"## 2026-02-24 {market_scope_name}\u5927\u76d8\u590d\u76d8", prompt)
            self.assertIn("## \u6570\u636e\u8fb9\u754c", prompt)
            self.assertIn("### \u4e09、\u6d88\u606f\u50ac\u5316", prompt)
            self.assertIn(strategy_title, prompt)
            self.assertNotIn("### \u4e09、\u677f\u5757\u4e3b\u7ebf", prompt)
            self.assertNotIn("### \u56db、\u8d44\u91d1\u4e0e\u60c5\u7eea", prompt)
            self.assertNotIn("\u89e3\u8bfb\u6210\u4ea4\u989d、\u6da8\u8dcc\u505c\u7ed3\u6784、\u5e02\u573a\u5bbd\u5ea6", prompt)
            self.assertNotIn("A/H/\u7f8e\u80a1\u5e02\u573a\u5206\u6790\u5e08", prompt)

    def test_cn_prompt_uses_english_shell_when_report_language_is_en(self):
        with patch("src.market_analyzer.get_config", return_value=SimpleNamespace(report_language="en")):
            analyzer = MarketAnalyzer(region="cn")

        prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

        self.assertIn("# Today's Market Data", prompt)
        self.assertIn("### 1. Market Summary", prompt)
        self.assertIn("A-share Three-Phase Recap Strategy", prompt)
        self.assertNotIn("### \u4e00、\u5e02\u573a\u603b\u7ed3", prompt)
        self.assertNotIn("A\u80a1\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565", prompt)

    def test_jp_kr_strategy_blocks_are_localized_when_report_language_is_en(self):
        cases = [
            ("jp", "Japan Market Regime Strategy", "Macro & FX", "\u65e5\u672c\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565"),
            ("kr", "Korea Market Regime Strategy", "Technology Cycle", "\u97e9\u56fd\u5e02\u573a\u4e09\u6bb5\u5f0f\u590d\u76d8\u7b56\u7565"),
        ]

        for region, title, dimension, chinese_title in cases:
            with self.subTest(region=region):
                with patch(
                    "src.market_analyzer.get_config",
                    return_value=SimpleNamespace(report_language="en"),
                ):
                    analyzer = MarketAnalyzer(region=region)

                prompt_block = analyzer._get_strategy_prompt_block()
                markdown_block = analyzer._get_strategy_markdown_block("en")

                self.assertIn(title, prompt_block)
                self.assertIn(dimension, prompt_block)
                self.assertNotIn(chinese_title, prompt_block)
                self.assertNotIn("\u53ea\u57fa\u4e8e\u53ef\u5f97\u6307\u6570", prompt_block)
                self.assertIn("### 6. Strategy Framework", markdown_block)
                self.assertIn(dimension, markdown_block)
                self.assertNotIn("### \u516d、\u7b56\u7565\u6846\u67b6", markdown_block)

    def test_jp_kr_review_prompt_roles_are_market_aware(self):
        cases = [
            ("jp", "Japan market", "\u65e5\u672c\u5e02\u573a"),
            ("kr", "Korea market", "\u97e9\u56fd\u5e02\u573a"),
        ]

        for region, english_market, chinese_market in cases:
            with self.subTest(region=region, language="en"):
                with patch(
                    "src.market_analyzer.get_config",
                    return_value=SimpleNamespace(report_language="en"),
                ):
                    analyzer = MarketAnalyzer(region=region)

                prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

                self.assertIn(
                    f"You are a professional {english_market} analyst.",
                    prompt,
                )
                self.assertNotIn("US/A/H market analyst", prompt)

            with self.subTest(region=region, language="zh"):
                with patch(
                    "src.market_analyzer.get_config",
                    return_value=SimpleNamespace(report_language="zh"),
                ):
                    analyzer = MarketAnalyzer(region=region)

                prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

                self.assertIn(f"\u4f60\u662f\u4e00\u4f4d\u4e13\u4e1a\u7684{chinese_market}\u5206\u6790\u5e08", prompt)
                self.assertNotIn("A/H/\u7f8e\u80a1\u5e02\u573a\u5206\u6790\u5e08", prompt)

    def test_market_stats_passes_market_review_purpose(self):
        analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
        analyzer.region = "hk"
        analyzer.data_manager = MagicMock()
        analyzer.data_manager.get_market_stats.return_value = {
            "up_count": 3,
            "down_count": 2,
            "flat_count": 1,
            "limit_up_count": 0,
            "limit_down_count": 0,
            "total_amount": 12.0,
        }
        overview = MarketOverview(date="2026-02-24")

        analyzer._get_market_statistics(overview)

        analyzer.data_manager.get_market_stats.assert_called_once_with(
            purpose="market_review:hk"
        )
        self.assertEqual(overview.up_count, 3)


if __name__ == "__main__":
    unittest.main()
