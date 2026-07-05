# -*- coding: utf-8 -*-
"""Tests for analyzer news prompt hard constraints (Issue #697)."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    from tests.litellm_stub import ensure_litellm_stub

    ensure_litellm_stub()

from src.analyzer import (
    GeminiAnalyzer,
    _BULLISH_TREND_HINTS,
    _contains_trend_hint,
    _infer_trend_direction,
    _sanitize_trend_analysis_for_prompt,
)


class AnalyzerNewsPromptTestCase(unittest.TestCase):
    def test_contains_trend_hint_treats_non_adjacent_negation_as_negated(self) -> None:
        self.assertFalse(_contains_trend_hint("\u5c1a\u672a\u5f62\u6210\u4e0a\u5347\u8d8b\u52bf，\u7ee7\u7eed\u89c2\u5bdf。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u672a\u5f62\u6210\u4e0a\u5347\u8d8b\u52bf，\u7ee7\u7eed\u89c2\u5bdf。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u5e76\u672a\u5f62\u6210\u4e0a\u5347\u8d8b\u52bf，\u7ee7\u7eed\u89c2\u5bdf。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u6ca1\u6709\u5f62\u6210\u591a\u5934\u6392\u5217，\u7ee7\u7eed\u89c2\u5bdf。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u5f53\u524d\u65e0\u591a\u5934\u6392\u5217，\u4ecd\u9700\u89c2\u5bdf。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u5c1a\u4e0d\u5c5e\u4e8e\u4e0a\u5347\u8d8b\u52bf，\u53cd\u5f39\u4ecd\u5f85\u786e\u8ba4。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u5f53\u524d\u975e\u591a\u5934\u6392\u5217，\u4ecd\u9700\u89c2\u5bdf。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("This is not a bullish trend yet.", _BULLISH_TREND_HINTS))

    def test_contains_trend_hint_scans_later_non_negated_occurrences(self) -> None:
        self.assertTrue(
            _contains_trend_hint(
                "\u4e0d\u662f\u591a\u5934\u6392\u5217，\u540e\u7eed\u653e\u91cf\u540e\u518d\u6b21\u51fa\u73b0\u591a\u5934\u6392\u5217\u4fe1\u53f7。",
                _BULLISH_TREND_HINTS,
            )
        )

    def test_contains_trend_hint_keeps_contrast_clause_target_hint(self) -> None:
        self.assertTrue(_contains_trend_hint("\u4e0d\u662f\u7a7a\u5934\u800c\u662f\u591a\u5934\u6392\u5217，\u8d8b\u52bf\u4fee\u590d。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("\u672a\u8f6c\u4e3a\u4e0a\u5347\u8d8b\u52bf，\u53cd\u5f39\u4ecd\u5f85\u786e\u8ba4。", _BULLISH_TREND_HINTS))

    def test_contains_trend_hint_ignores_single_character_prefixes_in_common_words(self) -> None:
        self.assertTrue(_contains_trend_hint("\u975e\u5e38\u660e\u663e\u7684\u591a\u5934\u6392\u5217，\u8d8b\u52bf\u4ecd\u5728\u5ef6\u7eed。", _BULLISH_TREND_HINTS))
        self.assertTrue(_contains_trend_hint("\u672a\u6765\u4e0a\u5347\u8d8b\u52bf\u82e5\u653e\u91cf\u5c06\u8fdb\u4e00\u6b65\u786e\u8ba4。", _BULLISH_TREND_HINTS))
        self.assertEqual(
            _infer_trend_direction({"trend_status": "\u975e\u5e38\u660e\u663e\u7684\u591a\u5934\u6392\u5217", "ma_alignment": "\u672a\u6765\u4e0a\u5347\u8d8b\u52bf\u9010\u6b65\u660e\u786e"}),
            "bullish",
        )

    def test_infer_trend_direction_recognizes_weak_bullish_and_bearish_states(self) -> None:
        self.assertEqual(
            _infer_trend_direction({"trend_status": "\u5f31\u52bf\u591a\u5934", "ma_alignment": "\u5f31\u52bf\u591a\u5934，MA5>MA10 \u4f46 MA10≤MA20"}),
            "bullish",
        )
        self.assertEqual(
            _infer_trend_direction({"trend_status": "\u5f31\u52bf\u7a7a\u5934", "ma_alignment": "\u5f31\u52bf\u7a7a\u5934，MA5<MA10 \u4f46 MA10≥MA20"}),
            "bearish",
        )

    def test_infer_trend_direction_ignores_negated_bullish_hints(self) -> None:
        self.assertEqual(
            _infer_trend_direction({"trend_status": "\u672a\u5f62\u6210\u4e0a\u5347\u8d8b\u52bf", "ma_alignment": "\u5f53\u524d\u975e\u591a\u5934\u6392\u5217"}),
            "neutral",
        )
        self.assertEqual(
            _infer_trend_direction({"trend_status": "\u6ca1\u6709\u5f62\u6210\u591a\u5934\u6392\u5217", "ma_alignment": "\u5f53\u524d\u65e0\u4e0a\u5347\u8d8b\u52bf"}),
            "neutral",
        )

    def test_infer_trend_direction_keeps_contrast_clause_final_direction(self) -> None:
        self.assertEqual(
            _infer_trend_direction({"trend_status": "\u4e0d\u662f\u7a7a\u5934\u800c\u662f\u591a\u5934\u6392\u5217", "ma_alignment": ""}),
            "bullish",
        )

    def test_analysis_prompt_resolves_shared_skill_prompt_state_by_default(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        fake_state = SimpleNamespace(
            skill_instructions="### \u6280\u80fd 1: \u6ce2\u6bb5\u4f4e\u5438\n- \u5173\u6ce8\u652f\u6491\u786e\u8ba4",
            default_skill_policy="",
        )
        with patch("src.agent.factory.resolve_skill_prompt_state", return_value=fake_state):
            prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

        self.assertIn("### \u6280\u80fd 1: \u6ce2\u6bb5\u4f4e\u5438", prompt)
        self.assertNotIn("\u4e13\u6ce8\u4e8e\u8d8b\u52bf\u4ea4\u6613", prompt)

    def test_analysis_prompt_uses_injected_skill_sections_instead_of_hardcoded_trend_baseline(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### \u6280\u80fd 1: \u7f20\u8bba\n- \u5173\u6ce8\u4e2d\u67a2\u4e0e\u80cc\u9a70",
                default_skill_policy="",
            )

        prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

        self.assertIn("### \u6280\u80fd 1: \u7f20\u8bba", prompt)
        self.assertNotIn("\u4e13\u6ce8\u4e8e\u8d8b\u52bf\u4ea4\u6613", prompt)
        self.assertNotIn("\u591a\u5934\u6392\u5217：MA5 > MA10 > MA20", prompt)

    def test_analysis_prompt_keeps_injected_default_policy_for_implicit_default_run(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### \u6280\u80fd 1: \u9ed8\u8ba4\u591a\u5934\u8d8b\u52bf",
                default_skill_policy="## \u9ed8\u8ba4\u6280\u80fd\u57fa\u7ebf（\u5fc5\u987b\u4e25\u683c\u9075\u5b88）\n- **\u591a\u5934\u6392\u5217\u5fc5\u987b\u6761\u4ef6**：MA5 > MA10 > MA20",
                use_legacy_default_prompt=True,
            )

        prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

        self.assertIn("\u4e13\u6ce8\u4e8e\u8d8b\u52bf\u4ea4\u6613", prompt)
        self.assertIn("\u591a\u5934\u6392\u5217\u5fc5\u987b\u6761\u4ef6", prompt)
        self.assertIn("\u591a\u5934\u6392\u5217：MA5 > MA10 > MA20", prompt)

    def test_analysis_prompt_requires_phase_decision_in_main_and_legacy_modes(self) -> None:
        for legacy in (False, True):
            with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
                analyzer = GeminiAnalyzer(
                    skill_instructions="",
                    default_skill_policy="",
                    use_legacy_default_prompt=legacy,
                )

            prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

            self.assertIn('"phase_decision"', prompt)
            self.assertIn('"watch_conditions"', prompt)
            self.assertIn('"data_limitations"', prompt)
            self.assertIn("quote/daily_bars/technical \u5b58\u5728 stale、fallback、missing、fetch_failed、partial \u6216 estimated", prompt)
            self.assertIn("`confidence_level` \u4e0d\u5f97\u4e3a\u9ad8", prompt)

    def test_analysis_prompt_contains_actionability_guardrails(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        prompt = analyzer._get_analysis_system_prompt("zh", stock_code="002812")

        self.assertIn("\u53ef\u64cd\u4f5c\u6027\u4e0e\u7a33\u5b9a\u6027\u7ea6\u675f", prompt)
        self.assertIn("\u4e0d\u5f97\u4ec5\u56e0\u4e3a\u5355\u65e5\u6da8\u8dcc", prompt)
        self.assertIn("\u652f\u6491/\u538b\u529b\u4f4d", prompt)
        self.assertIn("\u6d17\u76d8\u89c2\u5bdf", prompt)

    def test_analysis_prompt_score_scale_splits_reduce_and_sell_bands(self) -> None:
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
                    analyzer = GeminiAnalyzer(
                        skill_instructions="",
                        default_skill_policy="",
                        use_legacy_default_prompt=legacy,
                    )

                prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

                self.assertIn("### \u51cf\u4ed3（20-39\u5206）", prompt)
                self.assertIn("### \u5356\u51fa（0-19\u5206）", prompt)
                self.assertIn("20-39：\u51cf\u4ed3，`action=reduce`，`decision_type=sell`。", prompt)
                self.assertIn("0-19：\u5356\u51fa，`action=sell`，`decision_type=sell`。", prompt)
                self.assertNotIn("### \u5356\u51fa/\u51cf\u4ed3（0-39\u5206）", prompt)

    def test_prompt_contains_time_constraints(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-16",
            "today": {},
            "fundamental_context": {
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_cash_dividend_per_share": 1.2, "ttm_dividend_yield_pct": 2.4},
                    }
                }
            },
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="medium",  # 7 days
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context="news")

        self.assertIn("\u8fd17\u65e5\u7684\u65b0\u95fb\u641c\u7d22\u7ed3\u679c", prompt)
        self.assertIn("\u6bcf\u4e00\u6761\u90fd\u5fc5\u987b\u5e26\u5177\u4f53\u65e5\u671f（YYYY-MM-DD）", prompt)
        self.assertIn("\u8d85\u51fa\u8fd17\u65e5\u7a97\u53e3\u7684\u65b0\u95fb\u4e00\u5f8b\u5ffd\u7565", prompt)
        self.assertIn("\u65f6\u95f4\u672a\u77e5、\u65e0\u6cd5\u786e\u5b9a\u53d1\u5e03\u65e5\u671f\u7684\u65b0\u95fb\u4e00\u5f8b\u5ffd\u7565", prompt)
        self.assertIn("\u8d22\u62a5\u4e0e\u5206\u7ea2（\u4ef7\u503c\u6295\u8d44\u53e3\u5f84）", prompt)
        self.assertIn("\u7981\u6b62\u7f16\u9020", prompt)

    def test_prompt_includes_capital_flow_as_operation_filter(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "002812",
            "stock_name": "\u6069\u6377\u80a1\u4efd",
            "date": "2026-04-01",
            "today": {"close": 32.8, "ma5": 31.2, "ma10": 30.5, "ma20": 29.8},
            "fundamental_context": {
                "capital_flow": {
                    "status": "ok",
                    "data": {
                        "stock_flow": {
                            "main_net_inflow": -1200000,
                            "inflow_5d": -3600000,
                            "inflow_10d": -5200000,
                        },
                        "sector_rankings": {
                            "top": [{"name": "\u7535\u6c60"}],
                            "bottom": [{"name": "\u5316\u5de5"}],
                        },
                    },
                }
            },
        }

        prompt = analyzer._format_prompt(context, "\u6069\u6377\u80a1\u4efd", news_context=None)

        self.assertIn("\u4e3b\u529b\u8d44\u91d1\u6d41\u5411（\u64cd\u4f5c\u5efa\u8bae\u8fc7\u6ee4\u5668）", prompt)
        self.assertIn("\u4e3b\u529b\u51c0\u6d41\u5165", prompt)
        self.assertIn("-1200000", prompt)
        self.assertIn("\u63a5\u8fd1\u538b\u529b\u4e14\u4e3b\u529b\u6d41\u51fa\u65f6\u4e0d\u5f97\u8ffd\u4e70", prompt)
        self.assertIn("\u6d17\u76d8\u89c2\u5bdf", prompt)

    def test_prompt_prefers_context_news_window_days(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-16",
            "today": {},
            "news_window_days": 1,
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="long",  # 30 days if fallback is used
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context="news")

        self.assertIn("\u8fd11\u65e5\u7684\u65b0\u95fb\u641c\u7d22\u7ed3\u679c", prompt)
        self.assertIn("\u8d85\u51fa\u8fd11\u65e5\u7a97\u53e3\u7684\u65b0\u95fb\u4e00\u5f8b\u5ffd\u7565", prompt)

    def test_format_prompt_injects_market_phase_and_pack_summary_before_technical_data(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-27",
            "today": {},
            "market_phase_context": {
                "market": "cn",
                "phase": "premarket",
                "market_local_time": "2026-03-27T09:00:00+08:00",
                "effective_daily_bar_date": "2026-03-26",
                "is_partial_bar": False,
                "minutes_to_open": 30,
                "warnings": [],
            },
        }

        prompt = analyzer._format_prompt(
            context,
            "\u8d35\u5dde\u8305\u53f0",
            news_context=None,
            analysis_context_pack_summary="\n## \u5206\u6790\u4e0a\u4e0b\u6587\u5305\u6458\u8981\n- \u6570\u636e\u5757\u72b6\u6001：\u884c\u60c5 available\n",
        )

        phase_index = prompt.index("\u5e02\u573a\u9636\u6bb5\u4e0a\u4e0b\u6587")
        pack_index = prompt.index("\u5206\u6790\u4e0a\u4e0b\u6587\u5305\u6458\u8981")
        technical_index = prompt.index("\u6280\u672f\u9762\u6570\u636e")
        self.assertLess(phase_index, technical_index)
        self.assertLess(phase_index, pack_index)
        self.assertLess(pack_index, technical_index)
        self.assertIn("\u76d8\u524d", prompt)
        self.assertIn("\u4e0d\u5f97\u63cf\u8ff0“\u4eca\u65e5\u8d70\u52bf\u5df2\u7ecf\u53d1\u751f”", prompt)

    def test_format_prompt_omits_market_phase_section_without_context(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-27",
            "today": {},
        }

        prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

        self.assertNotIn("\u5e02\u573a\u9636\u6bb5\u4e0a\u4e0b\u6587", prompt)
        self.assertNotIn("\u5206\u6790\u4e0a\u4e0b\u6587\u5305\u6458\u8981", prompt)

    def test_format_prompt_labels_intraday_partial_quote_as_estimated(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-27",
            "today": {"close": 1880.0},
            "market_phase_context": {
                "phase": "intraday",
                "is_partial_bar": True,
                "warnings": [],
            },
        }

        prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

        self.assertIn("### \u6700\u65b0\u884c\u60c5", prompt)
        self.assertIn("| \u76d8\u4e2d\u4f30\u7b97\u4ef7 | 1880.0 \u5143 |", prompt)
        self.assertNotIn("### \u4eca\u65e5\u884c\u60c5", prompt)
        self.assertNotIn("| \u6536\u76d8\u4ef7 | 1880.0 \u5143 |", prompt)

    def test_format_prompt_uses_complete_daily_labels_for_premarket_and_non_trading(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        for phase in ("premarket", "non_trading"):
            context = {
                "code": "600519",
                "stock_name": "\u8d35\u5dde\u8305\u53f0",
                "date": "2026-03-27",
                "today": {
                    "close": 1870.0,
                    "open": 1860.0,
                    "high": 1880.0,
                    "low": 1855.0,
                },
                "market_phase_context": {
                    "phase": phase,
                    "is_partial_bar": False,
                    "warnings": [],
                },
            }

            prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

            self.assertIn("### \u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5\u884c\u60c5", prompt)
            self.assertIn("| \u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5\u6536\u76d8\u4ef7 | 1870.0 \u5143 |", prompt)
            self.assertIn("| \u5f00\u76d8\u4ef7 | 1860.0 \u5143 |", prompt)
            self.assertIn("| \u6700\u9ad8\u4ef7 | 1880.0 \u5143 |", prompt)
            self.assertIn("| \u6700\u4f4e\u4ef7 | 1855.0 \u5143 |", prompt)
            self.assertNotIn("### \u4eca\u65e5\u884c\u60c5", prompt)
            self.assertNotIn("| \u6536\u76d8\u4ef7 | 1870.0 \u5143 |", prompt)

    def test_format_prompt_does_not_label_realtime_overlay_as_previous_close(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        for phase in ("premarket", "non_trading"):
            context = {
                "code": "600519",
                "stock_name": "\u8d35\u5dde\u8305\u53f0",
                "date": "2026-03-27",
                "today": {
                    "close": 1882.5,
                    "open": 1878.0,
                    "high": 1885.0,
                    "low": 1876.0,
                    "pct_chg": 0.42,
                    "volume": 1200000,
                    "amount": 226000000,
                    "data_source": "realtime:tencent",
                    "is_estimated": True,
                    "estimated_fields": ["close", "open", "high", "low"],
                },
                "market_phase_context": {
                    "phase": phase,
                    "is_partial_bar": False,
                    "warnings": [],
                },
            }

            prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

            self.assertIn("### \u6700\u65b0\u884c\u60c5", prompt)
            self.assertIn("| \u5b9e\u65f6\u4f30\u7b97\u4ef7 | 1882.5 \u5143 |", prompt)
            self.assertNotIn("### \u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5\u884c\u60c5", prompt)
            self.assertNotIn("| \u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5\u6536\u76d8\u4ef7 | 1882.5 \u5143 |", prompt)
            self.assertNotIn("| \u5f00\u76d8\u4ef7 |", prompt)
            self.assertNotIn("| \u6700\u9ad8\u4ef7 |", prompt)
            self.assertNotIn("| \u6700\u4f4e\u4ef7 |", prompt)
            self.assertIn("| \u5b9e\u65f6\u6da8\u8dcc\u5e45 | 0.42% |", prompt)
            self.assertIn("| \u5b9e\u65f6\u6210\u4ea4\u91cf | 120.00 \u4e07\u80a1 |", prompt)
            self.assertIn("| \u5b9e\u65f6\u6210\u4ea4\u989d | 2.26 \u4ebf\u5143 |", prompt)
            self.assertNotIn("| \u6da8\u8dcc\u5e45 | 0.42% |", prompt)
            self.assertNotIn("| \u6210\u4ea4\u91cf | 120.00 \u4e07\u80a1 |", prompt)
            self.assertNotIn("| \u6210\u4ea4\u989d | 2.26 \u4ebf\u5143 |", prompt)

    def test_format_prompt_does_not_label_date_mismatch_as_previous_close(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-27",
            "today": {
                "close": 1882.5,
                "open": 1878.0,
                "high": 1885.0,
                "low": 1876.0,
                "date": "2026-03-27",
            },
            "market_phase_context": {
                "phase": "premarket",
                "effective_daily_bar_date": "2026-03-26",
                "is_partial_bar": False,
                "warnings": [],
            },
        }

        prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

        self.assertIn("### \u6700\u65b0\u884c\u60c5", prompt)
        self.assertIn("| \u6700\u65b0\u4ef7 | 1882.5 \u5143 |", prompt)
        self.assertNotIn("### \u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5\u884c\u60c5", prompt)
        self.assertNotIn("| \u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5\u6536\u76d8\u4ef7 | 1882.5 \u5143 |", prompt)
        self.assertNotIn("| \u5f00\u76d8\u4ef7 |", prompt)
        self.assertNotIn("| \u6700\u9ad8\u4ef7 |", prompt)
        self.assertNotIn("| \u6700\u4f4e\u4ef7 |", prompt)

    def test_format_prompt_keeps_legacy_quote_labels_without_partial_intraday_context(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        for phase_context in (
            {"phase": "intraday", "is_partial_bar": False, "warnings": []},
            {"phase": "intraday", "warnings": []},
            {"phase": "postmarket", "is_partial_bar": False, "warnings": []},
            {"phase": "unknown", "is_partial_bar": True, "warnings": []},
            None,
        ):
            context = {
                "code": "600519",
                "stock_name": "\u8d35\u5dde\u8305\u53f0",
                "date": "2026-03-27",
                "today": {"close": 1880.0},
            }
            if phase_context is not None:
                context["market_phase_context"] = phase_context

            prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

            self.assertIn("### \u4eca\u65e5\u884c\u60c5", prompt)
            self.assertIn("| \u6536\u76d8\u4ef7 | 1880.0 \u5143 |", prompt)

    def test_format_prompt_omits_legacy_trend_checks_for_nondefault_skill_mode(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### \u6280\u80fd 1: \u7f20\u8bba\n- \u5173\u6ce8\u4e2d\u67a2\u4e0e\u80cc\u9a70",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-03-16",
            "today": {"close": 100, "ma5": 99, "ma10": 98, "ma20": 97},
            "trend_analysis": {
                "trend_status": "\u9707\u8361\u504f\u5f3a",
                "ma_alignment": "\u7c98\u5408\u540e\u53d1\u6563",
                "trend_strength": 61,
                "bias_ma5": 1.2,
                "bias_ma10": 2.4,
                "volume_status": "\u5e73\u91cf",
                "volume_trend": "\u91cf\u80fd\u6e29\u548c",
                "buy_signal": "\u89c2\u5bdf",
                "signal_score": 58,
                "signal_reasons": ["\u7ed3\u6784\u5f85\u786e\u8ba4"],
                "risk_factors": ["\u65e0\u80cc\u9a70\u786e\u8ba4"],
            },
        }
        prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

        self.assertIn("\u5f53\u524d\u7ed3\u6784\u662f\u5426\u6ee1\u8db3\u6fc0\u6d3b\u6280\u80fd\u7684\u5173\u952e\u89e6\u53d1\u6761\u4ef6", prompt)
        self.assertNotIn("\u662f\u5426\u6ee1\u8db3 MA5>MA10>MA20 \u591a\u5934\u6392\u5217", prompt)
        self.assertNotIn("\u8d85\u8fc75%\u5fc5\u987b\u6807\u6ce8\"\u4e25\u7981\u8ffd\u9ad8\"", prompt)
        self.assertNotIn("MA5>MA10>MA20\u4e3a\u591a\u5934", prompt)

    def test_format_prompt_removes_bullish_reasons_when_final_trend_is_bearish(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### \u6280\u80fd 1: \u7f20\u8bba\n- \u5173\u6ce8\u4e2d\u67a2\u4e0e\u80cc\u9a70",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "603259",
            "stock_name": "\u836f\u660e\u5eb7\u5fb7",
            "date": "2026-04-28",
            "today": {"close": 58.6, "ma5": 57.2, "ma10": 58.8, "ma20": 60.4},
            "yesterday": {"close": 57.8},
            "volume_change_ratio": 12.4,
            "trend_analysis": {
                "trend_status": "\u7a7a\u5934\u6392\u5217",
                "ma_alignment": "\u7a7a\u5934\u6392\u5217 MA5<MA10<MA20",
                "trend_strength": 34,
                "bias_ma5": 2.1,
                "bias_ma10": -0.8,
                "volume_status": "\u653e\u91cf",
                "volume_trend": "\u653e\u91cf\u9707\u8361",
                "buy_signal": "\u89c2\u5bdf",
                "signal_score": 41,
                "signal_reasons": ["\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", "\u4e8b\u4ef6\u50ac\u5316\u5b58\u5728\u4f46\u6280\u672f\u5f85\u786e\u8ba4"],
                "risk_factors": ["\u8dcc\u7834MA20，\u8d8b\u52bf\u627f\u538b"],
            },
        }

        prompt = analyzer._format_prompt(
            context,
            "\u836f\u660e\u5eb7\u5fb7",
            news_context="2026-04-27 \u4e00\u5b63\u62a5\u8d85\u9884\u671f，\u8ba2\u5355\u589e\u957f。",
        )

        self.assertIn("\u7a7a\u5934\u6392\u5217 MA5<MA10<MA20", prompt)
        self.assertNotIn("\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", prompt)
        self.assertIn("\u4e8b\u4ef6\u50ac\u5316\u5b58\u5728\u4f46\u6280\u672f\u5f85\u786e\u8ba4", prompt)
        self.assertIn("\u4e8b\u4ef6\u5148\u884c、\u6280\u672f\u5f85\u786e\u8ba4", prompt)
        self.assertIn("\u91cf\u80fd\u5f02\u5e38\u63d0\u793a", prompt)
        self.assertIn("\u6280\u672f\u9762\u4e00\u81f4\u6027", prompt)

    def test_format_prompt_removes_bearish_risks_when_final_trend_is_bullish(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### \u6280\u80fd 1: \u7f20\u8bba\n- \u5173\u6ce8\u4e2d\u67a2\u4e0e\u80cc\u9a70",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "date": "2026-04-28",
            "today": {"close": 1688.0, "ma5": 1675.0, "ma10": 1660.0, "ma20": 1640.0},
            "trend_analysis": {
                "trend_status": "\u591a\u5934\u6392\u5217",
                "ma_alignment": "\u591a\u5934\u6392\u5217 MA5>MA10>MA20",
                "trend_strength": 78,
                "bias_ma5": 1.8,
                "bias_ma10": 3.2,
                "volume_status": "\u5e73\u91cf",
                "volume_trend": "\u91cf\u4ef7\u914d\u5408",
                "buy_signal": "\u504f\u5f3a",
                "signal_score": 73,
                "signal_reasons": ["\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", "\u7a7a\u5934\u6392\u5217，\u6301\u7eed\u4e0b\u8dcc"],
                "risk_factors": ["\u7a7a\u5934\u6392\u5217，\u6301\u7eed\u4e0b\u8dcc", "\u8d22\u62a5\u62ab\u9732\u524d\u6ce2\u52a8\u53ef\u80fd\u653e\u5927"],
            },
        }

        prompt = analyzer._format_prompt(context, "\u8d35\u5dde\u8305\u53f0", news_context=None)

        self.assertIn("\u591a\u5934\u6392\u5217 MA5>MA10>MA20", prompt)
        self.assertIn("\u8d22\u62a5\u62ab\u9732\u524d\u6ce2\u52a8\u53ef\u80fd\u653e\u5927", prompt)
        self.assertNotIn("\u7a7a\u5934\u6392\u5217，\u6301\u7eed\u4e0b\u8dcc\n", prompt)
        self.assertNotIn("\u7a7a\u5934\u6392\u5217，\u6301\u7eed\u4e0b\u8dcc", prompt)
        self.assertIn("\u5df2\u5254\u9664\u4e0e\u591a\u5934\u4e3b\u5224\u65ad\u76f4\u63a5\u51b2\u7a81\u7684\u7a7a\u5934\u7ed3\u6784\u7406\u7531", prompt)
        self.assertIn("\u5df2\u5254\u9664\u4e0e\u591a\u5934\u4e3b\u5224\u65ad\u76f4\u63a5\u51b2\u7a81\u7684\u7a7a\u5934\u7ed3\u6784\u98ce\u9669\u8868\u8ff0", prompt)

    def test_format_prompt_removes_bullish_reasons_when_final_trend_is_weak_bearish(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### \u6280\u80fd 1: \u7f20\u8bba\n- \u5173\u6ce8\u4e2d\u67a2\u4e0e\u80cc\u9a70",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "300750",
            "stock_name": "\u5b81\u5fb7\u65f6\u4ee3",
            "date": "2026-04-28",
            "today": {"close": 178.5, "ma5": 176.0, "ma10": 180.2, "ma20": 179.9},
            "trend_analysis": {
                "trend_status": "\u5f31\u52bf\u7a7a\u5934",
                "ma_alignment": "\u5f31\u52bf\u7a7a\u5934，MA5<MA10 \u4f46 MA10≥MA20",
                "trend_strength": 43,
                "bias_ma5": 1.4,
                "bias_ma10": -0.9,
                "volume_status": "\u5e73\u91cf",
                "volume_trend": "\u91cf\u80fd\u4e00\u822c",
                "buy_signal": "\u89c2\u5bdf",
                "signal_score": 45,
                "signal_reasons": ["\u5f31\u52bf\u591a\u5934\u4fee\u590d", "\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", "\u4e8b\u4ef6\u50ac\u5316\u5b58\u5728\u4f46\u6280\u672f\u5f85\u786e\u8ba4"],
                "risk_factors": ["MA10 \u538b\u5236\u4ecd\u5728"],
            },
        }

        prompt = analyzer._format_prompt(
            context,
            "\u5b81\u5fb7\u65f6\u4ee3",
            news_context="2026-04-27 \u65b0\u4ea7\u54c1\u53d1\u5e03，\u5e02\u573a\u60c5\u7eea\u56de\u6696。",
        )

        self.assertIn("\u5f31\u52bf\u7a7a\u5934，MA5<MA10 \u4f46 MA10≥MA20", prompt)
        self.assertNotIn("\u5f31\u52bf\u591a\u5934\u4fee\u590d", prompt)
        self.assertNotIn("\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", prompt)
        self.assertIn("\u4e8b\u4ef6\u50ac\u5316\u5b58\u5728\u4f46\u6280\u672f\u5f85\u786e\u8ba4", prompt)
        self.assertIn("\u5df2\u5254\u9664\u4e0e\u7a7a\u5934\u4e3b\u5224\u65ad\u76f4\u63a5\u51b2\u7a81\u7684\u770b\u591a\u7ed3\u6784\u7406\u7531", prompt)

    def test_sanitize_trend_analysis_for_prompt_returns_derived_copy_only(self) -> None:
        original = {
            "trend_status": "\u7a7a\u5934\u6392\u5217",
            "ma_alignment": "\u7a7a\u5934\u6392\u5217 MA5<MA10<MA20",
            "signal_reasons": ["\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", "\u4e8b\u4ef6\u50ac\u5316\u5b58\u5728\u4f46\u6280\u672f\u5f85\u786e\u8ba4"],
            "risk_factors": ["\u8dcc\u7834MA20，\u8d8b\u52bf\u627f\u538b"],
        }

        sanitized = _sanitize_trend_analysis_for_prompt(original, volume_change_ratio=12.4)

        self.assertEqual(
            original["signal_reasons"],
            ["\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", "\u4e8b\u4ef6\u50ac\u5316\u5b58\u5728\u4f46\u6280\u672f\u5f85\u786e\u8ba4"],
        )
        self.assertNotIn("prompt_consistency_notes", original)
        self.assertNotIn("prompt_trend_direction", original)
        self.assertNotIn("\u591a\u5934\u6392\u5217，\u6301\u7eed\u4e0a\u6da8", sanitized["signal_reasons"])
        self.assertEqual(sanitized["prompt_trend_direction"], "bearish")


if __name__ == "__main__":
    unittest.main()
