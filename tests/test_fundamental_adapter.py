# -*- coding: utf-8 -*-
"""
Tests for fundamental adapter helpers.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.fundamental_adapter import (
    AkshareFundamentalAdapter,
    _build_dividend_payload,
    _extract_latest_row,
    _parse_dividend_plan_to_per_share,
)


class TestFundamentalAdapter(unittest.TestCase):
    def test_parse_dividend_plan_to_per_share_supports_cn_patterns(self) -> None:
        self.assertAlmostEqual(_parse_dividend_plan_to_per_share("10\u6d3e3\u5143(\u542b\u7a0e)"), 0.3, places=6)
        self.assertAlmostEqual(_parse_dividend_plan_to_per_share("\u6bcf10\u80a1\u6d3e\u53d12.5\u5143"), 0.25, places=6)
        self.assertAlmostEqual(_parse_dividend_plan_to_per_share("\u6bcf\u80a1\u6d3e0.8\u5143"), 0.8, places=6)
        self.assertIsNone(_parse_dividend_plan_to_per_share("\u4ec5\u9001\u80a1，\u4e0d\u73b0\u91d1\u5206\u7ea2"))

    def test_extract_latest_row_returns_none_when_code_mismatch(self) -> None:
        df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600000", "000001"],
                "\u503c": [1, 2],
            }
        )
        row = _extract_latest_row(df, "600519")
        self.assertIsNone(row)

    def test_extract_latest_row_fallback_when_no_code_column(self) -> None:
        df = pd.DataFrame({"\u503c": [1, 2]})
        row = _extract_latest_row(df, "600519")
        self.assertIsNotNone(row)
        self.assertEqual(row["\u503c"], 1)

    def test_dragon_tiger_no_match_with_code_column_is_ok(self) -> None:
        adapter = AkshareFundamentalAdapter()
        df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600000"],
                "\u65e5\u671f": ["2026-01-01"],
            }
        )
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_lhb_stock_statistic_em", [])):
            result = adapter.get_dragon_tiger_flag("600519")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["is_on_list"])
        self.assertEqual(result["recent_count"], 0)

    def test_dragon_tiger_match_is_ok(self) -> None:
        adapter = AkshareFundamentalAdapter()
        today = pd.Timestamp.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519"],
                "\u65e5\u671f": [today],
            }
        )
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_lhb_stock_statistic_em", [])):
            result = adapter.get_dragon_tiger_flag("600519")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["is_on_list"])
        self.assertGreaterEqual(result["recent_count"], 1)

    def test_fundamental_bundle_includes_financial_report_and_dividend_payload(self) -> None:
        adapter = AkshareFundamentalAdapter()
        now = datetime.now()
        within_ttm = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        future_day = (now + timedelta(days=10)).strftime("%Y-%m-%d")
        old_day = (now - timedelta(days=500)).strftime("%Y-%m-%d")
        fin_df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519"],
                "\u62a5\u544a\u671f": [within_ttm],
                "\u8425\u4e1a\u603b\u6536\u5165": [1000.0],
                "\u5f52\u6bcd\u51c0\u5229\u6da6": [300.0],
                "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d": [500.0],
                "\u51c0\u8d44\u4ea7\u6536\u76ca\u7387": [18.2],
                "\u8425\u4e1a\u6536\u5165\u540c\u6bd4": [12.0],
                "\u51c0\u5229\u6da6\u540c\u6bd4": [9.5],
            }
        )
        forecast_df = pd.DataFrame({"\u80a1\u7968\u4ee3\u7801": ["600519"], "\u9884\u544a": ["\u9884\u589e"]})
        quick_df = pd.DataFrame({"\u80a1\u7968\u4ee3\u7801": ["600519"], "\u5feb\u62a5": ["\u5feb\u62a5\u6458\u8981"]})
        dividend_df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519", "600519", "600519", "600519"],
                "\u9664\u606f\u65e5": [within_ttm, within_ttm, future_day, old_day],
                "\u5206\u914d\u65b9\u6848": ["10\u6d3e3\u5143(\u542b\u7a0e)", "10\u6d3e3\u5143(\u542b\u7a0e)", "10\u6d3e5\u5143", "10\u6d3e1\u5143"],
            }
        )

        with patch.object(
            adapter,
            "_call_df_candidates",
            side_effect=[
                (fin_df, "stock_financial_abstract", []),
                (forecast_df, "stock_yjyg_em", []),
                (quick_df, "stock_yjkb_em", []),
                (dividend_df, "stock_fhps_detail_em", []),
                (None, None, []),
                (None, None, []),
            ],
        ):
            result = adapter.get_fundamental_bundle("600519")

        financial_report = result["earnings"].get("financial_report", {})
        self.assertEqual(financial_report.get("report_date"), within_ttm)
        self.assertEqual(financial_report.get("revenue"), 1000.0)
        self.assertEqual(financial_report.get("net_profit_parent"), 300.0)
        self.assertEqual(financial_report.get("operating_cash_flow"), 500.0)
        self.assertEqual(financial_report.get("roe"), 18.2)

        dividend_payload = result["earnings"].get("dividend", {})
        events = dividend_payload.get("events", [])
        self.assertEqual(len(events), 2)  # duplicate + future day filtered
        self.assertEqual(dividend_payload.get("ttm_event_count"), 1)
        self.assertAlmostEqual(dividend_payload.get("ttm_cash_dividend_per_share"), 0.3, places=6)

    def test_build_dividend_payload_returns_empty_when_code_not_matched(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["000001"],
                "\u9664\u606f\u65e5": [now],
                "\u5206\u914d\u65b9\u6848": ["10\u6d3e3\u5143(\u542b\u7a0e)"],
            }
        )

        payload = _build_dividend_payload(df, stock_code="600519")
        self.assertEqual(payload, {})

    def test_build_dividend_payload_skips_after_tax_plan(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519"],
                "\u9664\u606f\u65e5": [now],
                "\u5206\u914d\u65b9\u6848": ["10\u6d3e3\u5143(\u7a0e\u540e)"],
            }
        )

        payload = _build_dividend_payload(df, stock_code="600519")
        self.assertEqual(payload, {})

    def test_build_dividend_payload_ttm_window_boundary(self) -> None:
        now = datetime.now()
        day_365 = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        day_366 = (now - timedelta(days=366)).strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519", "600519"],
                "\u9664\u606f\u65e5": [day_365, day_366],
                "\u5206\u914d\u65b9\u6848": ["10\u6d3e3\u5143(\u542b\u7a0e)", "10\u6d3e5\u5143(\u542b\u7a0e)"],
            }
        )

        payload = _build_dividend_payload(df, stock_code="600519")
        self.assertEqual(payload.get("ttm_event_count"), 1)
        self.assertAlmostEqual(payload.get("ttm_cash_dividend_per_share"), 0.3, places=6)


if __name__ == "__main__":
    unittest.main()
