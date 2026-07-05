# -*- coding: utf-8 -*-
"""
data_provider/yfinance_fetcher \u4e2d\u6e2f\u80a1\u6307\u6570\u83b7\u53d6\u903b\u8f91\u7684\u5355\u5143\u6d4b\u8bd5

\u4f7f\u7528 unittest.mock \u6a21\u62df yfinance API \u54cd\u5e94，\u8986\u76d6：
- _get_hk_main_indices \u6e2f\u80a1\u6307\u6570\u6279\u91cf\u83b7\u53d6
- \u6e2f\u80a1\u6307\u6570 Yahoo Finance \u7b26\u53f7\u6620\u5c04\u6b63\u786e\u6027
- \u90e8\u5206/\u5168\u90e8\u5931\u8d25\u7684\u964d\u7ea7\u573a\u666f
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
    high = high if high is not None else close + 100
    low = low if low is not None else close - 100
    return pd.DataFrame({
        'Close': [prev_close, close],
        'Open': [prev_close - 50, close - 30],
        'High': [prev_close + 100, high],
        'Low': [prev_close - 100, low],
        'Volume': [5000000000.0, 5200000000.0],
    }, index=pd.DatetimeIndex(['2025-02-16', '2025-02-17']))


def _make_mock_yf(hist_df: pd.DataFrame):
    """\u6784\u9020\u6a21\u62df\u7684 yf \u6a21\u5757，Ticker().history() \u8fd4\u56de\u7ed9\u5b9a DataFrame"""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = hist_df
    mock_yf = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker
    return mock_yf


class TestHkIndexSymbolMapping(unittest.TestCase):
    """\u9a8c\u8bc1\u6e2f\u80a1\u6307\u6570 Yahoo Finance \u7b26\u53f7\u6620\u5c04\u7684\u6b63\u786e\u6027"""

    def setUp(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher
        self.fetcher = YfinanceFetcher()

    def test_hk_indices_mapping_symbols(self):
        """\u6e2f\u80a1\u6307\u6570\u6620\u5c04\u5e94\u4f7f\u7528\u6b63\u786e\u7684 Yahoo Finance \u7b26\u53f7"""
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        self.fetcher._get_hk_main_indices(mock_yf)

        # \u6536\u96c6\u6240\u6709 Ticker() \u8c03\u7528\u7684\u53c2\u6570
        ticker_calls = [call.args[0] for call in mock_yf.Ticker.call_args_list]

        self.assertIn('^HSI', ticker_calls, '\u6052\u751f\u6307\u6570\u5e94\u4f7f\u7528 ^HSI')
        self.assertIn('HSTECH.HK', ticker_calls, '\u6052\u751f\u79d1\u6280\u6307\u6570\u5e94\u4f7f\u7528 HSTECH.HK，\u800c\u975e ^HSTECH')
        self.assertIn('^HSCE', ticker_calls, '\u56fd\u4f01\u6307\u6570\u5e94\u4f7f\u7528 ^HSCE，\u800c\u975e ^HSCEI')

    def test_hk_indices_mapping_no_invalid_symbols(self):
        """\u786e\u4fdd\u4e0d\u518d\u4f7f\u7528\u5df2\u77e5\u9519\u8bef\u7684\u65e7\u6620\u5c04\u7b26\u53f7"""
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        self.fetcher._get_hk_main_indices(mock_yf)

        ticker_calls = [call.args[0] for call in mock_yf.Ticker.call_args_list]

        self.assertNotIn('^HSTECH', ticker_calls, '^HSTECH \u4e0d\u662f\u6709\u6548\u7684 Yahoo Finance \u7b26\u53f7')
        self.assertNotIn('^HSCEI', ticker_calls, '^HSCEI \u4e0d\u662f\u6709\u6548\u7684 Yahoo Finance \u7b26\u53f7')


class TestGetHkMainIndices(unittest.TestCase):
    """_get_hk_main_indices \u6e2f\u80a1\u6307\u6570\u6279\u91cf\u83b7\u53d6\u6d4b\u8bd5"""

    def setUp(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher
        self.fetcher = YfinanceFetcher()

    def test_returns_list_when_all_succeed(self):
        """\u5168\u90e8\u6307\u6570\u53d6\u6570\u6210\u529f\u65f6\u8fd4\u56de\u5305\u542b\u4e09\u4e2a\u6307\u6570\u7684\u5217\u8868"""
        mock_hist = _make_mock_hist(close=20000.0, prev_close=19800.0)
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._get_hk_main_indices(mock_yf)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

        codes = {item['code'] for item in result}
        self.assertEqual(codes, {'HSI', 'HSTECH', 'HSCEI'})

        for item in result:
            self.assertIn('code', item)
            self.assertIn('name', item)
            self.assertIn('current', item)
            self.assertIn('change_pct', item)
            self.assertIn('prev_close', item)
            self.assertIn('amplitude', item)

    def test_returns_correct_computed_values(self):
        """\u9a8c\u8bc1\u6da8\u8dcc\u5e45\u548c\u632f\u5e45\u7684\u8ba1\u7b97\u7ed3\u679c"""
        mock_hist = _make_mock_hist(
            close=20000.0, prev_close=19800.0, high=20200.0, low=19700.0
        )
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._get_hk_main_indices(mock_yf)

        self.assertIsNotNone(result)
        item = result[0]
        self.assertEqual(item['current'], 20000.0)
        self.assertEqual(item['prev_close'], 19800.0)
        self.assertAlmostEqual(item['change'], 200.0)
        expected_pct = (200.0 / 19800.0) * 100
        self.assertAlmostEqual(item['change_pct'], expected_pct)
        expected_amplitude = ((20200.0 - 19700.0) / 19800.0) * 100
        self.assertAlmostEqual(item['amplitude'], expected_amplitude)

    def test_handles_partial_failure(self):
        """\u90e8\u5206\u6307\u6570 history \u4e3a\u7a7a\u65f6\u4ecd\u8fd4\u56de\u80fd\u53d6\u5230\u6570\u636e\u7684\u6307\u6570"""
        call_count = [0]

        def history_side_effect(period):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_mock_hist(close=20000.0, prev_close=19800.0)
            return pd.DataFrame()

        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = history_side_effect
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        result = self.fetcher._get_hk_main_indices(mock_yf)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_returns_none_when_all_fail(self):
        """\u5168\u90e8\u53d6\u6570\u5931\u8d25\u65f6\u8fd4\u56de None"""
        mock_yf = _make_mock_yf(pd.DataFrame())

        result = self.fetcher._get_hk_main_indices(mock_yf)

        self.assertIsNone(result)

    def test_handles_ticker_exception(self):
        """Ticker.history \u629b\u5f02\u5e38\u65f6\u8df3\u8fc7\u8be5\u6307\u6570，\u4e0d\u6574\u4f53\u5931\u8d25"""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("Network error")
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        result = self.fetcher._get_hk_main_indices(mock_yf)

        self.assertIsNone(result)

    def test_return_codes_match_expected_keys(self):
        """\u8fd4\u56de\u7684 code \u5b57\u6bb5\u5e94\u4e3a HSI/HSTECH/HSCEI，\u4e0e MarketAnalyzer prompt \u4e00\u81f4"""
        mock_hist = _make_mock_hist(close=20000.0, prev_close=19800.0)
        mock_yf = _make_mock_yf(mock_hist)

        result = self.fetcher._get_hk_main_indices(mock_yf)

        self.assertIsNotNone(result)
        codes = [item['code'] for item in result]
        self.assertIn('HSI', codes)
        self.assertIn('HSTECH', codes)
        self.assertIn('HSCEI', codes)


class TestGetMainIndicesDispatch(unittest.TestCase):
    """get_main_indices region \u5206\u53d1\u6d4b\u8bd5"""

    def setUp(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher
        self.fetcher = YfinanceFetcher()

    def test_region_hk_dispatches_to_hk_method(self):
        """region='hk' \u5e94\u59d4\u6258\u7ed9 _get_hk_main_indices"""
        mock_yf = MagicMock()
        with patch.dict('sys.modules', {'yfinance': mock_yf}):
            with patch.object(self.fetcher, '_get_hk_main_indices', return_value=[{'code': 'HSI'}]) as mock_hk:
                result = self.fetcher.get_main_indices(region='hk')

                mock_hk.assert_called_once()
                self.assertEqual(result, [{'code': 'HSI'}])


if __name__ == '__main__':
    unittest.main()
