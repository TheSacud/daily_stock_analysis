# -*- coding: utf-8 -*-
"""
data_provider/yfinance_fetcher \u4e2d\u7f8e\u80a1\u6307\u6570\u83b7\u53d6\u903b\u8f91\u7684\u5355\u5143\u6d4b\u8bd5

\u4f7f\u7528 unittest.mock \u6a21\u62df yfinance API \u54cd\u5e94，\u8986\u76d6：
- _fetch_yf_ticker_data \u5355\u6307\u6570\u6570\u636e\u89e3\u6790
- _get_us_main_indices \u7f8e\u80a1\u6307\u6570\u6279\u91cf\u83b7\u53d6\u53ca\u5f02\u5e38\u573a\u666f
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

# \u5728\u5bfc\u5165 data_provider \u524d mock \u53ef\u80fd\u7f3a\u5931\u7684\u4f9d\u8d56，\u907f\u514d\u73af\u5883\u5dee\u5f02\u5bfc\u81f4\u6d4b\u8bd5\u65e0\u6cd5\u8fd0\u884c
if 'fake_useragent' not in sys.modules:
    sys.modules['fake_useragent'] = MagicMock()

# \u786e\u4fdd\u80fd\u5bfc\u5165\u9879\u76ee\u6a21\u5757
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _make_mock_hist(close: float, prev_close: float, high: float = None, low: float = None) -> pd.DataFrame:
    """\u6784\u9020\u6a21\u62df\u7684 history DataFrame，\u5305\u542b\u8ba1\u7b97\u6da8\u8dcc\u5e45\u6240\u9700\u5b57\u6bb5"""
    high = high if high is not None else close + 1
    low = low if low is not None else close - 1
    return pd.DataFrame({
        'Close': [prev_close, close],
        'Open': [prev_close - 0.5, close - 0.3],
        'High': [prev_close + 1, high],
        'Low': [prev_close - 1, low],
        'Volume': [1000000.0, 1200000.0],
    }, index=pd.DatetimeIndex(['2025-02-16', '2025-02-17']))


def _make_mock_yf(hist_df: pd.DataFrame):
    """\u6784\u9020\u6a21\u62df\u7684 yf \u6a21\u5757，Ticker().history() \u8fd4\u56de\u7ed9\u5b9a DataFrame"""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = hist_df
    mock_yf = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker
    return mock_yf


class TestFetchYfTickerData(unittest.TestCase):
    """_fetch_yf_ticker_data \u5355\u6307\u6570\u53d6\u6570\u903b\u8f91\u6d4b\u8bd5"""

    def setUp(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher
        self.fetcher = YfinanceFetcher()

    def test_returns_dict_with_correct_fields(self):
        """\u6b63\u5e38\u6570\u636e\u5e94\u8fd4\u56de\u5305\u542b code/name/current/change_pct \u7b49\u5b57\u6bb5\u7684\u5b57\u5178"""
        mock_hist = _make_mock_hist(close=5100.0, prev_close=5000.0)
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._fetch_yf_ticker_data(mock_yf, '^GSPC', '\u6807\u666e500\u6307\u6570', 'SPX')

        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'SPX')
        self.assertEqual(result['name'], '\u6807\u666e500\u6307\u6570')
        self.assertEqual(result['current'], 5100.0)
        self.assertEqual(result['prev_close'], 5000.0)
        self.assertEqual(result['change'], 100.0)
        self.assertAlmostEqual(result['change_pct'], 2.0)
        self.assertIn('open', result)
        self.assertIn('high', result)
        self.assertIn('low', result)
        self.assertIn('volume', result)
        self.assertIn('amount', result)
        self.assertIn('amplitude', result)

    def test_returns_none_when_history_empty(self):
        """history \u4e3a\u7a7a\u65f6\u5e94\u8fd4\u56de None"""
        mock_yf = _make_mock_yf(pd.DataFrame())

        result = self.fetcher._fetch_yf_ticker_data(mock_yf, '^GSPC', '\u6807\u666e500\u6307\u6570', 'SPX')

        self.assertIsNone(result)

    def test_single_row_history_uses_same_as_prev(self):
        """\u4ec5\u4e00\u884c\u6570\u636e\u65f6 prev_close \u7b49\u4e8e current，change_pct \u4e3a 0"""
        mock_hist = _make_mock_hist(close=5000.0, prev_close=5000.0)
        mock_hist = mock_hist.iloc[[-1]]
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._fetch_yf_ticker_data(mock_yf, '^GSPC', '\u6807\u666e500\u6307\u6570', 'SPX')

        self.assertIsNotNone(result)
        self.assertEqual(result['change_pct'], 0.0)


class TestGetUsMainIndices(unittest.TestCase):
    """_get_us_main_indices \u7f8e\u80a1\u6307\u6570\u6279\u91cf\u83b7\u53d6\u6d4b\u8bd5"""

    def setUp(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher
        self.fetcher = YfinanceFetcher()

    @patch('data_provider.yfinance_fetcher.get_us_index_yf_symbol')
    def test_returns_list_when_mock_succeeds(self, mock_get_symbol):
        """\u5f53\u6620\u5c04\u4e0e\u53d6\u6570\u5747\u6210\u529f\u65f6\u8fd4\u56de\u6307\u6570\u5217\u8868"""
        def get_symbol(code):
            mapping = {
                'SPX': ('^GSPC', '\u6807\u666e500\u6307\u6570'),
                'IXIC': ('^IXIC', '\u7eb3\u65af\u8fbe\u514b\u7efc\u5408\u6307\u6570'),
                'DJI': ('^DJI', '\u9053\u743c\u65af\u5de5\u4e1a\u6307\u6570'),
                'VIX': ('^VIX', 'VIX\u6050\u614c\u6307\u6570'),
            }
            return mapping.get(code, (None, None))

        mock_get_symbol.side_effect = get_symbol
        mock_hist = _make_mock_hist(close=5100.0, prev_close=5000.0)
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._get_us_main_indices(mock_yf)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)
        for item in result:
            self.assertIn('code', item)
            self.assertIn('name', item)
            self.assertIn('current', item)
            self.assertIn('change_pct', item)

    @patch('data_provider.yfinance_fetcher.get_us_index_yf_symbol')
    def test_handles_empty_history_gracefully(self, mock_get_symbol):
        """\u90e8\u5206\u6307\u6570 history \u4e3a\u7a7a\u65f6\u4ecd\u8fd4\u56de\u80fd\u53d6\u5230\u6570\u636e\u7684\u6307\u6570"""
        call_count = [0]

        def get_symbol(code):
            return ('^GSPC', '\u6807\u666e500\u6307\u6570') if code == 'SPX' else (
                ('^IXIC', '\u7eb3\u65af\u8fbe\u514b\u7efc\u5408\u6307\u6570') if code == 'IXIC' else (None, None)
            )

        def history_side_effect(period):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_mock_hist(close=5100.0, prev_close=5000.0)
            return pd.DataFrame()

        mock_get_symbol.side_effect = get_symbol
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = history_side_effect
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        result = self.fetcher._get_us_main_indices(mock_yf)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)

    @patch('data_provider.yfinance_fetcher.get_us_index_yf_symbol')
    def test_returns_none_when_all_fail(self, mock_get_symbol):
        """\u5168\u90e8\u53d6\u6570\u5931\u8d25\u65f6\u8fd4\u56de None"""
        mock_get_symbol.return_value = (None, None)
        mock_yf = _make_mock_yf(pd.DataFrame())

        result = self.fetcher._get_us_main_indices(mock_yf)

        self.assertIsNone(result)

    @patch('data_provider.yfinance_fetcher.get_us_index_yf_symbol')
    def test_handles_ticker_exception(self, mock_get_symbol):
        """Ticker.history \u629b\u5f02\u5e38\u65f6\u8df3\u8fc7\u8be5\u6307\u6570，\u4e0d\u6574\u4f53\u5931\u8d25"""
        mock_get_symbol.return_value = ('^GSPC', '\u6807\u666e500\u6307\u6570')
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("Network error")
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        result = self.fetcher._get_us_main_indices(mock_yf)

        self.assertIsNone(result)

    @patch('data_provider.yfinance_fetcher.get_us_index_yf_symbol')
    def test_skips_unknown_index_code(self, mock_get_symbol):
        """get_us_index_yf_symbol \u8fd4\u56de (None, None) \u7684\u4ee3\u7801\u5e94\u88ab\u8df3\u8fc7"""
        def get_symbol(code):
            if code == 'SPX':
                return ('^GSPC', '\u6807\u666e500\u6307\u6570')
            return (None, None)

        mock_get_symbol.side_effect = get_symbol
        mock_hist = _make_mock_hist(close=5100.0, prev_close=5000.0)
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._get_us_main_indices(mock_yf)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['code'], 'SPX')


if __name__ == '__main__':
    unittest.main()
