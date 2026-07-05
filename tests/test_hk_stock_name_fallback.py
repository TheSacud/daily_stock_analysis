# -*- coding: utf-8 -*-
"""
Regression tests for HK stock name fallback when stock_hk_spot_em fails.

Covers: data_provider/akshare_fetcher.py _get_hk_realtime_quote
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()
try:
    import json_repair  # noqa: F401
except ImportError:
    if "json_repair" not in sys.modules:
        sys.modules["json_repair"] = MagicMock()

from data_provider.akshare_fetcher import AkshareFetcher


class _DummyCircuitBreaker:
    def __init__(self):
        self.failures = []
        self.successes = []

    def is_available(self, source: str) -> bool:
        return True

    def record_success(self, source: str) -> None:
        self.successes.append(source)

    def record_failure(self, source: str, error=None) -> None:
        self.failures.append((source, error))


def _make_spot_em_df():
    """Simulate stock_hk_spot_em() return value."""
    return pd.DataFrame([{
        '\u4ee3\u7801': '00700',
        '\u540d\u79f0': '\u817e\u8baf\u63a7\u80a1',
        '\u6700\u65b0\u4ef7': 370.0,
        '\u6da8\u8dcc\u5e45': 1.5,
        '\u6da8\u8dcc\u989d': 5.5,
        '\u6210\u4ea4\u91cf': 10000,
        '\u6210\u4ea4\u989d': 3700000.0,
        '\u91cf\u6bd4': 1.2,
        '\u6362\u624b\u7387': 0.3,
        '\u632f\u5e45': 2.0,
        '\u5e02\u76c8\u7387': 20.0,
        '\u5e02\u51c0\u7387': 3.5,
        '\u603b\u5e02\u503c': 3.5e12,
        '\u6d41\u901a\u5e02\u503c': 3.5e12,
        '52\u5468\u6700\u9ad8': 400.0,
        '52\u5468\u6700\u4f4e': 280.0,
    }])


def _make_spot_df():
    """Simulate stock_hk_spot() return value (sina source)."""
    return pd.DataFrame([{
        '\u4ee3\u7801': '00700',
        '\u540d\u79f0': '\u817e\u8baf\u63a7\u80a1',
        '\u6700\u65b0\u4ef7': 368.0,
        '\u6da8\u8dcc\u989d': 3.5,
        '\u6da8\u8dcc\u5e45': 0.96,
        '\u4e70\u5165': 367.8,
        '\u5356\u51fa': 368.2,
        '\u6628\u6536': 364.5,
        '\u4eca\u5f00': 365.0,
        '\u6700\u9ad8': 370.0,
        '\u6700\u4f4e': 364.0,
        '\u6210\u4ea4\u91cf': 9800,
        '\u6210\u4ea4\u989d': 3606400.0,
    }])


class TestHKRealtimeFallback(unittest.TestCase):
    """stock_hk_spot_em \u5931\u8d25\u65f6\u5e94 fallback \u5230 stock_hk_spot。"""

    def setUp(self):
        self.fetcher = AkshareFetcher()
        # Bypass rate limiting
        self.fetcher._enforce_rate_limit = lambda: None
        self.fetcher._set_random_user_agent = lambda: None

    @patch("data_provider.akshare_fetcher.get_realtime_circuit_breaker")
    def test_em_success_returns_quote_with_name(self, mock_cb):
        """stock_hk_spot_em \u6210\u529f\u65f6\u76f4\u63a5\u8fd4\u56de\u542b\u540d\u79f0\u7684 quote。"""
        mock_cb.return_value = _DummyCircuitBreaker()
        ak_mock = MagicMock()
        ak_mock.stock_hk_spot_em.return_value = _make_spot_em_df()

        with patch.dict(sys.modules, {"akshare": ak_mock}):
            quote = self.fetcher._get_hk_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.name, "\u817e\u8baf\u63a7\u80a1")
        self.assertAlmostEqual(quote.price, 370.0)

    @patch("data_provider.akshare_fetcher.get_realtime_circuit_breaker")
    def test_em_failure_falls_back_to_spot(self, mock_cb):
        """stock_hk_spot_em \u629b\u5f02\u5e38\u65f6\u5e94 fallback \u5230 stock_hk_spot \u5e76\u8fd4\u56de\u540d\u79f0。"""
        mock_cb.return_value = _DummyCircuitBreaker()
        ak_mock = MagicMock()
        ak_mock.stock_hk_spot_em.side_effect = Exception("\u63a5\u53e3\u5f02\u5e38：\u6570\u636e\u6e90\u4e0d\u53ef\u7528")
        ak_mock.stock_hk_spot.return_value = _make_spot_df()

        with patch.dict(sys.modules, {"akshare": ak_mock}):
            quote = self.fetcher._get_hk_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.name, "\u817e\u8baf\u63a7\u80a1")
        self.assertAlmostEqual(quote.price, 368.0)
        ak_mock.stock_hk_spot.assert_called_once()

    @patch("data_provider.akshare_fetcher.get_realtime_circuit_breaker")
    def test_both_fail_returns_none(self, mock_cb):
        """stock_hk_spot_em \u548c stock_hk_spot \u90fd\u5931\u8d25\u65f6\u8fd4\u56de None，\u4e0d\u629b\u5f02\u5e38。"""
        mock_cb.return_value = _DummyCircuitBreaker()
        ak_mock = MagicMock()
        ak_mock.stock_hk_spot_em.side_effect = Exception("\u4e1c\u65b9\u8d22\u5bcc\u63a5\u53e3\u8d85\u65f6")
        ak_mock.stock_hk_spot.side_effect = Exception("\u65b0\u6d6a\u63a5\u53e3\u8d85\u65f6")

        with patch.dict(sys.modules, {"akshare": ak_mock}):
            quote = self.fetcher._get_hk_realtime_quote("HK00700")

        self.assertIsNone(quote)

    @patch("data_provider.akshare_fetcher.get_realtime_circuit_breaker")
    def test_em_returns_empty_df_falls_back_to_spot(self, mock_cb):
        """stock_hk_spot_em \u8fd4\u56de\u7a7a DataFrame \u65f6\u5e94 fallback \u5230 stock_hk_spot。"""
        mock_cb.return_value = _DummyCircuitBreaker()
        ak_mock = MagicMock()
        ak_mock.stock_hk_spot_em.return_value = pd.DataFrame(columns=['\u4ee3\u7801', '\u540d\u79f0', '\u6700\u65b0\u4ef7'])
        ak_mock.stock_hk_spot.return_value = _make_spot_df()

        with patch.dict(sys.modules, {"akshare": ak_mock}):
            quote = self.fetcher._get_hk_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.name, "\u817e\u8baf\u63a7\u80a1")

    @patch("data_provider.akshare_fetcher.get_realtime_circuit_breaker")
    def test_circuit_breaker_open_returns_none(self, mock_cb):
        """\u7194\u65ad\u72b6\u6001\u4e0b\u76f4\u63a5\u8fd4\u56de None。"""
        cb = _DummyCircuitBreaker()
        cb.is_available = lambda source: False
        mock_cb.return_value = cb
        ak_mock = MagicMock()

        with patch.dict(sys.modules, {"akshare": ak_mock}):
            quote = self.fetcher._get_hk_realtime_quote("HK00700")

        self.assertIsNone(quote)
        ak_mock.stock_hk_spot_em.assert_not_called()


if __name__ == "__main__":
    unittest.main()
