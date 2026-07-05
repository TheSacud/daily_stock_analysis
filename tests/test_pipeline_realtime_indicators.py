# -*- coding: utf-8 -*-
"""
Issue #234 \u76d8\u4e2d\u5b9e\u65f6\u6280\u672f\u6307\u6807\u7684\u5355\u5143\u6d4b\u8bd5。

\u8986\u76d6\u8303\u56f4：
- _augment_historical_with_realtime：\u8ffd\u52a0/\u66f4\u65b0\u903b\u8f91\u548c\u9632\u62a4\u6761\u4ef6
- _compute_ma_status：\u5747\u7ebf\u6392\u5217\u6587\u6848
- _enhance_context：\u4f7f\u7528 realtime + trend_result \u8986\u76d6 today
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult, TrendStatus
from src.core.pipeline import StockAnalysisPipeline


def _make_realtime_quote(
    price: float = 15.72,
    open_price: float = 15.62,
    high: float = 16.29,
    low: float = 15.55,
    volume: int = 13995600,
    amount: float = None,
    change_pct: float = 0.96,
    **overrides,
) -> UnifiedRealtimeQuote:
    return UnifiedRealtimeQuote(
        code="600519",
        name="\u8d35\u5dde\u8305\u53f0",
        source=RealtimeSource.TENCENT,
        price=price,
        open_price=open_price,
        high=high,
        low=low,
        volume=volume,
        amount=amount,
        change_pct=change_pct,
        **overrides,
    )


def _make_historical_df(days: int = 25, last_date: date = None) -> pd.DataFrame:
    """\u6784\u9020\u5386\u53f2 OHLCV DataFrame。"""
    if last_date is None:
        last_date = date.today() - timedelta(days=1)
    dates = [last_date - timedelta(days=i) for i in range(days - 1, -1, -1)]
    base = 100.0
    data = []
    for i, d in enumerate(dates):
        close = base + i * 0.5
        data.append({
            "code": "600519",
            "date": d,
            "open": close - 0.2,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": 1000000 + i * 10000,
            "amount": close * (1000000 + i * 10000),
            "pct_chg": 0.5,
            "ma5": close,
            "ma10": close - 0.1,
            "ma20": close - 0.2,
            "volume_ratio": 1.0,
        })
    return pd.DataFrame(data)


class TestAugmentHistoricalWithRealtime(unittest.TestCase):
    """_augment_historical_with_realtime \u7684\u6d4b\u8bd5。"""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_returns_unchanged_when_realtime_none(self) -> None:
        df = _make_historical_df()
        result = self.pipeline._augment_historical_with_realtime(df, None, "600519")
        self.assertIs(result, df)
        self.assertEqual(len(result), len(df))

    def test_returns_unchanged_when_price_invalid(self) -> None:
        df = _make_historical_df()
        quote = _make_realtime_quote(price=0)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df))
        quote2 = MagicMock()
        quote2.price = None
        result2 = self.pipeline._augment_historical_with_realtime(df, quote2, "600519")
        self.assertEqual(len(result2), len(df))

    def test_returns_unchanged_when_df_empty(self) -> None:
        df = pd.DataFrame()
        quote = _make_realtime_quote()
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertTrue(result.empty)

    def test_returns_unchanged_when_df_missing_close(self) -> None:
        df = pd.DataFrame({"date": [date.today()], "open": [100]})
        quote = _make_realtime_quote()
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), 1)
        self.assertNotIn("close", result.columns)

    @patch("src.core.pipeline.get_market_now")
    @patch("src.core.pipeline.is_market_open", return_value=True)
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_appends_row_when_last_date_before_today(
        self, _mock_market, _mock_open, mock_now
    ) -> None:
        today = date.today()
        # \u56fa\u5b9a\u5e02\u573a\u65f6\u949f\u4e3a UTC \u5f53\u65e5，\u4f7f pipeline \u7684 market_today \u7b49\u4e8e date.today()，
        # \u4e0d\u53d7 get_market_now \u901a\u5e38\u4f7f\u7528\u7684\u5e02\u573a\u65f6\u533a\u5f71\u54cd（\u4f8b\u5982 CST=UTC+8）。
        mock_now.return_value = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc
        )
        df = _make_historical_df(last_date=today - timedelta(days=1))
        quote = _make_realtime_quote(price=15.72)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df) + 1)
        last = result.iloc[-1]
        self.assertEqual(last["close"], 15.72)
        self.assertEqual(last["date"], today)

    @patch("src.core.pipeline.get_market_now")
    @patch("src.core.pipeline.is_market_open", return_value=True)
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_updates_last_row_when_last_date_is_today(
        self, _mock_market, _mock_open, mock_now
    ) -> None:
        today = date.today()
        # \u56fa\u5b9a\u5e02\u573a\u65f6\u949f\u4e3a\u5f53\u65e5，\u4f7f last_date >= market_today，\u4ece\u800c\u66f4\u65b0\u6700\u540e\u4e00\u884c\u800c\u4e0d\u662f\u8ffd\u52a0。
        # \u8fd9\u53ef\u4ee5\u907f\u514d CI \u5728 CST \u6536\u76d8\u540e\u8fd0\u884c\u65f6\u51fa\u73b0\u65e5\u671f\u8fb9\u754c\u504f\u79fb。
        mock_now.return_value = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc
        )
        df = _make_historical_df(last_date=today, days=25)
        df.loc[df.index[-1], "date"] = today
        quote = _make_realtime_quote(price=16.0)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df))
        self.assertEqual(result.iloc[-1]["close"], 16.0)


class TestComputeMaStatus(unittest.TestCase):
    """_compute_ma_status \u7684\u6d4b\u8bd5。"""

    def test_bullish_alignment(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(11, 10, 9.5, 9)
        self.assertIn("\u591a\u5934", status)

    def test_bearish_alignment(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(8, 9, 9.5, 10)
        self.assertIn("\u7a7a\u5934", status)

    def test_consolidation(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(10, 10, 10, 10)
        self.assertIn("\u9707\u8361", status)


class TestEnhanceContextRealtimeOverride(unittest.TestCase):
    """_enhance_context \u4f7f\u7528\u5b9e\u65f6\u884c\u60c5\u548c\u8d8b\u52bf\u7ed3\u679c\u8986\u76d6 today \u7684\u6d4b\u8bd5。"""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    @patch("src.core.pipeline.get_market_now")
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_today_overridden_when_realtime_and_trend_exist(
        self, _mock_market, mock_now
    ) -> None:
        today = date.today()
        # \u56fa\u5b9a\u5e02\u573a\u65f6\u949f，\u4f7f _enhance_context \u8bbe\u7f6e enhanced['date'] == date.today().isoformat()，
        # \u4e0d\u53d7 get_market_now \u901a\u5e38\u4f7f\u7528\u7684\u5e02\u573a\u65f6\u533a\u5f71\u54cd（\u4f8b\u5982 CST=UTC+8）。
        mock_now.return_value = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc
        )
        context = {
            "code": "600519",
            "date": (today - timedelta(days=1)).isoformat(),
            "today": {"close": 15.0, "ma5": 14.8, "ma10": 14.5},
            "yesterday": {"close": 14.5, "volume": 1000000},
        }
        quote = _make_realtime_quote(price=15.72, volume=2000000)
        trend = TrendAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            ma5=15.5,
            ma10=15.2,
            ma20=14.9,
        )
        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "\u8d35\u5dde\u8305\u53f0"
        )
        self.assertEqual(enhanced["today"]["close"], 15.72)
        self.assertEqual(enhanced["today"]["ma5"], 15.5)
        self.assertEqual(enhanced["today"]["ma10"], 15.2)
        self.assertEqual(enhanced["today"]["ma20"], 14.9)
        self.assertIn("\u591a\u5934", enhanced["ma_status"])
        self.assertEqual(enhanced["date"], today.isoformat())
        self.assertEqual(enhanced["today"]["date"], today.isoformat())
        self.assertEqual(enhanced["today"]["data_source"], "realtime:tencent")
        self.assertEqual(enhanced["today"]["realtime_source"], "tencent")
        self.assertIn("price_change_ratio", enhanced)
        self.assertIn("volume_change_ratio", enhanced)

    @patch("src.core.pipeline.get_market_now")
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_tencent_688691_volume_change_ratio_uses_normalized_share_volume(
        self, _mock_market, mock_now
    ) -> None:
        today = date.today()
        mock_now.return_value = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc
        )
        context = {
            "code": "688691",
            "date": (today - timedelta(days=1)).isoformat(),
            "today": {
                "close": 128.46,
                "volume": 19512753,
                "amount": 2487341983,
                "date": (today - timedelta(days=1)).isoformat(),
                "dataSource": "AkshareFetcher",
            },
            "yesterday": {"close": 128.46, "volume": 19512753},
        }
        quote = UnifiedRealtimeQuote(
            code="688691",
            name="\u707f\u82af\u80a1\u4efd",
            source=RealtimeSource.TENCENT,
            price=122.70,
            open_price=120.09,
            high=125.96,
            low=116.20,
            volume=10931723,
            amount=1327404280,
            change_pct=3.40,
        )
        trend = TrendAnalysisResult(
            code="688691",
            trend_status=TrendStatus.BULL,
            ma5=120.014,
            ma10=119.425,
            ma20=115.8305,
        )

        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "\u707f\u82af\u80a1\u4efd"
        )

        self.assertEqual(enhanced["today"]["volume"], 10931723)
        self.assertEqual(enhanced["today"]["amount"], 1327404280)
        self.assertEqual(enhanced["volume_change_ratio"], 0.56)
        self.assertEqual(enhanced["today"]["date"], today.isoformat())
        self.assertEqual(enhanced["today"]["data_source"], "realtime:tencent")
        self.assertEqual(enhanced["today"]["realtime_source"], "tencent")
        self.assertNotIn("dataSource", enhanced["today"])

    @patch("src.core.pipeline.get_market_now")
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_realtime_metadata_and_partial_estimated_fields_are_propagated(
        self, _mock_market, mock_now
    ) -> None:
        today = date.today()
        mock_now.return_value = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc
        )
        context = {
            "code": "600519",
            "date": (today - timedelta(days=1)).isoformat(),
            "today": {
                "close": 15.0,
                "amount": 999999,
                "date": (today - timedelta(days=1)).isoformat(),
                "dataSource": "AkshareFetcher",
            },
            "yesterday": {"close": 14.5, "volume": 1000000},
        }
        quote = _make_realtime_quote(
            price=15.72,
            amount=None,
            fetched_at="2026-05-31T10:00:05+00:00",
            provider_timestamp="2026-05-31T10:00:00+00:00",
            is_stale=False,
            stale_seconds=5,
            fallback_from="efinance",
        )
        trend = TrendAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            ma5=15.5,
            ma10=15.2,
            ma20=14.9,
        )

        enhanced = self.pipeline._enhance_context(
            context,
            quote,
            None,
            trend,
            "\u8d35\u5dde\u8305\u53f0",
            market_phase_context={"is_partial_bar": True},
        )

        self.assertEqual(enhanced["realtime"]["source"], "tencent")
        self.assertEqual(enhanced["realtime"]["fetched_at"], "2026-05-31T10:00:05+00:00")
        self.assertEqual(enhanced["realtime"]["provider_timestamp"], "2026-05-31T10:00:00+00:00")
        self.assertIs(enhanced["realtime"]["is_stale"], False)
        self.assertEqual(enhanced["realtime"]["stale_seconds"], 5)
        self.assertEqual(enhanced["realtime"]["fallback_from"], "efinance")
        self.assertTrue(enhanced["today"]["is_partial_bar"])
        self.assertTrue(enhanced["today"]["is_estimated"])
        self.assertEqual(
            enhanced["today"]["estimated_fields"],
            ["close", "open", "high", "low", "ma5", "ma10", "ma20", "volume", "pct_chg"],
        )
        self.assertEqual(enhanced["today"]["fetched_at"], "2026-05-31T10:00:05+00:00")
        self.assertEqual(enhanced["today"]["provider_timestamp"], "2026-05-31T10:00:00+00:00")
        self.assertEqual(enhanced["today"]["fallback_from"], "efinance")
        self.assertNotIn("amount", enhanced["today"])
        self.assertNotIn("dataSource", enhanced["today"])

    @patch("src.core.pipeline.get_market_now")
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_realtime_today_does_not_backfill_historical_amount_or_source(
        self, _mock_market, mock_now
    ) -> None:
        today = date.today()
        mock_now.return_value = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc
        )
        context = {
            "code": "600519",
            "date": (today - timedelta(days=1)).isoformat(),
            "today": {
                "close": 15.0,
                "amount": 999999,
                "date": (today - timedelta(days=1)).isoformat(),
                "dataSource": "AkshareFetcher",
                "code": "600519",
            },
            "yesterday": {"close": 14.5, "volume": 1000000},
        }
        quote = _make_realtime_quote(price=15.72, amount=None)
        trend = TrendAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            ma5=15.5,
            ma10=15.2,
            ma20=14.9,
        )

        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "\u8d35\u5dde\u8305\u53f0"
        )

        self.assertNotIn("amount", enhanced["today"])
        self.assertNotIn("dataSource", enhanced["today"])
        self.assertEqual(enhanced["today"]["date"], today.isoformat())
        self.assertEqual(enhanced["today"]["data_source"], "realtime:tencent")
        self.assertEqual(enhanced["today"]["code"], "600519")

    def test_enhance_context_injects_runtime_news_window_days(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        enhanced = self.pipeline._enhance_context(
            context, None, None, None, "\u8d35\u5dde\u8305\u53f0"
        )
        self.assertEqual(
            enhanced["news_window_days"],
            self.pipeline.search_service.news_window_days,
        )

    def test_today_not_overridden_when_trend_missing(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        quote = _make_realtime_quote(price=15.72)
        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "\u8d35\u5dde\u8305\u53f0"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)

    def test_today_not_overridden_when_realtime_missing(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        trend = TrendAnalysisResult(code="600519", ma5=15.0, ma10=14.8, ma20=14.5)
        enhanced = self.pipeline._enhance_context(
            context, None, None, trend, "\u8d35\u5dde\u8305\u53f0"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)

    def test_today_not_overridden_when_trend_ma_zero(self) -> None:
        """StockTrendAnalyzer \u56e0\u6570\u636e\u4e0d\u8db3\u63d0\u524d\u8fd4\u56de ma5=0.0 \u65f6，\u4e0d\u5e94\u8986\u76d6 today。"""
        context = {"code": "600519", "today": {"close": 15.0, "ma5": 14.8}}
        quote = _make_realtime_quote(price=15.72)
        trend = TrendAnalysisResult(code="600519")  # \u9ed8\u8ba4 ma5=ma10=ma20=0.0
        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "\u8d35\u5dde\u8305\u53f0"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)
        self.assertEqual(enhanced["today"]["ma5"], 14.8)


if __name__ == "__main__":
    unittest.main()
