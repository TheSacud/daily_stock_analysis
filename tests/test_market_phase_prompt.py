# -*- coding: utf-8 -*-
"""Tests for Issue #1386 P2-min market phase prompt rendering."""

import unittest

from src.market_phase_prompt import format_market_phase_prompt_section


def _ctx(**overrides):
    payload = {
        "market": "cn",
        "phase": "intraday",
        "market_local_time": "2026-03-27T10:00:00+08:00",
        "effective_daily_bar_date": "2026-03-26",
        "is_partial_bar": True,
        "minutes_to_open": None,
        "minutes_to_close": 300,
        "warnings": [],
        "trigger_source": "system",
        "analysis_intent": "auto",
    }
    payload.update(overrides)
    return payload


class MarketPhasePromptTestCase(unittest.TestCase):
    def test_empty_or_invalid_context_returns_empty_section(self):
        self.assertEqual(format_market_phase_prompt_section(None), "")
        self.assertEqual(format_market_phase_prompt_section({}), "")
        self.assertEqual(format_market_phase_prompt_section("intraday"), "")

    def test_premarket_mentions_opening_plan_and_completed_daily_bar(self):
        section = format_market_phase_prompt_section(
            _ctx(phase="premarket", is_partial_bar=False, minutes_to_open=30)
        )

        self.assertIn("\u5e02\u573a\u9636\u6bb5\u4e0a\u4e0b\u6587", section)
        self.assertIn("\u76d8\u524d", section)
        self.assertIn("\u5c1a\u672a\u5f00\u76d8", section)
        self.assertIn("\u4e0d\u5f97\u63cf\u8ff0“\u4eca\u65e5\u8d70\u52bf\u5df2\u7ecf\u53d1\u751f”", section)
        self.assertIn("\u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5", section)
        self.assertIn("2026-03-26", section)
        self.assertIn("\u8ddd\u5e38\u89c4\u5f00\u76d8\u7ea6 30 \u5206\u949f", section)

    def test_intraday_partial_bar_warns_against_full_daily_recap(self):
        section = format_market_phase_prompt_section(_ctx())

        self.assertIn("\u76d8\u4e2d", section)
        self.assertIn("\u5f53\u524d\u4e0d\u662f\u76d8\u540e\u590d\u76d8", section)
        self.assertIn("\u6700\u540e\u4e00\u6839\u65e5\u7ebf\u53ef\u80fd\u5c1a\u672a\u5b8c\u6210", section)
        self.assertIn("\u4e0d\u5f97\u5f53\u4f5c\u5b8c\u6574\u65e5\u7ebf\u590d\u76d8", section)
        self.assertIn("\u8ddd\u5e38\u89c4\u6536\u76d8\u7ea6 300 \u5206\u949f", section)

    def test_lunch_break_and_closing_auction_add_phase_specific_guidance(self):
        lunch = format_market_phase_prompt_section(_ctx(phase="lunch_break"))
        closing = format_market_phase_prompt_section(_ctx(phase="closing_auction"))

        self.assertIn("\u5348\u95f4\u4f11\u5e02", lunch)
        self.assertIn("\u4e0b\u5348\u4ea4\u6613\u786e\u8ba4", lunch)
        self.assertIn("\u4e34\u8fd1\u6536\u76d8", closing)
        self.assertIn("\u662f\u5426\u9694\u591c\u6301\u4ed3", closing)

    def test_postmarket_keeps_recap_semantics(self):
        section = format_market_phase_prompt_section(
            _ctx(phase="postmarket", is_partial_bar=False, minutes_to_close=None)
        )

        self.assertIn("\u76d8\u540e", section)
        self.assertIn("\u5b8c\u6574\u4ea4\u6613\u65e5\u590d\u76d8\u8bed\u4e49", section)

    def test_non_trading_prevents_fake_intraday_movement(self):
        section = format_market_phase_prompt_section(
            _ctx(phase="non_trading", is_partial_bar=False, minutes_to_close=None)
        )

        self.assertIn("\u975e\u4ea4\u6613\u65e5", section)
        self.assertIn("\u4e0d\u5f97\u4f2a\u9020\u4eca\u65e5\u76d8\u4e2d\u8d70\u52bf", section)
        self.assertIn("2026-03-26", section)

    def test_unknown_phase_and_warnings_are_conservative_without_raw_codes(self):
        section = format_market_phase_prompt_section(
            _ctx(phase="not_a_phase", warnings=["calendar_unavailable", "unknown_warning"])
        )

        self.assertIn("\u672a\u77e5\u9636\u6bb5", section)
        self.assertIn("\u4e0d\u53ef\u53ef\u9760\u63a8\u65ad", section)
        self.assertIn("\u4ea4\u6613\u65e5\u5386\u4e0d\u53ef\u7528", section)
        self.assertNotIn("calendar_unavailable", section)
        self.assertNotIn("unknown_warning", section)

    def test_missing_phase_uses_unknown_template(self):
        payload = _ctx()
        payload.pop("phase")

        section = format_market_phase_prompt_section(payload)

        self.assertIn("\u672a\u77e5\u9636\u6bb5", section)
        self.assertIn("\u4e0d\u53ef\u53ef\u9760\u63a8\u65ad", section)

    def test_warnings_non_list_is_ignored(self):
        section = format_market_phase_prompt_section(_ctx(warnings="calendar_unavailable"))

        self.assertNotIn("\u964d\u7ea7\u8bf4\u660e", section)
        self.assertIn("\u76d8\u4e2d", section)

    def test_english_mode_outputs_readable_english_constraints(self):
        section = format_market_phase_prompt_section(
            _ctx(phase="premarket", is_partial_bar=False),
            report_language="en",
        )

        self.assertIn("Market Phase Context", section)
        self.assertIn("pre-market", section)
        self.assertIn("has not opened", section)
        self.assertIn("Do not describe today's price action as already happened", section)
        self.assertNotIn("(premarket)", section)

    def test_output_does_not_leak_runtime_raw_keys(self):
        section = format_market_phase_prompt_section(_ctx())

        self.assertNotIn("market_phase_context", section)
        self.assertNotIn("is_partial_bar", section)
        self.assertNotIn("trigger_source", section)
        self.assertNotIn("analysis_intent", section)
        self.assertNotIn("intraday", section)


if __name__ == "__main__":
    unittest.main()
