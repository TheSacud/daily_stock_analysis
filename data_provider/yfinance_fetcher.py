# -*- coding: utf-8 -*-
"""
===================================
YfinanceFetcher - \u515c\u5e95data source (Priority 4)
===================================

\u6570\u636esource: Yahoo Finance (\u901a\u8fc7 yfinance library)
\u7279\u70b9: \u56fd\u9645data source、\u53ef\u80fd\u6709\u5ef6\u8fdfor\u7f3a\u5931
\u5b9acharacters: \u5f53\u6240\u6709\u56fd\u5185data source\u90fdfailed\u65f6\u7684\u6700\u540e\u4fdd\u969c

\u5173\u952estrategy:
1. \u81ea\u52a8\u5c06 A \u80a1code\u8f6c\u6362\u4e3a yfinance \u683c\u5f0f (.SS / .SZ)
2. \u5904\u7406 Yahoo Finance data\u683c\u5f0f\u5dee\u5f02
3. failed\u540eindex\u9000\u907f\u91cd\u8bd5
"""

import csv
import logging
from datetime import datetime
from io import StringIO
from typing import Optional, List, Dict, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS, is_bse_code
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource
from .us_index_mapping import get_us_index_yf_symbol, is_us_stock_code
from src.services.market_symbol_utils import get_suffix_market, is_suffix_market_symbol

# optional\u5bfc\u5165\u672c\u5730\u80a1\u7968\u6620\u5c04\u8865\u4e01; \u82e5\u7f3a\u5931\u5219\u4f7f\u7528\u7a7a\u5b57\u5178\u515c\u5e95
try:
    from src.data.stock_mapping import STOCK_NAME_MAP, is_meaningful_stock_name
except (ImportError, ModuleNotFoundError):
    STOCK_NAME_MAP = {}

    def is_meaningful_stock_name(name: str | None, stock_code: str) -> bool:
        """\u7b80\u5355\u7684name\u6709\u6548\u6821\u9a8c\u515c\u5e95"""
        if not name:
            return False
        n = str(name).strip()
        return bool(n and n.upper() != str(stock_code).strip().upper())

import os

logger = logging.getLogger(__name__)


class YfinanceFetcher(BaseFetcher):
    """
    Yahoo Finance data source\u5b9e\u73b0

    \u4f18\u5148\u7ea7: 4 (\u6700Low; \u4f5c\u4e3a\u515c\u5e95)
    \u6570\u636esource: Yahoo Finance

    \u5173\u952estrategy:
    - \u81ea\u52a8\u8f6c\u6362stock code\u683c\u5f0f
    - \u5904\u7406\u65f6\u533a\u548c\u6570\u636e\u683c\u5f0f\u5dee\u5f02
    - failed\u540eindex\u9000\u907f\u91cd\u8bd5

    \u6ce8\u610f\u4e8b\u9879:
    - A \u80a1\u6570\u636e\u53ef\u80fd\u6709\u5ef6\u8fdf
    - \u67d0\u4e9b\u80a1\u7968\u53ef\u80fdno data
    - \u6570\u636e\u7cbe\u5ea6\u53ef\u80fd\u4e0e\u56fd\u5185\u6e90\u7565\u6709\u5dee\u5f02
    """

    name = "YfinanceFetcher"
    priority = int(os.getenv("YFINANCE_PRIORITY", "4"))

    def __init__(self):
        """\u521d\u59cb\u5316 YfinanceFetcher"""
        pass

    @staticmethod
    def _is_jp_kr_suffix_stock(stock_code: str) -> bool:
        """Return True for supported JP/KR suffix-only Yahoo symbols."""
        return is_suffix_market_symbol(stock_code, "jp") or is_suffix_market_symbol(stock_code, "kr")

    @staticmethod
    def _is_tw_suffix_stock(stock_code: str) -> bool:
        """Return True for supported Taiwan suffix-only Yahoo symbols (TWSE `.TW` / TPEx `.TWO`).

        Taiwan base codes are 4-6 digits (common stocks 4, ETFs/others up to 6,
        e.g. 00878 / 006208), wider than the JP `.T` range.
        """
        return is_suffix_market_symbol(stock_code, "tw")

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        \u8f6c\u6362stock code\u4e3a Yahoo Finance \u683c\u5f0f

        Yahoo Finance code\u683c\u5f0f:
        - A-share\u6caa\u5e02: 600519.SS (Shanghai Stock Exchange)
        - A-share\u6df1\u5e02: 000001.SZ (Shenzhen Stock Exchange)
        - HK stock: 0700.HK (Hong Kong Stock Exchange)
        - US stock: AAPL, TSLA, GOOGL (\u65e0\u9700\u540e\u7f00)

        Args:
            stock_code: \u539f\u59cbcode; \u5982 '600519', 'hk00700', 'AAPL'

        Returns:
            Yahoo Finance \u683c\u5f0fcode

        Examples:
            >>> fetcher._convert_stock_code('600519')
            '600519.SS'
            >>> fetcher._convert_stock_code('hk00700')
            '0700.HK'
            >>> fetcher._convert_stock_code('AAPL')
            'AAPL'
        """
        code = stock_code.strip().upper()

        # US stockindex: \u6620\u5c04\u5230 Yahoo Finance \u7b26\u53f7 (\u5982 SPX -> ^GSPC)
        yf_symbol, _ = get_us_index_yf_symbol(code)
        if yf_symbol:
            logger.debug(f"\u8bc6\u522b\u4e3aUS stockindex: {code} -> {yf_symbol}")
            return yf_symbol

        # US stock: 1-5 \u4e2a\u5927\u5199\u5b57\u6bcd (optional .X \u540e\u7f00); \u539f\u6837\u8fd4\u56de
        if is_us_stock_code(code):
            logger.debug(f"\u8bc6\u522b\u4e3aUS stockcode: {code}")
            return code

        # JP stock/KR stock/TW stock MVP: \u663e\u5f0f Yahoo Finance suffix-only code; \u539f\u6837\u4f20\u7ed9 Yahoo.
        if self._is_jp_kr_suffix_stock(code) or self._is_tw_suffix_stock(code):
            logger.debug(f"\u8bc6\u522b\u4e3a\u65e5\u97e9\u53f0 Yahoo suffix code: {code}")
            return code

        # HK stock: hkprefix -> .HK\u540e\u7f00
        if code.startswith('HK'):
            hk_code = code[2:].lstrip('0') or '0'  # \u53bb\u9664\u524d\u5bfc0; \u4f46\u4fdd\u7559\u81f3\u5c11\u4e00\u4e2a0
            hk_code = hk_code.zfill(4)  # \u8865\u9f50\u52304characters
            logger.debug(f"\u8f6c\u6362HK stockcode: {stock_code} -> {hk_code}.HK")
            return f"{hk_code}.HK"

        # \u5df2\u7ecf\u5305\u542b\u540e\u7f00\u7684\u60c5\u51b5
        if '.SS' in code or '.SZ' in code or '.HK' in code or '.BJ' in code:
            return code

        # \u53bb\u9664\u53ef\u80fd\u7684 .SH \u540e\u7f00
        code = code.replace('.SH', '')

        # ETF: Shanghai ETF (51xx, 52xx, 56xx, 58xx) -> .SS; Shenzhen ETF (15xx, 16xx, 18xx) -> .SZ
        if len(code) == 6:
            if code.startswith(('51', '52', '56', '58')):
                return f"{code}.SS"
            if code.startswith(('15', '16', '18')):
                return f"{code}.SZ"

        # BSE (Beijing Stock Exchange): 8xxxxx, 4xxxxx, 920xxx
        if is_bse_code(code):
            base = code.split('.')[0] if '.' in code else code
            return f"{base}.BJ"

        # A-share: \u6839\u636ecodeprefix\u5224\u65admarket
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SS"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            logger.warning(f"Unable to determine\u80a1\u7968 {code} \u7684market; default\u4f7f\u7528\u6df1\u5e02")
            return f"{code}.SZ"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u4ece Yahoo Finance \u83b7\u53d6\u539f\u59cb\u6570\u636e

        \u4f7f\u7528 yfinance.download() \u83b7\u53d6history\u6570\u636e

        \u6d41\u7a0b:
        1. \u8f6c\u6362stock code\u683c\u5f0f
        2. \u8c03\u7528 yfinance API
        3. \u5904\u7406\u8fd4\u56de\u6570\u636e
        """
        import yfinance as yf

        # \u8f6c\u6362code\u683c\u5f0f
        yf_code = self._convert_stock_code(stock_code)

        logger.debug(f"\u8c03\u7528 yfinance.download({yf_code}, {start_date}, {end_date})")

        try:
            # \u4f7f\u7528 yfinance \u4e0b\u8f7d\u6570\u636e
            df = yf.download(
                tickers=yf_code,
                start=start_date,
                end=end_date,
                progress=False,  # \u7981\u6b62\u8fdb\u5ea6\u6761
                auto_adjust=True,  # \u81ea\u52a8\u8c03\u6574price (\u590d\u6743)
                multi_level_index=True
            )

            # \u7b5b\u9009\u51fa yf_code \u7684\u5217, \u907f\u514d\u591astocks\u6570\u636e\u6df7\u6dc6
            if isinstance(df.columns, pd.MultiIndex) and len(df.columns) > 1:
                ticker_level = df.columns.get_level_values(1)
                mask = ticker_level == yf_code
                if mask.any():
                    df = df.loc[:, mask].copy()

            if df.empty:
                raise DataFetchError(f"Yahoo Finance found no data for {stock_code} data")

            return df

        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Yahoo Finance data fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        \u6807\u51c6\u5316 Yahoo Finance \u6570\u636e

        yfinance \u8fd4\u56de\u7684\u5217\u540d:
        Open, High, Low, Close, Volume (\u7d22\u5f15\u662fdate)

        \u6ce8\u610f: \u65b0\u7248 yfinance \u8fd4\u56de MultiIndex \u5217\u540d; \u5982 ('Close', 'AMD')
        \u9700\u8981\u5148\u6241\u5e73\u5316\u5217\u540d\u518d\u8fdb\u884c\u5904\u7406

        \u9700\u8981\u6620\u5c04\u5230\u6807\u51c6\u5217\u540d:
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # \u5904\u7406 MultiIndex \u5217\u540d (\u65b0\u7248 yfinance \u8fd4\u56de\u683c\u5f0f)
        # \u4f8b\u5982: ('Close', 'AMD') -> 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            logger.debug("\u68c0\u6d4b\u5230 MultiIndex \u5217\u540d; \u8fdb\u884c\u6241\u5e73\u5316\u5904\u7406")
            # \u53d6\u7b2c\u4e00\u7ea7\u5217\u540d (Price level: Close, High, Low, etc.)
            df.columns = df.columns.get_level_values(0)

        # \u91cd\u7f6e\u7d22\u5f15; \u5c06date\u4ece\u7d22\u5f15\u53d8\u4e3a\u5217
        df = df.reset_index()

        # \u5217\u540d\u6620\u5c04 (yfinance \u4f7f\u7528\u9996\u5b57\u6bcd\u5927\u5199)
        column_mapping = {
            'Date': 'date',
            'Datetime': 'date',
            'datetime': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }

        df = df.rename(columns=column_mapping)
        if 'date' not in df.columns:
            index_col = df.columns[0] if len(df.columns) else None
            if index_col is not None:
                candidate = df[index_col]
                if pd.api.types.is_datetime64_any_dtype(candidate):
                    df = df.rename(columns={index_col: 'date'})
                elif not pd.api.types.is_numeric_dtype(candidate):
                    parsed_dates = pd.to_datetime(candidate, errors='coerce')
                    if parsed_dates.notna().any():
                        df = df.rename(columns={index_col: 'date'})
                        df['date'] = parsed_dates

        # \u8ba1\u7b97change\u5e45 (\u56e0\u4e3a yfinance \u4e0d\u76f4\u63a5\u63d0\u4f9b)
        if 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)

        # \u8ba1\u7b97amount (yfinance \u4e0d\u63d0\u4f9b; \u4f7f\u7528\u4f30\u7b97\u503c)
        # amount ≈ volume * \u5e73\u5747price
        if 'volume' in df.columns and 'close' in df.columns:
            df['amount'] = df['volume'] * df['close']
        else:
            df['amount'] = 0

        # \u6dfb\u52a0stock code\u5217
        df['code'] = stock_code

        # \u53ea\u4fdd\u7559\u9700\u8981\u7684\u5217
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def _fetch_yf_ticker_data(self, yf, yf_code: str, name: str, return_code: str) -> Optional[Dict[str, Any]]:
        """
        \u901a\u8fc7 yfinance \u62c9\u53d6\u5355\u4e2aindex/\u80a1\u7968\u7684\u884c\u60c5\u6570\u636e.

        Args:
            yf: yfinance \u6a21chunks\u5f15\u7528
            yf_code: yfinance \u4f7f\u7528\u7684code (\u5982 '000001.SS'、'^GSPC')
            name: index\u663e\u793aname
            return_code: \u5199\u5165result dict \u7684 code \u5b57\u6bb5 (\u5982 'sh000001'、'SPX')

        Returns:
            \u884c\u60c5\u5b57\u5178; failed\u65f6\u8fd4\u56de None
        """
        ticker = yf.Ticker(yf_code)
        # \u53d6\u8fd1\u4e24\u65e5\u6570\u636e\u4ee5\u8ba1\u7b97change\u5e45
        hist = ticker.history(period='2d')
        if hist.empty:
            return None
        today_row = hist.iloc[-1]
        prev_row = hist.iloc[-2] if len(hist) > 1 else today_row
        price = float(today_row['Close'])
        prev_close = float(prev_row['Close'])
        change = price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0
        high = float(today_row['High'])
        low = float(today_row['Low'])
        # \u632f\u5e45 = (\u6700High - \u6700Low) / \u6628\u6536 * 100
        amplitude = ((high - low) / prev_close * 100) if prev_close else 0
        return {
            'code': return_code,
            'name': name,
            'current': price,
            'change': change,
            'change_pct': change_pct,
            'open': float(today_row['Open']),
            'high': high,
            'low': low,
            'prev_close': prev_close,
            'volume': float(today_row['Volume']),
            'amount': 0.0,  # Yahoo Finance \u4e0d\u63d0\u4f9b\u51c6\u786eamount
            'amplitude': amplitude,
        }

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        \u83b7\u53d6\u4e3b\u8981index\u884c\u60c5 (Yahoo Finance); \u652f\u6301 A \u80a1、US stock、HK stock、JP stock、KR stock\u4e0eTW stock.
        region=us \u65f6\u59d4\u6258\u7ed9 _get_us_main_indices.
        region=hk \u65f6\u59d4\u6258\u7ed9 _get_hk_main_indices.
        region=jp/kr/tw \u65f6\u5206\u522b\u59d4\u6258\u7ed9\u5bf9\u5e94marketindex\u65b9\u6cd5.
        """
        import yfinance as yf

        if region == "us":
            return self._get_us_main_indices(yf)
        if region == "hk":
            return self._get_hk_main_indices(yf)
        if region == "jp":
            return self._get_jp_main_indices(yf)
        if region == "kr":
            return self._get_kr_main_indices(yf)
        if region == "tw":
            return self._get_tw_main_indices(yf)

        # A \u80a1index: akshare code -> (yfinance code, \u663e\u793aname)
        yf_mapping = {
            'sh000001': ('000001.SS', '\u4e0a\u8bc1index'),
            'sz399001': ('399001.SZ', '\u6df1\u8bc1\u6210\u6307'),
            'sz399006': ('399006.SZ', '\u521b\u4e1a\u677f\u6307'),
            'sh000688': ('000688.SS', '\u79d1\u521b50'),
            'sh000016': ('000016.SS', '\u4e0a\u8bc150'),
            'sh000300': ('000300.SS', '\u6caa\u6df1300'),
        }

        results = []
        try:
            for ak_code, (yf_code, name) in yf_mapping.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_code, name, ak_code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] \u83b7\u53d6index {name} success")
                except Exception as e:
                    logger.warning(f"[Yfinance] \u83b7\u53d6index {name} failed: {e}")

            if results:
                logger.info(f"[Yfinance] success\u83b7\u53d6 {len(results)} \u4e2a A \u80a1index\u884c\u60c5")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] \u83b7\u53d6 A \u80a1index\u884c\u60c5failed: {e}")

        return None

    def _get_us_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6US stock\u4e3b\u8981index\u884c\u60c5 (SPX、IXIC、DJI、VIX); \u590d\u7528 _fetch_yf_ticker_data"""
        # market review\u6240\u9700\u6838\u5fc3US stockindex
        us_indices = ['SPX', 'IXIC', 'DJI', 'VIX']
        results = []
        try:
            for code in us_indices:
                yf_symbol, name = get_us_index_yf_symbol(code)
                if not yf_symbol:
                    continue
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] \u83b7\u53d6US stockindex {name} success")
                except Exception as e:
                    logger.warning(f"[Yfinance] \u83b7\u53d6US stockindex {name} failed: {e}")

            if results:
                logger.info(f"[Yfinance] success\u83b7\u53d6 {len(results)} \u4e2aUS stockindex\u884c\u60c5")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] \u83b7\u53d6US stockindex\u884c\u60c5failed: {e}")

        return None

    def _get_hk_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6HK stock\u4e3b\u8981index\u884c\u60c5 (HSI、HSTECH、HSCEI); \u590d\u7528 _fetch_yf_ticker_data"""
        # Yahoo Finance HK stockindex\u7b26\u53f7\u6620\u5c04:
        # - HSI -> ^HSI
        # - HSTECH -> HSTECH.HK (\u4e0d\u662f ^HSTECH)
        # - HSCEI -> ^HSCE (\u4e0d\u662f ^HSCEI)
        # \u8be5\u6620\u5c04\u7531\u79bb\u7ebf\u5355\u6d4b tests/test_yfinance_hk_indices.py \u56fa\u5316; \u907f\u514d\u5728\u7ebf\u4f9d\u8d56\u5bfc\u81f4\u975e\u786e\u5b9afailed.
        hk_indices = {
            'HSI': ('^HSI', '\u6052\u751findex'),
            'HSTECH': ('HSTECH.HK', '\u6052\u751f\u79d1\u6280index'),
            'HSCEI': ('^HSCE', '\u56fd\u4f01index'),
        }
        results = []
        try:
            for code, (yf_symbol, name) in hk_indices.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] \u83b7\u53d6HK stockindex {name} success")
                except Exception as e:
                    logger.warning(f"[Yfinance] \u83b7\u53d6HK stockindex {name} failed: {e}")

            if results:
                logger.info(f"[Yfinance] success\u83b7\u53d6 {len(results)} \u4e2aHK stockindex\u884c\u60c5")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] \u83b7\u53d6HK stockindex\u884c\u60c5failed: {e}")

        return None

    def _get_jp_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6\u65e5\u672c\u4e3b\u8981index\u884c\u60c5 (\u65e5\u7ecf225、TOPIX); \u590d\u7528 _fetch_yf_ticker_data."""
        jp_indices = {
            'N225': ('^N225', '\u65e5\u7ecf225'),
            'TOPX': ('^TOPX', '\u4e1c\u8bc1index'),
        }
        results = []
        try:
            for code, (yf_symbol, name) in jp_indices.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] \u83b7\u53d6\u65e5\u672cindex {name} success")
                except Exception as e:
                    logger.warning(f"[Yfinance] \u83b7\u53d6\u65e5\u672cindex {name} failed: {e}")
            if results:
                logger.info(f"[Yfinance] success\u83b7\u53d6 {len(results)} \u4e2a\u65e5\u672cindex\u884c\u60c5")
                return results
        except Exception as e:
            logger.error(f"[Yfinance] \u83b7\u53d6\u65e5\u672cindex\u884c\u60c5failed: {e}")
        return None

    def _get_kr_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6\u97e9\u56fd\u4e3b\u8981index\u884c\u60c5 (KOSPI、KOSDAQ); \u590d\u7528 _fetch_yf_ticker_data."""
        kr_indices = {
            'KS11': ('^KS11', 'KOSPI'),
            'KQ11': ('^KQ11', 'KOSDAQ'),
        }
        results = []
        try:
            for code, (yf_symbol, name) in kr_indices.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] \u83b7\u53d6\u97e9\u56fdindex {name} success")
                except Exception as e:
                    logger.warning(f"[Yfinance] \u83b7\u53d6\u97e9\u56fdindex {name} failed: {e}")
            if results:
                logger.info(f"[Yfinance] success\u83b7\u53d6 {len(results)} \u4e2a\u97e9\u56fdindex\u884c\u60c5")
                return results
        except Exception as e:
            logger.error(f"[Yfinance] \u83b7\u53d6\u97e9\u56fdindex\u884c\u60c5failed: {e}")
        return None

    def _get_tw_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6\u53f0\u6e7e\u4e3b\u8981index\u884c\u60c5 (\u52a0\u6743index ^TWII、\u67dc\u4e70index ^TWOII); \u590d\u7528 _fetch_yf_ticker_data."""
        tw_indices = {
            'TWII': ('^TWII', '\u53f0\u6e7e\u52a0\u6743index'),
            'TWOII': ('^TWOII', '\u53f0\u6e7e\u67dc\u4e70index'),
        }
        results = []
        try:
            for code, (yf_symbol, name) in tw_indices.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] \u83b7\u53d6\u53f0\u6e7eindex {name} success")
                except Exception as e:
                    logger.warning(f"[Yfinance] \u83b7\u53d6\u53f0\u6e7eindex {name} failed: {e}")
            if results:
                logger.info(f"[Yfinance] success\u83b7\u53d6 {len(results)} \u4e2a\u53f0\u6e7eindex\u884c\u60c5")
                return results
        except Exception as e:
            logger.error(f"[Yfinance] \u83b7\u53d6\u53f0\u6e7eindex\u884c\u60c5failed: {e}")
        return None

    def _is_us_stock(self, stock_code: str) -> bool:
        """
        \u5224\u65adcode\u662f\u5426\u4e3aUS stock\u80a1\u7968 (\u6392\u9664US stockindex).

        \u59d4\u6258\u7ed9 us_index_mapping \u6a21chunks\u7684 is_us_stock_code().
        """
        return is_us_stock_code(stock_code)

    def _get_us_stock_quote_from_stooq(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u4f7f\u7528 Stooq \u4e3aUS stockrealtime quote\u63d0\u4f9b\u514d\u5bc6\u94a5\u515c\u5e95.

        Stooq \u63d0\u4f9b\u7684\u662f\u6700\u65b0\u4ea4\u6613\u65e5\u884c\u60c5; \u7cbe\u5ea6\u4e0d\u5982\u5206\u65f6\u5b9e\u65f6\u63a5\u53e3; \u4f46\u5728 Yahoo / yfinance
        \u88ab\u9650\u6d41\u65f6; \u81f3\u5c11\u80fd\u4e3a Web UI \u63d0\u4f9b\u53ef\u7528price；\u82e5\u53ef\u83b7\u53d6\u5230\u6628\u6536\u4ef7; \u5219\u540c\u65f6\u63d0\u4f9bchange\u5e45\u7b49\u884d\u751f\u6307\u6807.
        """
        symbol = stock_code.strip().upper()
        stooq_symbol = f"{symbol.lower()}.us"
        url = f"https://stooq.com/q/l/?s={stooq_symbol}"
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DSA/1.0; +https://github.com/ZhuLinsen/daily_stock_analysis)",
                "Accept": "text/plain,text/csv,*/*",
            },
        )

        try:
            with urlopen(request, timeout=15) as response:
                payload = response.read().decode("utf-8", "ignore").strip()
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning(f"[Stooq] \u83b7\u53d6US stock {symbol} realtime quotefailed: {exc}")
            return None

        if not payload or payload.upper().startswith("NO DATA"):
            logger.warning(f"[Stooq] \u65e0\u6cd5\u83b7\u53d6 {symbol} \u7684\u884c\u60c5\u6570\u636e")
            return None

        def _fetch_prev_close() -> Optional[float]:
            history_url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
            history_request = Request(
                history_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DSA/1.0; +https://github.com/ZhuLinsen/daily_stock_analysis)",
                    "Accept": "text/plain,text/csv,*/*",
                },
            )
            try:
                with urlopen(history_request, timeout=15) as response:
                    history_payload = response.read().decode("utf-8", "ignore").strip()
            except (HTTPError, URLError, TimeoutError) as exc:
                logger.debug(f"[Stooq] \u83b7\u53d6US stock {symbol} daily datahistoryfailed: {exc}")
                return None

            if not history_payload or history_payload.upper().startswith("NO DATA"):
                return None

            try:
                reader = csv.reader(StringIO(history_payload))
                header = next(reader, None)
                if not header:
                    return None

                header_tokens = [cell.strip().lower() for cell in header]
                has_header = "close" in header_tokens and "date" in header_tokens
                if not has_header:
                    return None

                date_index = header_tokens.index("date")
                close_index = header_tokens.index("close")

                daily_rows: list[tuple[datetime, float]] = []
                for row in reader:
                    if not row:
                        continue
                    date_text = row[date_index].strip() if len(row) > date_index else ""
                    close_text = row[close_index].strip() if len(row) > close_index else ""
                    if not date_text or not close_text:
                        continue
                    try:
                        dt = datetime.strptime(date_text, "%Y-%m-%d")
                        close_val = float(close_text)
                    except Exception:
                        continue
                    daily_rows.append((dt, close_val))

                if len(daily_rows) < 2:
                    return None

                daily_rows.sort(key=lambda item: item[0])
                return daily_rows[-2][1]
            except Exception:
                return None

        try:
            reader = csv.reader(StringIO(payload))
            first_row = next(reader, None)
            if first_row is None:
                raise ValueError(f"unexpected Stooq payload: {payload}")

            normalized_first_row = [cell.strip() for cell in first_row]
            header_tokens = {cell.lower() for cell in normalized_first_row if cell}
            has_header = 'open' in header_tokens and 'close' in header_tokens
            row = next(reader, None) if has_header else first_row
            if row is None:
                raise ValueError(f"unexpected Stooq payload: {payload}")

            normalized_row = [cell.strip() for cell in row]
            while normalized_row and normalized_row[-1] == '':
                normalized_row.pop()

            if len(normalized_row) >= 8:
                open_index, high_index, low_index, price_index, volume_index = 3, 4, 5, 6, 7
            elif len(normalized_row) >= 7:
                open_index, high_index, low_index, price_index, volume_index = 2, 3, 4, 5, 6
            else:
                raise ValueError(f"unexpected Stooq payload: {payload}")

            open_price = float(normalized_row[open_index])
            high = float(normalized_row[high_index])
            low = float(normalized_row[low_index])
            price = float(normalized_row[price_index])
            volume = int(float(normalized_row[volume_index]))

            prev_close = _fetch_prev_close()
            change_amount = None
            change_pct = None
            amplitude = None
            if prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100
                amplitude = ((high - low) / prev_close) * 100

            quote = UnifiedRealtimeQuote(
                code=symbol,
                name=STOCK_NAME_MAP.get(symbol, ''),
                source=RealtimeSource.STOOQ,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=None,
                circ_mv=None,
            )
            logger.info(f"[Stooq] \u83b7\u53d6US stock {symbol} \u515c\u5e95\u884c\u60c5success: price={price}")
            return quote
        except Exception as exc:
            logger.warning(f"[Stooq] \u89e3\u6790US stock {symbol} \u884c\u60c5failed: {exc}")
            return None

    def _get_us_index_realtime_quote(
        self,
        user_code: str,
        yf_symbol: str,
        index_name: str,
    ) -> Optional[UnifiedRealtimeQuote]:
        """
        Get realtime quote for US index (e.g. SPX -> ^GSPC).

        Args:
            user_code: User input code (e.g. SPX)
            yf_symbol: Yahoo Finance symbol (e.g. ^GSPC)
            index_name: Chinese name for the index

        Returns:
            UnifiedRealtimeQuote or None
        """
        import yfinance as yf

        try:
            logger.debug(f"[Yfinance] \u83b7\u53d6US stockindex {user_code} ({yf_symbol}) realtime quote")
            ticker = yf.Ticker(yf_symbol)

            try:
                info = ticker.fast_info
                if info is None:
                    raise ValueError("fast_info is None")
                price = getattr(info, 'lastPrice', None) or getattr(info, 'last_price', None)
                prev_close = getattr(info, 'previousClose', None) or getattr(info, 'previous_close', None)
                open_price = getattr(info, 'open', None)
                high = getattr(info, 'dayHigh', None) or getattr(info, 'day_high', None)
                low = getattr(info, 'dayLow', None) or getattr(info, 'day_low', None)
                volume = getattr(info, 'lastVolume', None) or getattr(info, 'last_volume', None)
            except Exception:
                logger.debug("[Yfinance] fast_info failed; \u5c1d\u8bd5 history \u65b9\u6cd5")
                hist = ticker.history(period='2d')
                if hist.empty:
                    logger.warning(f"[Yfinance] \u65e0\u6cd5\u83b7\u53d6 {yf_symbol} data")
                    return None
                today = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else today
                price = float(today['Close'])
                prev_close = float(prev['Close'])
                open_price = float(today['Open'])
                high = float(today['High'])
                low = float(today['Low'])
                volume = int(today['Volume'])

            change_amount = None
            change_pct = None
            if price is not None and prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100

            amplitude = None
            if high is not None and low is not None and prev_close is not None and prev_close > 0:
                amplitude = ((high - low) / prev_close) * 100

            try:
                ticker_info = ticker.info or {}
            except Exception:
                ticker_info = {}
            missing_fields = [
                field
                for field, value in {
                    "price": price,
                    "prev_close": prev_close,
                    "volume": volume,
                    "amount": None,
                    "pe_ratio": None,
                    "pb_ratio": None,
                }.items()
                if value is None
            ]

            quote = UnifiedRealtimeQuote(
                code=user_code,
                name=index_name or user_code,
                source=RealtimeSource.FALLBACK,
                market="us",
                currency=str(ticker_info.get("currency") or "").upper() or None,
                data_quality="partial" if missing_fields else "ok",
                missing_fields=missing_fields or None,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=None,
                circ_mv=None,
            )
            logger.info(f"[Yfinance] \u83b7\u53d6US stockindex {user_code} realtime quotesuccess: price={price}")
            return quote
        except Exception as e:
            logger.warning(f"[Yfinance] \u83b7\u53d6US stockindex {user_code} realtime quotefailed: {e}")
            return None

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6US stock/US stockindexrealtime quote\u6570\u636e

        \u652f\u6301US stock\u80a1\u7968 (AAPL、TSLA)\u548cUS stockindex (SPX、DJI \u7b49).
        \u6570\u636esource: yfinance Ticker.info

        Args:
            stock_code: US stockcodeorindexcode; \u5982 'AMD', 'AAPL', 'SPX', 'DJI'

        Returns:
            UnifiedRealtimeQuote \u5bf9\u8c61; fetch failed\u8fd4\u56de None
        """
        import yfinance as yf

        # US stockindex: \u4f7f\u7528\u6620\u5c04 (SPX -> ^GSPC)
        yf_symbol, index_name = get_us_index_yf_symbol(stock_code)
        if yf_symbol:
            return self._get_us_index_realtime_quote(
                user_code=stock_code.strip().upper(),
                yf_symbol=yf_symbol,
                index_name=index_name,
            )

        # \u4ec5\u5904\u7406US stock\u80a1\u7968or JP/KR/TW suffix-only \u80a1\u7968
        if not (
            self._is_us_stock(stock_code)
            or self._is_jp_kr_suffix_stock(stock_code)
            or self._is_tw_suffix_stock(stock_code)
        ):
            logger.debug(f"[Yfinance] {stock_code} \u4e0d\u662fUS stockor\u65e5\u97e9 suffix code; skipping")
            return None

        try:
            symbol = self._convert_stock_code(stock_code)
            is_us_symbol = self._is_us_stock(symbol)
            suffix_market = get_suffix_market(symbol)
            logger.debug(f"[Yfinance] \u83b7\u53d6 {symbol} realtime quote")

            ticker = yf.Ticker(symbol)

            # \u5c1d\u8bd5\u83b7\u53d6 fast_info (\u66f4\u5feb; \u4f46\u5b57\u6bb5\u8f83\u5c11)
            try:
                info = ticker.fast_info
                if info is None:
                    raise ValueError("fast_info is None")

                price = getattr(info, 'lastPrice', None) or getattr(info, 'last_price', None)
                prev_close = getattr(info, 'previousClose', None) or getattr(info, 'previous_close', None)
                open_price = getattr(info, 'open', None)
                high = getattr(info, 'dayHigh', None) or getattr(info, 'day_high', None)
                low = getattr(info, 'dayLow', None) or getattr(info, 'day_low', None)
                volume = getattr(info, 'lastVolume', None) or getattr(info, 'last_volume', None)
                market_cap = getattr(info, 'marketCap', None) or getattr(info, 'market_cap', None)

            except Exception:
                # \u56de\u9000\u5230 history \u65b9\u6cd5\u83b7\u53d6\u6700\u65b0\u6570\u636e
                logger.debug("[Yfinance] fast_info failed; \u5c1d\u8bd5 history \u65b9\u6cd5")
                hist = ticker.history(period='2d')
                if hist.empty:
                    if is_us_symbol:
                        logger.warning(f"[Yfinance] \u65e0\u6cd5\u83b7\u53d6 {symbol} data; \u5c1d\u8bd5 Stooq \u515c\u5e95")
                        return self._get_us_stock_quote_from_stooq(symbol)
                    logger.warning(f"[Yfinance] \u65e0\u6cd5\u83b7\u53d6 {symbol} data")
                    return None

                today = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else today

                price = float(today['Close'])
                prev_close = float(prev['Close'])
                open_price = float(today['Open'])
                high = float(today['High'])
                low = float(today['Low'])
                volume = int(today['Volume'])
                market_cap = None

            # \u8ba1\u7b97change\u5e45
            change_amount = None
            change_pct = None
            if price is not None and prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100

            # \u8ba1\u7b97\u632f\u5e45
            amplitude = None
            if high is not None and low is not None and prev_close is not None and prev_close > 0:
                amplitude = ((high - low) / prev_close) * 100

            # \u83b7\u53d6stock name\u4e0e provider \u5143\u6570\u636e
            try:
                ticker_info = ticker.info or {}
            except Exception:
                ticker_info = {}
            try:
                info_name = ticker_info.get('shortName', '') or ticker_info.get('longName', '') or ''
                name = info_name if is_meaningful_stock_name(info_name, symbol) else STOCK_NAME_MAP.get(symbol, '')
            except Exception:
                name = STOCK_NAME_MAP.get(symbol, '')

            missing_fields = [
                field
                for field, value in {
                    "price": price,
                    "prev_close": prev_close,
                    "volume": volume,
                    "amount": None,
                    "pe_ratio": None,
                    "pb_ratio": None,
                }.items()
                if value is None
            ]
            quote = UnifiedRealtimeQuote(
                code=symbol,
                name=name,
                source=RealtimeSource.FALLBACK,
                market=suffix_market or ("us" if is_us_symbol else None),
                currency=str(ticker_info.get("currency") or "").upper() or None,
                data_quality="partial" if missing_fields else "ok",
                missing_fields=missing_fields or None,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,  # yfinance \u4e0d\u76f4\u63a5\u63d0\u4f9bamount
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=market_cap,
                circ_mv=None,
            )

            logger.info(f"[Yfinance] \u83b7\u53d6 {symbol} realtime quotesuccess: price={price}")
            return quote

        except Exception as e:
            if self._is_us_stock(stock_code):
                logger.warning(f"[Yfinance] \u83b7\u53d6US stock {stock_code} realtime quotefailed: {e}; \u5c1d\u8bd5 Stooq \u515c\u5e95")
                return self._get_us_stock_quote_from_stooq(stock_code)
            logger.warning(f"[Yfinance] \u83b7\u53d6 {stock_code} realtime quotefailed: {e}")
            return None


if __name__ == "__main__":
    # \u6d4b\u8bd5code
    logging.basicConfig(level=logging.DEBUG)

    fetcher = YfinanceFetcher()

    try:
        df = fetcher.get_daily_data('600519')  # \u8305\u53f0
        print(f"fetch succeeded; \u5171 {len(df)} \u6761\u6570\u636e")
        print(df.tail())
    except Exception as e:
        print(f"fetch failed: {e}")
