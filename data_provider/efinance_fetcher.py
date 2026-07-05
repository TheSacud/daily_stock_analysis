# -*- coding: utf-8 -*-
"""
===================================
EfinanceFetcher - \u4f18\u5148data source (Priority 0)
===================================

\u6570\u636esource: Eastmoney\u722c\u866b (\u901a\u8fc7 efinance library)
\u7279\u70b9: \u514d\u8d39、\u65e0\u9700 Token、\u6570\u636e\u5168\u9762、API \u7b80\u6d01
\u4ed3library: https://github.com/Micro-sheep/efinance

\u4e0e AkshareFetcher \u7c7b\u4f3c; \u4f46 efinance library:
1. API \u66f4\u7b80\u6d01\u6613\u7528
2. \u652f\u6301batch\u83b7\u53d6\u6570\u636e
3. \u66f4\u7a33\u5b9a\u7684\u63a5\u53e3\u5c01\u88c5

\u9632\u5c01\u7981strategy:
1. \u6bcf\u6b21request\u524d\u968f\u673a\u4f11\u7720 1.5-3.0 \u79d2
2. \u968f\u673a\u8f6e\u6362 User-Agent
3. \u4f7f\u7528 tenacity \u5b9e\u73b0index\u9000\u907f\u91cd\u8bd5
4. \u7194\u65ad\u5668\u673a\u5236: \u8fde\u7eedfailed\u540e\u81ea\u52a8\u51b7\u5374
"""

import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import requests  # \u5f15\u5165 requests \u4ee5\u6355\u83b7\u5f02\u5e38
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Timeout (seconds) for efinance library calls that go through eastmoney APIs
# with no built-in timeout.  Prevents indefinite hangs when hosts are unreachable.
try:
    _EF_CALL_TIMEOUT = int(os.environ.get("EFINANCE_CALL_TIMEOUT", "30"))
except (ValueError, TypeError):
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "EFINANCE_CALL_TIMEOUT is not a valid integer, using default 30s"
    )
    _EF_CALL_TIMEOUT = 30

from src.patches.eastmoney_patch import eastmoney_patch
from src.config import get_config
from .base import (
    BaseFetcher,
    DataFetchError,
    RateLimitError,
    STANDARD_COLUMNS,
    is_bse_code,
    is_st_stock,
    is_kc_cy_stock,
    normalize_stock_code,
    _is_hk_market,
    _is_etf_code as _is_a_share_etf_code,
)
from .realtime_types import (
    UnifiedRealtimeQuote, RealtimeSource,
    get_realtime_circuit_breaker,
    safe_float, safe_int  # \u4f7f\u7528\u7edf\u4e00\u7684\u7c7b\u578b\u8f6c\u6362\u51fd\u6570
)


# \u4fdd\u7559\u65e7\u7684\u7c7b\u578balias; \u7528\u4e8e\u5411\u540e\u517c\u5bb9
@dataclass
class EfinanceRealtimeQuote:
    """
    realtime quote\u6570\u636e (\u6765\u81ea efinance)- \u5411\u540e\u517c\u5bb9alias

    \u65b0code\u5efa\u8bae\u4f7f\u7528 UnifiedRealtimeQuote
    """
    code: str
    name: str = ""
    price: float = 0.0           # \u6700\u65b0\u4ef7
    change_pct: float = 0.0      # change\u5e45(%)
    change_amount: float = 0.0   # change\u989d

    # \u91cf\u4ef7\u6307\u6807
    volume: int = 0              # volume
    amount: float = 0.0          # amount
    turnover_rate: float = 0.0   # turnover(%)
    amplitude: float = 0.0       # \u632f\u5e45(%)

    # price\u533a\u95f4
    high: float = 0.0            # \u6700High\u4ef7
    low: float = 0.0             # \u6700Low\u4ef7
    open_price: float = 0.0      # \u5f00\u76d8\u4ef7

    def to_dict(self) -> Dict[str, Any]:
        """\u8f6c\u6362\u4e3a\u5b57\u5178"""
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'volume': self.volume,
            'amount': self.amount,
            'turnover_rate': self.turnover_rate,
            'amplitude': self.amplitude,
            'high': self.high,
            'low': self.low,
            'open': self.open_price,
        }


logger = logging.getLogger(__name__)

EASTMONEY_HISTORY_ENDPOINT = "push2his.eastmoney.com/api/qt/stock/kline/get"


# User-Agent \u6c60; \u7528\u4e8e\u968f\u673a\u8f6e\u6362
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


# cacherealtime quote\u6570\u636e (\u907f\u514d\u91cd\u590drequest)
# TTL \u8bbe\u4e3a 10 \u5206\u949f (600\u79d2): batchanalyze\u573a\u666f\u4e0b\u907f\u514d\u91cd\u590d\u62c9\u53d6
_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 600  # 10\u5206\u949fcache\u6709\u6548\u671f
}

# ETF realtime quotecache (\u4e0e\u80a1\u7968\u5206\u5f00cache)
_etf_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 600  # 10\u5206\u949fcache\u6709\u6548\u671f
}

_ETF_SH_PREFIXES = ('51', '52', '56', '58')
_ETF_SZ_PREFIXES = ('15', '16', '18')


def _is_etf_code(stock_code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3a ETF \u57fa\u91d1

    ETF code\u89c4\u5219:
    - \u4e0a\u4ea4\u6240 ETF: 51xxxx, 52xxxx, 56xxxx, 58xxxx
    - \u6df1\u4ea4\u6240 ETF: 15xxxx, 16xxxx, 18xxxx

    Args:
        stock_code: \u80a1\u7968/\u57fa\u91d1code

    Returns:
        True \u8868\u793a\u662f ETF code; False \u8868\u793a\u662f\u666e\u901astock code
    """
    return _is_a_share_etf_code(stock_code)


def _build_eastmoney_etf_secid(stock_code: str) -> str:
    """Build Eastmoney secid for A-share ETF historical K-line queries."""
    code = normalize_stock_code(stock_code)
    if not _is_etf_code(code):
        raise DataFetchError(f"Unable to identify ETF code {stock_code}")
    if code.startswith(_ETF_SH_PREFIXES):
        return f"1.{code}"
    if code.startswith(_ETF_SZ_PREFIXES):
        return f"0.{code}"
    raise DataFetchError(f"Unable to determine ETF {stock_code} \u7684 Eastmoney marketprefix")


def _is_us_code(stock_code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3aUS stock

    US stockcode\u89c4\u5219:
    - 1-5\u4e2a\u5927\u5199\u5b57\u6bcd; \u5982 'AAPL', 'TSLA'
    - \u53ef\u80fd\u5305\u542b '.'; \u5982 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


def _ef_call_with_timeout(func, *args, timeout=None, **kwargs):
    """Run an efinance library call in a thread with a timeout.

    efinance internally uses requests/urllib3 with no timeout, so when
    eastmoney hosts are unreachable the call can hang for many minutes.
    This helper caps the *calling thread's* wait time.  Note: Python threads
    cannot be forcibly killed, so the worker thread may continue running in
    the background until the OS-level TCP timeout fires or the process exits.
    This is acceptable — the calling thread returns promptly on timeout.
    """
    if timeout is None:
        timeout = _EF_CALL_TIMEOUT
    # Do NOT use 'with ThreadPoolExecutor(...)' here: the context manager calls
    # shutdown(wait=True) on __exit__, which would re-block on the hung thread.
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=timeout)
    finally:
        # wait=False: calling thread returns immediately; worker cleans up later
        executor.shutdown(wait=False)


def _classify_eastmoney_error(exc: Exception) -> Tuple[str, str]:
    """
    Classify Eastmoney request failures into stable log categories.
    """
    message = str(exc).strip()
    lowered = message.lower()

    remote_disconnect_keywords = (
        'remotedisconnected',
        'remote end closed connection without response',
        'connection aborted',
        'connection broken',
        'protocolerror',
    )
    timeout_keywords = (
        'timeout',
        'timed out',
        'readtimeout',
        'connecttimeout',
    )
    rate_limit_keywords = (
        'banned',
        'blocked',
        '\u9891\u7387',
        'rate limit',
        'too many requests',
        '429',
        'limit',
        'forbidden',
        '403',
    )

    if any(keyword in lowered for keyword in remote_disconnect_keywords):
        return "remote_disconnect", message
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)) or any(
        keyword in lowered for keyword in timeout_keywords
    ):
        return "timeout", message
    if any(keyword in lowered for keyword in rate_limit_keywords):
        return "rate_limit_or_anti_bot", message
    if isinstance(exc, requests.exceptions.RequestException):
        return "request_error", message
    return "unknown_request_error", message


class EfinanceFetcher(BaseFetcher):
    """
    Efinance data source\u5b9e\u73b0

    \u4f18\u5148\u7ea7: 0 (\u6700High; \u4f18\u5148\u4e8e AkshareFetcher)
    \u6570\u636esource: Eastmoney\u7f51 (\u901a\u8fc7 efinance library\u5c01\u88c5)
    \u4ed3library: https://github.com/Micro-sheep/efinance

    \u4e3b\u8981 API:
    - ef.stock.get_quote_history(): \u83b7\u53d6history K \u7ebf\u6570\u636e
    - ef.stock.get_base_info(): \u83b7\u53d6\u80a1\u7968\u57fa\u672cinfo
    - ef.stock.get_realtime_quotes(): \u83b7\u53d6realtime quote

    \u5173\u952estrategy:
    - \u6bcf\u6b21request\u524d\u968f\u673a\u4f11\u7720 1.5-3.0 \u79d2
    - \u968f\u673a User-Agent \u8f6e\u6362
    - failed\u540eindex\u9000\u907f\u91cd\u8bd5 (\u6700\u591a3\u6b21)
    """

    name = "EfinanceFetcher"
    priority = int(os.getenv("EFINANCE_PRIORITY", "0"))  # \u6700High\u4f18\u5148\u7ea7; \u6392\u5728 AkshareFetcher \u4e4b\u524d

    def __init__(self, sleep_min: float = 1.5, sleep_max: float = 3.0):
        """
        \u521d\u59cb\u5316 EfinanceFetcher

        Args:
            sleep_min: \u6700\u5c0f\u4f11\u7720\u65f6\u95f4 (\u79d2)
            sleep_max: \u6700\u5927\u4f11\u7720\u65f6\u95f4 (\u79d2)
        """
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self._last_request_time: Optional[float] = None
        # \u4e1c\u8d22\u8865\u4e01\u5f00\u542f\u624d\u6267\u884c\u6253\u8865\u4e01\u64cd\u4f5c
        if get_config().enable_eastmoney_patch:
            eastmoney_patch()

    @staticmethod
    def _build_history_failure_message(
        stock_code: str,
        beg_date: str,
        end_date: str,
        exc: Exception,
        elapsed: float,
        is_etf: bool = False,
    ) -> Tuple[str, str]:
        category, detail = _classify_eastmoney_error(exc)
        instrument_type = "ETF" if is_etf else "stock"
        message = (
            "Eastmoney historyK\u7ebf\u63a5\u53e3failed: "
            f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
            f"market_type={instrument_type}, range={beg_date}~{end_date}, "
            f"category={category}, error_type={type(exc).__name__}, elapsed={elapsed:.2f}s, detail={detail}"
        )
        return category, message

    def _set_random_user_agent(self) -> None:
        """
        \u8bbe\u7f6e\u968f\u673a User-Agent

        \u901a\u8fc7\u4fee\u6539 requests Session \u7684 headers \u5b9e\u73b0
        \u8fd9\u662f\u5173\u952e\u7684\u53cd\u722cstrategy\u4e4b\u4e00
        """
        try:
            random_ua = random.choice(USER_AGENTS)
            logger.debug(f"\u8bbe\u7f6e User-Agent: {random_ua[:50]}...")
        except Exception as e:
            logger.debug(f"\u8bbe\u7f6e User-Agent failed: {e}")

    def _enforce_rate_limit(self) -> None:
        """
        \u5f3a\u5236\u6267\u884c\u901f\u7387limit

        strategy:
        1. \u68c0check\u8ddd\u79bb\u4e0a\u6b21request\u7684\u65f6\u95f4\u95f4\u9694
        2. \u5982\u679c\u95f4\u9694\u4e0d\u8db3; \u8865\u5145\u4f11\u7720\u65f6\u95f4
        3. \u7136\u540e\u518d\u6267\u884c\u968f\u673a jitter \u4f11\u7720
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            min_interval = self.sleep_min
            if elapsed < min_interval:
                additional_sleep = min_interval - elapsed
                logger.debug(f"\u8865\u5145\u4f11\u7720 {additional_sleep:.2f} \u79d2")
                time.sleep(additional_sleep)

        # \u6267\u884c\u968f\u673a jitter \u4f11\u7720
        self.random_sleep(self.sleep_min, self.sleep_max)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(1),  # \u51cf\u5c11\u52301\u6b21; \u907f\u514d\u89e6\u53d1\u9650\u6d41
        wait=wait_exponential(multiplier=1, min=4, max=60),  # \u4fdd\u6301waiting\u65f6\u95f4\u8bbe\u7f6e
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            requests.exceptions.RequestException,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u4ece efinance \u83b7\u53d6\u539f\u59cb\u6570\u636e

        \u6839\u636ecode\u7c7b\u578b\u81ea\u52a8\u9009\u62e9 API:
        - US stock: does not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        - \u666e\u901a\u80a1\u7968: \u4f7f\u7528 ef.stock.get_quote_history()
        - ETF \u57fa\u91d1: \u4f7f\u7528 ef.stock.get_quote_history() (ETF \u662f\u4ea4\u6613\u6240\u8bc1\u5238; \u4f7f\u7528\u80a1\u7968 K \u7ebf\u63a5\u53e3)

        \u6d41\u7a0b:
        1. \u5224\u65adcode\u7c7b\u578b (US stock/\u80a1\u7968/ETF)
        2. \u8bbe\u7f6e\u968f\u673a User-Agent
        3. \u6267\u884c\u901f\u7387limit (\u968f\u673a\u4f11\u7720)
        4. \u8c03\u7528\u5bf9\u5e94\u7684 efinance API
        5. \u5904\u7406\u8fd4\u56de\u6570\u636e
        """
        # US stockdoes not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230 AkshareFetcher/YfinanceFetcher
        if _is_us_code(stock_code):
            raise DataFetchError(f"EfinanceFetcher does not supportUS stock {stock_code}; please use AkshareFetcher or YfinanceFetcher")

        # efinance \u7684history K \u7ebf\u63a5\u53e3\u5728HK stockcode\u4e0a\u53ef\u80fd\u8fd4\u56de\u975e\u9884\u671fmarket\u6570\u636e;
        # \u660e\u786eskipping\u5e76\u4ea4\u7ed9 AkShare/Tushare/YFinance/Longbridge \u7b49HK stock\u8def\u5f84\u515c\u5e95.
        if _is_hk_market(stock_code):
            raise DataFetchError(f"EfinanceFetcher does not supportHK stockdaily data {stock_code}; please use AkshareFetcher orotherHK stockdata source")

        # \u6839\u636ecode\u7c7b\u578b\u9009\u62e9\u4e0d\u540c\u7684\u83b7\u53d6\u65b9\u6cd5
        if _is_etf_code(stock_code):
            return self._fetch_etf_data(stock_code, start_date, end_date)
        else:
            return self._fetch_stock_data(stock_code, start_date, end_date)

    def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u83b7\u53d6\u666e\u901a A \u80a1history\u6570\u636e

        \u6570\u636esource: ef.stock.get_quote_history()

        API parameter\u8bf4\u660e:
        - stock_codes: stock code
        - beg: \u5f00\u59cbdate; \u683c\u5f0f 'YYYYMMDD'
        - end: \u7ed3\u675fdate; \u683c\u5f0f 'YYYYMMDD'
        - klt: \u5468\u671f; 101=daily data
        - fqt: \u590d\u6743\u65b9\u5f0f; 1=\u524d\u590d\u6743
        """
        import efinance as ef

        # \u9632\u5c01\u7981strategy 1: \u968f\u673a User-Agent
        self._set_random_user_agent()

        # \u9632\u5c01\u7981strategy 2: \u5f3a\u5236\u4f11\u7720
        self._enforce_rate_limit()

        # \u683c\u5f0f\u5316date (efinance \u4f7f\u7528 YYYYMMDD \u683c\u5f0f)
        beg_date = start_date.replace('-', '')
        end_date_fmt = end_date.replace('-', '')

        logger.info(f"[API call] ef.stock.get_quote_history(stock_codes={stock_code}, "
                   f"beg={beg_date}, end={end_date_fmt}, klt=101, fqt=1)")

        api_start = time.time()
        try:
            # \u8c03\u7528 efinance \u83b7\u53d6 A \u80a1daily data\u6570\u636e
            # klt=101 \u83b7\u53d6daily data\u6570\u636e
            # fqt=1 \u83b7\u53d6\u524d\u590d\u6743\u6570\u636e
            df = _ef_call_with_timeout(
                ef.stock.get_quote_history,
                stock_codes=stock_code,
                beg=beg_date,
                end=end_date_fmt,
                klt=101,  # daily data
                fqt=1,    # \u524d\u590d\u6743
                timeout=60,
            )

            api_elapsed = time.time() - api_start

            # \u8bb0\u5f55\u8fd4\u56de\u6570\u636esummary
            if df is not None and not df.empty:
                logger.info(
                    "[API response] Eastmoney historyK\u7ebfsuccess: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
                    f"range={beg_date}~{end_date_fmt}, rows={len(df)}, elapsed={api_elapsed:.2f}s"
                )
                logger.info(f"[API response] \u5217\u540d: {list(df.columns)}")
                if 'date' in df.columns:
                    logger.info(f"[API response] date\u8303\u56f4: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
                logger.debug(f"[API response] \u6700\u65b03\u6761\u6570\u636e:\n{df.tail(3).to_string()}")
            else:
                logger.warning(
                    "[API response] Eastmoney historyK\u7ebf\u4e3a\u7a7a: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
                    f"range={beg_date}~{end_date_fmt}, elapsed={api_elapsed:.2f}s"
                )

            return df

        except Exception as e:
            api_elapsed = time.time() - api_start
            category, failure_message = self._build_history_failure_message(
                stock_code=stock_code,
                beg_date=beg_date,
                end_date=end_date_fmt,
                exc=e,
                elapsed=api_elapsed,
            )

            if category == "rate_limit_or_anti_bot":
                logger.warning(failure_message)
                raise RateLimitError(f"efinance may be rate limited: {failure_message}") from e

            logger.error(failure_message)
            raise DataFetchError(f"efinance data fetch failed: {failure_message}") from e

    def _fetch_etf_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u83b7\u53d6 ETF \u57fa\u91d1history\u6570\u636e

        Exchange-traded ETFs have OHLCV data just like regular stocks, so we use
        ef.stock.get_quote_history (the stock K-line API) which returns full
        open/high/low/close/volume data.

        Previously this method used ef.fund.get_quote_history which only returns
        NAV data (\u5355characters\u51c0\u503c/\u7d2f\u8ba1\u51c0\u503c) without volume or OHLC, causing:
        - Issue #541: 'got an unexpected keyword argument beg'
        - Issue #527: ETF volume/turnover always showing 0

        Args:
            stock_code: ETF code, e.g. '512400', '159883', '515120'
            start_date: Start date, format 'YYYY-MM-DD'
            end_date: End date, format 'YYYY-MM-DD'

        Returns:
            ETF historical OHLCV DataFrame
        """
        import efinance as ef

        # Anti-ban strategy 1: random User-Agent
        self._set_random_user_agent()

        # Anti-ban strategy 2: enforce rate limit
        self._enforce_rate_limit()

        # Format dates (efinance uses YYYYMMDD)
        beg_date = start_date.replace('-', '')
        end_date_fmt = end_date.replace('-', '')
        secid = _build_eastmoney_etf_secid(stock_code)

        logger.info(
            f"[API call] ef.stock.get_quote_history(stock_codes={secid}, "
            f"beg={beg_date}, end={end_date_fmt}, klt=101, fqt=1, "
            f"quote_id_mode=True, use_id_cache=False)  [ETF stock_code={stock_code}]"
        )

        api_start = time.time()
        try:
            # ETFs are exchange-traded securities; use the stock API to get full OHLCV data
            df = _ef_call_with_timeout(
                ef.stock.get_quote_history,
                stock_codes=secid,
                beg=beg_date,
                end=end_date_fmt,
                klt=101,  # daily
                fqt=1,    # forward-adjusted
                quote_id_mode=True,
                use_id_cache=False,
                timeout=60,
            )

            api_elapsed = time.time() - api_start

            if df is not None and not df.empty:
                logger.info(
                    "[API response] Eastmoney historyK\u7ebfsuccess [ETF]: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, secid={secid}, "
                    f"range={beg_date}~{end_date_fmt}, rows={len(df)}, elapsed={api_elapsed:.2f}s"
                )
                logger.info(f"[API response] \u5217\u540d: {list(df.columns)}")
                if 'date' in df.columns:
                    logger.info(f"[API response] date\u8303\u56f4: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
                logger.debug(f"[API response] \u6700\u65b03\u6761\u6570\u636e:\n{df.tail(3).to_string()}")
            else:
                logger.warning(
                    "[API response] Eastmoney historyK\u7ebf\u4e3a\u7a7a [ETF]: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, secid={secid}, "
                    f"range={beg_date}~{end_date_fmt}, elapsed={api_elapsed:.2f}s"
                )

            return df

        except Exception as e:
            api_elapsed = time.time() - api_start
            category, failure_message = self._build_history_failure_message(
                stock_code=stock_code,
                beg_date=beg_date,
                end_date=end_date_fmt,
                exc=e,
                elapsed=api_elapsed,
                is_etf=True,
            )

            if category == "rate_limit_or_anti_bot":
                logger.warning(failure_message)
                raise RateLimitError(f"efinance may be rate limited: {failure_message}") from e

            logger.error(failure_message)
            raise DataFetchError(f"efinance ETF data fetch failed: {failure_message}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        \u6807\u51c6\u5316 efinance \u6570\u636e

        efinance \u8fd4\u56de\u7684\u5217\u540d (Medium\u6587):
        stock name, stock code, date, \u5f00\u76d8, \u6536\u76d8, \u6700High, \u6700Low, volume, amount, \u632f\u5e45, change\u5e45, change\u989d, turnover

        \u9700\u8981\u6620\u5c04\u5230\u6807\u51c6\u5217\u540d:
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # Column mapping (efinance Chinese column names -> standard English column names)
        column_mapping = {
            'date': 'date',
            '\u5f00\u76d8': 'open',
            '\u6536\u76d8': 'close',
            '\u6700High': 'high',
            '\u6700Low': 'low',
            'volume': 'volume',
            'amount': 'amount',
            'change\u5e45': 'pct_chg',
            'stock code': 'code',
            'stock name': 'name',
        }

        # \u91cd\u547d\u540d\u5217
        df = df.rename(columns=column_mapping)

        # Fallback: if OHLC columns are missing (e.g. very old data path), fill from close
        if 'close' in df.columns and 'open' not in df.columns:
            df['open'] = df['close']
            df['high'] = df['close']
            df['low'] = df['close']

        # Fill volume and amount if missing
        if 'volume' not in df.columns:
            df['volume'] = 0
        if 'amount' not in df.columns:
            df['amount'] = 0


        # \u5982\u679c\u6ca1\u6709 code \u5217; \u624b\u52a8\u6dfb\u52a0
        if 'code' not in df.columns:
            df['code'] = stock_code

        # \u53ea\u4fdd\u7559\u9700\u8981\u7684\u5217
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6realtime quote\u6570\u636e

        \u6570\u636esource: ef.stock.get_realtime_quotes()
        ETF data source: ef.stock.get_realtime_quotes(['ETF'])

        Args:
            stock_code: stock code

        Returns:
            UnifiedRealtimeQuote \u5bf9\u8c61; fetch failed\u8fd4\u56de None
        """
        # ETF \u9700\u8981\u5355\u72ecrequest ETF realtime quote\u63a5\u53e3
        if _is_etf_code(stock_code):
            return self._get_etf_realtime_quote(stock_code)

        import efinance as ef
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "efinance"

        # \u68c0check\u7194\u65ad\u5668status
        if not circuit_breaker.is_available(source_key):
            logger.info(f"[Circuit breaker] data source {source_key} \u5904\u4e8e\u7194\u65adstatus; skipping")
            return None

        try:
            # \u68c0checkcache
            current_time = time.time()
            if (_realtime_cache['data'] is not None and
                current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']):
                df = _realtime_cache['data']
                cache_age = int(current_time - _realtime_cache['timestamp'])
                logger.debug(f"[Cache hit] realtime quote(efinance) - cache\u5e74\u9f84 {cache_age}s/{_realtime_cache['ttl']}s")
            else:
                # \u89e6\u53d1\u5168\u91cf\u5237\u65b0
                logger.info(f"[Cache miss] \u89e6\u53d1\u5168\u91cf\u5237\u65b0 realtime quote(efinance)")
                # \u9632\u5c01\u7981strategy
                self._set_random_user_agent()
                self._enforce_rate_limit()

                logger.info(f"[API call] ef.stock.get_realtime_quotes() \u83b7\u53d6realtime quote...")
                import time as _time
                api_start = _time.time()

                # efinance \u7684realtime quote API (with timeout to avoid indefinite hangs)
                df = _ef_call_with_timeout(ef.stock.get_realtime_quotes)

                api_elapsed = _time.time() - api_start
                logger.info(f"[API response] ef.stock.get_realtime_quotes success: \u8fd4\u56de {len(df)} stocks, elapsed {api_elapsed:.2f}s")
                circuit_breaker.record_success(source_key)

                # \u66f4\u65b0cache
                _realtime_cache['data'] = df
                _realtime_cache['timestamp'] = current_time
                logger.info(f"[Cache update] realtime quote(efinance) cache\u5df2\u5237\u65b0; TTL={_realtime_cache['ttl']}s")

            # check\u627e\u6307\u5b9a\u80a1\u7968
            # efinance \u8fd4\u56de\u7684\u5217\u540d\u53ef\u80fd\u662f 'stock code' or 'code'
            code_col = 'stock code' if 'stock code' in df.columns else 'code'
            row = df[df[code_col] == stock_code]
            if row.empty:
                logger.info(f"[API response] \u672a\u627e\u5230\u80a1\u7968 {stock_code} \u7684realtime quote")
                return None

            row = row.iloc[0]

            # \u4f7f\u7528 realtime_types.py Medium\u7684\u7edf\u4e00\u8f6c\u6362\u51fd\u6570
            # \u83b7\u53d6\u5217\u540d (\u53ef\u80fd\u662fMedium\u6587or\u82f1\u6587)
            name_col = 'stock name' if 'stock name' in df.columns else 'name'
            price_col = '\u6700\u65b0\u4ef7' if '\u6700\u65b0\u4ef7' in df.columns else 'price'
            pct_col = 'change\u5e45' if 'change\u5e45' in df.columns else 'pct_chg'
            chg_col = 'change\u989d' if 'change\u989d' in df.columns else 'change'
            vol_col = 'volume' if 'volume' in df.columns else 'volume'
            amt_col = 'amount' if 'amount' in df.columns else 'amount'
            turn_col = 'turnover' if 'turnover' in df.columns else 'turnover_rate'
            amp_col = '\u632f\u5e45' if '\u632f\u5e45' in df.columns else 'amplitude'
            high_col = '\u6700High' if '\u6700High' in df.columns else 'high'
            low_col = '\u6700Low' if '\u6700Low' in df.columns else 'low'
            open_col = '\u5f00\u76d8' if '\u5f00\u76d8' in df.columns else 'open'
            # efinance \u4e5f\u8fd4\u56de\u91cf\u6bd4、PE ratio、\u5e02\u503c\u7b49\u5b57\u6bb5
            vol_ratio_col = '\u91cf\u6bd4' if '\u91cf\u6bd4' in df.columns else 'volume_ratio'
            pe_col = 'PE ratio' if 'PE ratio' in df.columns else 'pe_ratio'
            total_mv_col = 'total market cap' if 'total market cap' in df.columns else 'total_mv'
            circ_mv_col = 'float market cap' if 'float market cap' in df.columns else 'circ_mv'

            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get(name_col, '')),
                source=RealtimeSource.EFINANCE,
                price=safe_float(row.get(price_col)),
                change_pct=safe_float(row.get(pct_col)),
                change_amount=safe_float(row.get(chg_col)),
                volume=safe_int(row.get(vol_col)),
                amount=safe_float(row.get(amt_col)),
                turnover_rate=safe_float(row.get(turn_col)),
                amplitude=safe_float(row.get(amp_col)),
                high=safe_float(row.get(high_col)),
                low=safe_float(row.get(low_col)),
                open_price=safe_float(row.get(open_col)),
                volume_ratio=safe_float(row.get(vol_ratio_col)),  # \u91cf\u6bd4
                pe_ratio=safe_float(row.get(pe_col)),  # PE ratio
                total_mv=safe_float(row.get(total_mv_col)),  # total market cap
                circ_mv=safe_float(row.get(circ_mv_col)),  # float market cap
            )

            logger.info(f"[realtime quote-efinance] {stock_code} {quote.name}: price={quote.price}, change={quote.change_pct}%, "
                       f"\u91cf\u6bd4={quote.volume_ratio}, turnover={quote.turnover_rate}%")
            return quote

        except FuturesTimeoutError:
            logger.info(f"[\u8d85\u65f6] ef.stock.get_realtime_quotes() \u8d85\u8fc7 {_EF_CALL_TIMEOUT}s; skipping {stock_code}")
            circuit_breaker.record_failure(source_key, "timeout")
            return None
        except Exception as e:
            logger.info(f"[API error] \u83b7\u53d6 {stock_code} realtime quote(efinance)failed: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None

    def _get_etf_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6 ETF realtime quote

        efinance default\u5b9e\u65f6\u63a5\u53e3\u4ec5\u8fd4\u56de\u80a1\u7968\u6570\u636e; ETF \u9700\u8981\u663e\u5f0f\u4f20\u5165 ['ETF'].
        """
        import efinance as ef
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "efinance_etf"

        if not circuit_breaker.is_available(source_key):
            logger.info(f"[Circuit breaker] data source {source_key} \u5904\u4e8e\u7194\u65adstatus; skipping")
            return None

        try:
            current_time = time.time()
            if (
                _etf_realtime_cache['data'] is not None and
                current_time - _etf_realtime_cache['timestamp'] < _etf_realtime_cache['ttl']
            ):
                df = _etf_realtime_cache['data']
                cache_age = int(current_time - _etf_realtime_cache['timestamp'])
                logger.debug(f"[Cache hit] ETFrealtime quote(efinance) - cache\u5e74\u9f84 {cache_age}s/{_etf_realtime_cache['ttl']}s")
            else:
                self._set_random_user_agent()
                self._enforce_rate_limit()

                logger.info("[API call] ef.stock.get_realtime_quotes(['ETF']) \u83b7\u53d6ETFrealtime quote...")
                import time as _time
                api_start = _time.time()
                df = _ef_call_with_timeout(ef.stock.get_realtime_quotes, ['ETF'])
                api_elapsed = _time.time() - api_start

                if df is not None and not df.empty:
                    logger.info(f"[API response] ETF realtime quotesuccess: {len(df)} \u6761, elapsed {api_elapsed:.2f}s")
                    circuit_breaker.record_success(source_key)
                else:
                    logger.info(f"[API response] ETF realtime quote\u4e3a\u7a7a, elapsed {api_elapsed:.2f}s")
                    df = pd.DataFrame()

                _etf_realtime_cache['data'] = df
                _etf_realtime_cache['timestamp'] = current_time

            if df is None or df.empty:
                logger.info(f"[Realtime quote] ETFrealtime quote\u6570\u636e\u4e3a\u7a7a(efinance); skipping {stock_code}")
                return None

            code_col = 'stock code' if 'stock code' in df.columns else 'code'
            code_series = df[code_col].astype(str).str.zfill(6)
            target_code = str(stock_code).strip().zfill(6)
            row = df[code_series == target_code]
            if row.empty:
                logger.info(f"[API response] \u672a\u627e\u5230 ETF {stock_code} \u7684realtime quote(efinance)")
                return None

            row = row.iloc[0]
            name_col = 'stock name' if 'stock name' in df.columns else 'name'
            price_col = '\u6700\u65b0\u4ef7' if '\u6700\u65b0\u4ef7' in df.columns else 'price'
            pct_col = 'change\u5e45' if 'change\u5e45' in df.columns else 'pct_chg'
            chg_col = 'change\u989d' if 'change\u989d' in df.columns else 'change'
            vol_col = 'volume' if 'volume' in df.columns else 'volume'
            amt_col = 'amount' if 'amount' in df.columns else 'amount'
            turn_col = 'turnover' if 'turnover' in df.columns else 'turnover_rate'
            amp_col = '\u632f\u5e45' if '\u632f\u5e45' in df.columns else 'amplitude'
            high_col = '\u6700High' if '\u6700High' in df.columns else 'high'
            low_col = '\u6700Low' if '\u6700Low' in df.columns else 'low'
            open_col = '\u5f00\u76d8' if '\u5f00\u76d8' in df.columns else 'open'

            quote = UnifiedRealtimeQuote(
                code=target_code,
                name=str(row.get(name_col, '')),
                source=RealtimeSource.EFINANCE,
                price=safe_float(row.get(price_col)),
                change_pct=safe_float(row.get(pct_col)),
                change_amount=safe_float(row.get(chg_col)),
                volume=safe_int(row.get(vol_col)),
                amount=safe_float(row.get(amt_col)),
                turnover_rate=safe_float(row.get(turn_col)),
                amplitude=safe_float(row.get(amp_col)),
                high=safe_float(row.get(high_col)),
                low=safe_float(row.get(low_col)),
                open_price=safe_float(row.get(open_col)),
            )

            logger.info(
                f"[ETFrealtime quote-efinance] {target_code} {quote.name}: "
                f"price={quote.price}, change={quote.change_pct}%, turnover={quote.turnover_rate}%"
            )
            return quote
        except Exception as e:
            logger.info(f"[API error] \u83b7\u53d6 ETF {stock_code} realtime quote(efinance)failed: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        \u83b7\u53d6\u4e3b\u8981indexrealtime quote (efinance); \u4ec5\u652f\u6301 A \u80a1
        """
        if region != "cn":
            return None
        import efinance as ef

        indices_map = {
            '000001': ('\u4e0a\u8bc1index', 'sh000001'),
            '399001': ('\u6df1\u8bc1\u6210\u6307', 'sz399001'),
            '399006': ('\u521b\u4e1a\u677f\u6307', 'sz399006'),
            '000688': ('\u79d1\u521b50', 'sh000688'),
            '000016': ('\u4e0a\u8bc150', 'sh000016'),
            '000300': ('\u6caa\u6df1300', 'sh000300'),
        }

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[API call] ef.stock.get_realtime_quotes(['\u6caa\u6df1\u7cfb\u5217index']) \u83b7\u53d6index\u884c\u60c5...")
            import time as _time
            api_start = _time.time()
            df = _ef_call_with_timeout(ef.stock.get_realtime_quotes, ['\u6caa\u6df1\u7cfb\u5217index'])
            api_elapsed = _time.time() - api_start

            if df is None or df.empty:
                logger.warning(f"[API response] index\u884c\u60c5\u4e3a\u7a7a, elapsed {api_elapsed:.2f}s")
                return None

            logger.info(f"[API response] index\u884c\u60c5success: {len(df)} \u6761, elapsed {api_elapsed:.2f}s")
            code_col = 'stock code' if 'stock code' in df.columns else 'code'
            code_series = df[code_col].astype(str).str.zfill(6)

            results: List[Dict[str, Any]] = []
            for code, (name, full_code) in indices_map.items():
                row = df[code_series == code]
                if row.empty:
                    continue
                item = row.iloc[0]

                price_col = '\u6700\u65b0\u4ef7' if '\u6700\u65b0\u4ef7' in df.columns else 'price'
                pct_col = 'change\u5e45' if 'change\u5e45' in df.columns else 'pct_chg'
                chg_col = 'change\u989d' if 'change\u989d' in df.columns else 'change'
                open_cols = [column for column in ('\u4eca\u5f00', '\u5f00\u76d8', 'open') if column in df.columns]
                high_col = '\u6700High' if '\u6700High' in df.columns else 'high'
                low_col = '\u6700Low' if '\u6700Low' in df.columns else 'low'
                vol_col = 'volume' if 'volume' in df.columns else 'volume'
                amt_col = 'amount' if 'amount' in df.columns else 'amount'
                amp_col = '\u632f\u5e45' if '\u632f\u5e45' in df.columns else 'amplitude'

                current = safe_float(item.get(price_col, 0))
                change_amount = safe_float(item.get(chg_col, 0))
                open_price = 0.0
                for column in open_cols:
                    candidate = safe_float(item.get(column), default=None)
                    if candidate not in (None, 0.0):
                        open_price = candidate
                        break
                if open_price == 0.0 and open_cols:
                    open_price = safe_float(item.get(open_cols[0], 0), 0)

                results.append({
                    'code': full_code,
                    'name': name,
                    'current': current,
                    'change': change_amount,
                    'change_pct': safe_float(item.get(pct_col, 0)),
                    'open': open_price,
                    'high': safe_float(item.get(high_col, 0)),
                    'low': safe_float(item.get(low_col, 0)),
                    'prev_close': current - change_amount if current or change_amount else 0,
                    'volume': safe_float(item.get(vol_col, 0)),
                    'amount': safe_float(item.get(amt_col, 0)),
                    'amplitude': safe_float(item.get(amp_col, 0)),
                })

            if results:
                logger.info(f"[efinance] \u83b7\u53d6\u5230 {len(results)} \u4e2aindex\u884c\u60c5")
            return results if results else None
        except Exception as e:
            logger.error(f"[efinance] \u83b7\u53d6index\u884c\u60c5failed: {e}")
            return None

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """
        \u83b7\u53d6marketchange\u7edf\u8ba1 (efinance)
        """
        import efinance as ef

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            current_time = time.time()
            if (
                _realtime_cache['data'] is not None and
                current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']
            ):
                df = _realtime_cache['data']
                logger.info(
                    "[MarketStats] component=market_stats provider=EfinanceFetcher "
                    "api=ef.stock.get_realtime_quotes action=cache_hit cache_age=%.0fs",
                    current_time - _realtime_cache['timestamp'],
                )
            else:
                started_at = time.monotonic()
                logger.info(
                    "[MarketStats] component=market_stats provider=EfinanceFetcher "
                    "api=ef.stock.get_realtime_quotes action=request_start"
                )
                df = _ef_call_with_timeout(ef.stock.get_realtime_quotes)
                elapsed = time.monotonic() - started_at
                logger.info(
                    "[MarketStats] component=market_stats provider=EfinanceFetcher "
                    "api=ef.stock.get_realtime_quotes action=request_complete elapsed=%.2fs",
                    elapsed,
                )
                _realtime_cache['data'] = df
                _realtime_cache['timestamp'] = current_time

            if df is None or df.empty:
                logger.warning(
                    "[MarketStats] component=market_stats provider=EfinanceFetcher "
                    "api=ef.stock.get_realtime_quotes action=parse status=empty"
                )
                return None

            return self._calc_market_stats(df)
        except Exception as e:
            logger.error(
                "[MarketStats] component=market_stats provider=EfinanceFetcher "
                "api=ef.stock.get_realtime_quotes action=failed error=%s",
                e,
            )
            return None

    def _calc_market_stats(
        self,
        df: pd.DataFrame,
        ) -> Optional[Dict[str, Any]]:
        """\u4ece\u884c\u60c5 DataFrame \u8ba1\u7b97change\u7edf\u8ba1."""
        import numpy as np

        df = df.copy()

        # 1. \u63d0\u53d6\u57fa\u7840\u6bd4\u5bf9\u6570\u636e: \u6700\u65b0\u4ef7、\u6628\u6536
        # \u517c\u5bb9\u4e0d\u540c\u63a5\u53e3\u8fd4\u56de\u7684\u5217\u540d sina/em efinance tushare xtdata
        code_col = next((c for c in ['code', 'stock code', 'ts_code','stock_code'] if c in df.columns), None)
        name_col = next((c for c in ['name', 'stock name','name','name'] if c in df.columns), None)
        close_col = next((c for c in ['\u6700\u65b0\u4ef7', '\u6700\u65b0\u4ef7', 'close','lastPrice'] if c in df.columns), None)
        pre_close_col = next((c for c in ['\u6628\u6536', '\u6628\u65e5\u6536\u76d8', 'pre_close','lastClose'] if c in df.columns), None)
        amount_col = next((c for c in ['amount', 'amount', 'amount','amount'] if c in df.columns), None)

        limit_up_count = 0
        limit_down_count = 0
        up_count = 0
        down_count = 0
        flat_count = 0

        for code, name, current_price, pre_close, amount in zip(
            df[code_col], df[name_col], df[close_col], df[pre_close_col], df[amount_col]
        ):

            # \u505c\u724c\u8fc7\u6ee4 efinance \u7684\u505c\u724c\u6570\u636e\u6709\u65f6\u5019\u4f1a\u7f3a\u5931price\u663e\u793a\u4e3a '-'; em \u663e\u793a\u4e3anone
            if pd.isna(current_price) or pd.isna(pre_close) or current_price in ['-'] or pre_close in ['-'] or amount == 0:
                continue

            # em、efinance \u4e3astr \u9700\u8981\u8f6c\u6362\u4e3afloat
            current_price = float(current_price)
            pre_close = float(pre_close)

            # \u83b7\u53d6\u53bb\u9664prefix\u7684\u7eaf\u6570\u5b57code
            pure_code = normalize_stock_code(str(code))

            # A. \u786e\u5b9a\u6bcfstocks\u7684change\u5e45\u6bd4\u4f8b (\u4f7f\u7528\u7eaf\u6570\u5b57code\u5224\u65ad)
            if is_bse_code(pure_code):
                ratio = 0.30
            elif is_kc_cy_stock(pure_code): #pure_code.startswith(('688', '30')):
                ratio = 0.20
            elif is_st_stock(name): #'ST' in str_name:
                ratio = 0.05
            else:
                ratio = 0.10

            # B. \u4e25\u683c\u6309\u7167 A \u80a1\u89c4\u5219\u8ba1\u7b97change\u505c\u4ef7: \u6628\u6536 * (1 ± \u6bd4\u4f8b) -> \u56db\u820d\u4e94\u5165\u4fdd\u75592characters\u5c0f\u6570
            limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
            limit_down_price = np.floor(pre_close * (1 - ratio) * 100 + 0.5) / 100.0

            limit_up_price_Tolerance = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
            limit_down_price_Tolerance = round(abs(pre_close * (1 - ratio) - limit_down_price), 10)

            # C. \u7cbe\u786e\u6bd4\u5bf9
            if current_price > 0 :
                is_limit_up = (current_price > 0) and (abs(current_price - limit_up_price) <= limit_up_price_Tolerance)
                is_limit_down = (current_price > 0) and (abs(current_price - limit_down_price) <= limit_down_price_Tolerance)

                if is_limit_up:
                    limit_up_count += 1
                if is_limit_down:
                    limit_down_count += 1

                if current_price > pre_close:
                    up_count += 1
                elif current_price < pre_close:
                    down_count += 1
                else:
                    flat_count += 1

        # \u7edf\u8ba1count
        stats = {
            'up_count': up_count,
            'down_count': down_count,
            'flat_count': flat_count,
            'limit_up_count': limit_up_count,
            'limit_down_count': limit_down_count,
            'total_amount': 0.0,
        }

        # amount\u7edf\u8ba1
        if amount_col and amount_col in df.columns:
            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
            stats['total_amount'] = (df[amount_col].sum() / 1e8)

        return stats

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """
        \u83b7\u53d6sectorchange\u699c (efinance)
        """
        import efinance as ef

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[API call] ef.stock.get_realtime_quotes(['industrysector']) \u83b7\u53d6sector\u884c\u60c5...")
            df = _ef_call_with_timeout(ef.stock.get_realtime_quotes, ['industrysector'])
            if df is None or df.empty:
                logger.warning("[efinance] sector\u884c\u60c5\u6570\u636e\u4e3a\u7a7a")
                return None

            change_col = 'change\u5e45' if 'change\u5e45' in df.columns else 'pct_chg'
            name_col = 'stock name' if 'stock name' in df.columns else 'name'
            if change_col not in df.columns or name_col not in df.columns:
                return None

            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])
            top = df.nlargest(n, change_col)
            bottom = df.nsmallest(n, change_col)

            top_sectors = [
                {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                for _, row in top.iterrows()
            ]
            bottom_sectors = [
                {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                for _, row in bottom.iterrows()
            ]
            return top_sectors, bottom_sectors
        except Exception as e:
            logger.error(f"[efinance] \u83b7\u53d6sector\u6392\u884cfailed: {e}")
            return None

    def get_base_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        \u83b7\u53d6\u80a1\u7968\u57fa\u672cinfo

        \u6570\u636esource: ef.stock.get_base_info()
        \u5305\u542b: PE ratio、PB ratio、\u6240\u5904industry、total market cap、float market cap、ROE、\u51c0\u5229\u7387\u7b49

        Args:
            stock_code: stock code

        Returns:
            \u5305\u542b\u57fa\u672cinfo\u7684\u5b57\u5178; fetch failed\u8fd4\u56de None
        """
        import efinance as ef

        try:
            # \u9632\u5c01\u7981strategy
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info(f"[API call] ef.stock.get_base_info(stock_codes={stock_code}) \u83b7\u53d6\u57fa\u672cinfo...")
            import time as _time
            api_start = _time.time()

            info = _ef_call_with_timeout(ef.stock.get_base_info, stock_code)

            api_elapsed = _time.time() - api_start
            logger.info(f"[API response] ef.stock.get_base_info success, elapsed {api_elapsed:.2f}s")

            if info is None:
                logger.warning(f"[API response] \u672a\u83b7\u53d6\u5230 {stock_code} \u7684\u57fa\u672cinfo")
                return None

            # \u8f6c\u6362\u4e3a\u5b57\u5178
            if isinstance(info, pd.Series):
                return info.to_dict()
            elif isinstance(info, pd.DataFrame):
                if not info.empty:
                    return info.iloc[0].to_dict()

            return None

        except Exception as e:
            logger.error(f"[API error] \u83b7\u53d6 {stock_code} \u57fa\u672cinfofailed: {e}")
            return None

    def get_belong_board(self, stock_code: str) -> Optional[pd.DataFrame]:
        """
        \u83b7\u53d6\u80a1\u7968\u6240\u5c5esector

        \u6570\u636esource: ef.stock.get_belong_board()

        Args:
            stock_code: stock code

        Returns:
            \u6240\u5c5esector DataFrame; fetch failed\u8fd4\u56de None
        """
        import efinance as ef

        try:
            # \u9632\u5c01\u7981strategy
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info(f"[API call] ef.stock.get_belong_board(stock_code={stock_code}) \u83b7\u53d6\u6240\u5c5esector...")
            import time as _time
            api_start = _time.time()

            df = _ef_call_with_timeout(ef.stock.get_belong_board, stock_code)

            api_elapsed = _time.time() - api_start

            if df is not None and not df.empty:
                logger.info(f"[API response] ef.stock.get_belong_board success: \u8fd4\u56de {len(df)} \u4e2asector, elapsed {api_elapsed:.2f}s")
                return df
            else:
                logger.warning(f"[API response] \u672a\u83b7\u53d6\u5230 {stock_code} \u7684sectorinfo")
                return None

        except FuturesTimeoutError:
            logger.warning(f"[\u8d85\u65f6] ef.stock.get_belong_board({stock_code}) \u8d85\u8fc7 {_EF_CALL_TIMEOUT}s; skipping")
            return None
        except Exception as e:
            logger.error(f"[API error] \u83b7\u53d6 {stock_code} \u6240\u5c5esectorfailed: {e}")
            return None

    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        \u83b7\u53d6\u589e\u5f3a\u6570\u636e (historyK\u7ebf + realtime quote + \u57fa\u672cinfo)

        Args:
            stock_code: stock code
            days: history\u6570\u636e\u5929\u6570

        Returns:
            \u5305\u542b\u6240\u6709\u6570\u636e\u7684\u5b57\u5178
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
            'base_info': None,
            'belong_board': None,
        }

        # \u83b7\u53d6daily data\u6570\u636e
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"\u83b7\u53d6 {stock_code} daily data\u6570\u636efailed: {e}")

        # \u83b7\u53d6realtime quote
        result['realtime_quote'] = self.get_realtime_quote(stock_code)

        # \u83b7\u53d6\u57fa\u672cinfo
        result['base_info'] = self.get_base_info(stock_code)

        # \u83b7\u53d6\u6240\u5c5esector
        result['belong_board'] = self.get_belong_board(stock_code)

        return result


if __name__ == "__main__":
    # \u6d4b\u8bd5code
    logging.basicConfig(level=logging.DEBUG)

    fetcher = EfinanceFetcher()

    # \u6d4b\u8bd5\u666e\u901a\u80a1\u7968
    print("=" * 50)
    print("\u6d4b\u8bd5\u666e\u901a\u80a1\u7968\u6570\u636e\u83b7\u53d6 (efinance)")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('600519')  # \u8305\u53f0
        print(f"[\u80a1\u7968] fetch succeeded; \u5171 {len(df)} \u6761\u6570\u636e")
        print(df.tail())
    except Exception as e:
        print(f"[\u80a1\u7968] fetch failed: {e}")

    # \u6d4b\u8bd5 ETF \u57fa\u91d1
    print("\n" + "=" * 50)
    print("\u6d4b\u8bd5 ETF \u57fa\u91d1\u6570\u636e\u83b7\u53d6 (efinance)")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('512400')  # \u6709\u8272\u9f99\u5934ETF
        print(f"[ETF] fetch succeeded; \u5171 {len(df)} \u6761\u6570\u636e")
        print(df.tail())
    except Exception as e:
        print(f"[ETF] fetch failed: {e}")

    # \u6d4b\u8bd5realtime quote
    print("\n" + "=" * 50)
    print("\u6d4b\u8bd5realtime quote\u83b7\u53d6 (efinance)")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('600519')
        if quote:
            print(f"[Realtime quote] {quote.name}: price={quote.price}, change\u5e45={quote.change_pct}%")
        else:
            print("[Realtime quote] \u672a\u83b7\u53d6\u5230\u6570\u636e")
    except Exception as e:
        print(f"[Realtime quote] fetch failed: {e}")

    # \u6d4b\u8bd5\u57fa\u672cinfo
    print("\n" + "=" * 50)
    print("\u6d4b\u8bd5\u57fa\u672cinfo\u83b7\u53d6 (efinance)")
    print("=" * 50)
    try:
        info = fetcher.get_base_info('600519')
        if info:
            dynamic_pe = info.get('PE ratio(dynamic)', info.get('PE ratio(\u52a8)', 'N/A'))
            print(f"[Basic info] PE ratio={dynamic_pe}, PB ratio={info.get('PB ratio', 'N/A')}")
        else:
            print("[\u57fa\u672cinfo] \u672a\u83b7\u53d6\u5230\u6570\u636e")
    except Exception as e:
        print(f"[\u57fa\u672cinfo] fetch failed: {e}")

    # \u6d4b\u8bd5market\u7edf\u8ba1
    print("\n" + "=" * 50)
    print("Testing get_market_stats (efinance)")
    print("=" * 50)
    try:
        stats = fetcher.get_market_stats()
        if stats:
            print(f"Market Stats successfully computed:")
            print(f"Up: {stats['up_count']} (Limit Up: {stats['limit_up_count']})")
            print(f"Down: {stats['down_count']} (Limit Down: {stats['limit_down_count']})")
            print(f"Flat: {stats['flat_count']}")
            print(f"Total Amount: {stats['total_amount']:.2f} \u4ebf (Yi)")
        else:
            print("Failed to compute market stats.")
    except Exception as e:
        print(f"Failed to compute market stats: {e}")
