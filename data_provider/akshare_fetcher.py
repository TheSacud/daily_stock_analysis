# -*- coding: utf-8 -*-
"""
===================================
AkshareFetcher - primary data source (Priority 1)
===================================

Data sources:
1. Eastmoney scraper through akshare - default source
2. Sina Finance API - fallback source
3. Tencent Finance API - fallback source

Features: free, no token required, broad coverage
Risk: scraper-based access can be blocked by anti-scraping controls

Anti-blocking strategy:
1. Randomly sleep 2-5 seconds before each request
2. Rotate User-Agent randomly
3. Use tenacity for exponential-backoff retries
4. Circuit breaker: cool down after consecutive failures

Enhanced data:
- Realtime quotes: volume ratio, turnover, PE, PB, total market cap, float market cap
- Chip distribution: profit ratio, average cost, concentration
"""

import logging
import multiprocessing
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.patches.eastmoney_patch import eastmoney_patch
from src.config import get_config
from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS, is_bse_code, is_st_stock, is_kc_cy_stock, normalize_stock_code
from .realtime_types import (
    UnifiedRealtimeQuote, ChipDistribution, RealtimeSource,
    get_realtime_circuit_breaker, get_chip_circuit_breaker,
    safe_float, safe_int  # Use shared type-conversion helpers
)
from .us_index_mapping import is_us_index_code, is_us_stock_code


# Keep the legacy RealtimeQuote alias for backward compatibility
RealtimeQuote = UnifiedRealtimeQuote


logger = logging.getLogger(__name__)

SINA_REALTIME_ENDPOINT = "hq.sinajs.cn/list"
TENCENT_REALTIME_ENDPOINT = "qt.gtimg.cn/q"
_AKSHARE_HISTORY_CALL_TIMEOUT = 30.0
_AKSHARE_TIMEOUT_PROCESS_JOIN_GRACE = 1.0
_AKSHARE_TIMEOUT_PROCESS_START_METHOD = "spawn"


# User-Agent pool for random rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


# Cache realtime quote data to avoid repeated requests
# TTL \u8bbe\u4e3a 20 \u5206\u949f (1200\u79d2):
# - batchanalyze\u573a\u666f: \u901a\u5e38 30 stocks\u5728 5 \u5206\u949f\u5185analyze\u5b8c; 20 \u5206\u949f\u8db3\u591f\u8986\u76d6
# - \u5b9e\u65f6\u8981\u6c42: \u80a1\u7968analyze\u4e0d\u9700\u8981\u79d2\u7ea7\u5b9e\u65f6\u6570\u636e; 20 \u5206\u949f\u5ef6\u8fdf\u53ef\u63a5\u53d7
# - \u9632\u5c01\u7981: \u51cf\u5c11 API \u8c03\u7528\u9891\u7387
_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 1200  # 20-minute cache TTL
}

# ETF realtime quote cache
_etf_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 1200  # 20-minute cache TTL
}


def _is_etf_code(stock_code: str) -> bool:
    """
    Check whether the code is an ETF fund

    ETF code rules:
    - \u4e0a\u4ea4\u6240 ETF: 51xxxx, 52xxxx, 56xxxx, 58xxxx
    - \u6df1\u4ea4\u6240 ETF: 15xxxx, 16xxxx, 18xxxx

    Args:
        stock_code: stock/fund code

    Returns:
        True means ETF code; False means ordinary stock code
    """
    etf_prefixes = ('51', '52', '56', '58', '15', '16', '18')
    code = stock_code.strip().split('.')[0]
    return code.startswith(etf_prefixes) and len(code) == 6


def _is_hk_code(stock_code: str) -> bool:
    """
    Check whether the code is a Hong Kong stock

    Hong Kong stock code rules:
    - five-digit numeric code, such as '00700' (Tencent Holdings)
    - some Hong Kong stock codes may use a prefix, such as 'hk00700', 'hk1810'

    Args:
        stock_code: stock code

    Returns:
        True means Hong Kong stock code; False means not a Hong Kong stock code
    """
    # Strip an optional hk prefix and check for numeric content
    code = stock_code.strip().lower()
    if code.endswith('.hk'):
        numeric_part = code[:-3]
        return numeric_part.isdigit() and 1 <= len(numeric_part) <= 5
    if code.startswith('hk'):
        # Codes with hk prefix are Hong Kong stocks; after stripping the prefix, the code should be 1-5 digits
        numeric_part = code[2:]
        return numeric_part.isdigit() and 1 <= len(numeric_part) <= 5
    # Without prefix, only five-digit numeric codes are treated as Hong Kong stocks to avoid A-share false positives
    return code.isdigit() and len(code) == 5


def _normalize_tencent_volume(fields: List[str]) -> Optional[int]:
    """
    Normalize Tencent realtime quote volume to shares.

    \u817e\u8baf\u8fd4\u56de\u5185\u5bb9\u5bf9\u5b57\u6bb5 6 \u7684\u516c\u5f00\u8bf4\u660e\u548c\u5b9e\u9645\u8fd4\u56de\u4e0d\u5b8c\u5168\u4e00\u81f4.\u4f18\u5148\u4f7f\u7528
    \u6362\u624b\u7387、\u4ef7\u683c、\u6d41\u901a\u5e02\u503c\u4ea4\u53c9\u6821\u9a8c; \u5728\u539f\u503c\u548c\u65e7\u7684“\u624b\u8f6c\u80a1”\u7ed3\u679cMedium\u9009\u62e9
    \u66f4\u63a5\u8fd1\u7684\u4e00\u65b9.\u82e5\u65e0\u6cd5\u4ea4\u53c9\u6821\u9a8c; \u5219\u4fdd\u7559\u65e7\u7684“\u624b\u8f6c\u80a1”\u515c\u5e95\u903b\u8f91; \u907f\u514d
    \u4f20\u7edf\u817e\u8baf\u8fd4\u56de\u5185\u5bb9\u56de\u5f52\u4e3a\u539f\u6210\u4ea4\u91cf\u7684 1/100.
    """
    if len(fields) <= 6 or not fields[6]:
        return None

    raw_volume = safe_int(fields[6])
    if raw_volume is None:
        return None

    price = safe_float(fields[3]) if len(fields) > 3 else None
    turnover_rate = safe_float(fields[38]) if len(fields) > 38 else None
    circ_mv_yi = safe_float(fields[44]) if len(fields) > 44 and fields[44] else None
    circ_mv = circ_mv_yi * 100000000 if circ_mv_yi is not None else None

    if price and price > 0 and turnover_rate and turnover_rate > 0 and circ_mv and circ_mv > 0:
        expected_volume = (circ_mv / price) * (turnover_rate / 100)
        if expected_volume > 0:
            raw_delta = abs(raw_volume - expected_volume)
            hand_to_share_volume = raw_volume * 100
            hand_delta = abs(hand_to_share_volume - expected_volume)
            return raw_volume if raw_delta <= hand_delta else hand_to_share_volume

    return raw_volume * 100


def _parse_tencent_amount(fields: List[str]) -> Optional[float]:
    """
    Parse Tencent realtime quote turnover amount in CNY.

    \u89c2\u6d4b\u5230\u7684\u8fd4\u56de\u5185\u5bb9Medium; \u5b57\u6bb5 35 \u5305\u542b\u66f4\u7cbe\u786e\u7684“\u4ef7\u683c/\u6210\u4ea4\u91cf/\u6210\u4ea4\u989d”
    \u4e09\u5143\u7ec4.\u5b57\u6bb5 37 \u662f\u65e7\u7684“\u4e07\u5143”\u53e3\u5f84\u515c\u5e95\u5b57\u6bb5.
    """
    if len(fields) > 35 and fields[35]:
        parts = fields[35].split("/")
        if len(parts) >= 3:
            precise_amount = safe_float(parts[2])
            if precise_amount is not None:
                return precise_amount

    amount_wan = safe_float(fields[37]) if len(fields) > 37 and fields[37] else None
    return amount_wan * 10000 if amount_wan is not None else None


def is_hk_stock_code(stock_code: str) -> bool:
    """
    Public API: determine if a stock code is a Hong Kong stock.

    Delegates to _is_hk_code for internal compatibility.

    Args:
        stock_code: Stock code (e.g. '00700', 'hk00700')

    Returns:
        True if HK stock, False otherwise
    """
    return _is_hk_code(stock_code)


def _is_us_code(stock_code: str) -> bool:
    """
    Check whether the code is a US stock, excluding US indices.

    Delegate to is_us_stock_code() in us_index_mapping.

    Args:
        stock_code: stock code

    Returns:
        True means US stock code; False means not a US stock code

    Examples:
        >>> _is_us_code('AAPL')
        True
        >>> _is_us_code('TSLA')
        True
        >>> _is_us_code('SPX')
        False
        >>> _is_us_code('600519')
        False
    """
    return is_us_stock_code(stock_code)


def _to_sina_tx_symbol(stock_code: str) -> str:
    """Convert 6-digit A-share code to sh/sz/bj prefixed symbol for Sina/Tencent APIs."""
    base = (stock_code.strip().split(".")[0] if "." in stock_code else stock_code).strip()
    if is_bse_code(base):
        return f"bj{base}"
    # Shanghai: 60xxxx, 5xxxx (ETF), 90xxxx (B-shares)
    if base.startswith(("6", "5", "90")):
        return f"sh{base}"
    return f"sz{base}"


def _classify_realtime_http_error(exc: Exception) -> Tuple[str, str]:
    """
    Classify Sina/Tencent realtime quote failures into stable categories.
    """
    detail = str(exc).strip() or type(exc).__name__
    lowered = detail.lower()

    remote_disconnect_keywords = (
        "remotedisconnected",
        "remote end closed connection without response",
        "connection aborted",
        "connection broken",
        "protocolerror",
        "chunkedencodingerror",
    )
    timeout_keywords = (
        "timeout",
        "timed out",
        "readtimeout",
        "connecttimeout",
    )
    rate_limit_keywords = (
        "banned",
        "blocked",
        "\u9891\u7387",
        "rate limit",
        "too many requests",
        "429",
        "limit",
        "forbidden",
        "403",
    )

    if any(keyword in lowered for keyword in remote_disconnect_keywords):
        return "remote_disconnect", detail
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)) or any(
        keyword in lowered for keyword in timeout_keywords
    ):
        return "timeout", detail
    if any(keyword in lowered for keyword in rate_limit_keywords):
        return "rate_limit_or_anti_bot", detail
    if isinstance(exc, requests.exceptions.RequestException):
        return "request_error", detail
    return "unknown_request_error", detail


def _build_realtime_failure_message(
    source_name: str,
    endpoint: str,
    stock_code: str,
    symbol: str,
    category: str,
    detail: str,
    elapsed: float,
    error_type: str,
) -> str:
    return (
        f"{source_name} realtime quote endpoint failed: endpoint={endpoint}, stock_code={stock_code}, "
        f"symbol={symbol}, category={category}, error_type={error_type}, "
        f"elapsed={elapsed:.2f}s, detail={detail}"
    )


def _akshare_call_with_timeout(
    func,
    *args,
    timeout: Optional[float] = None,
    call_name: str = "akshare",
    **kwargs,
):
    """Run an akshare call with a bounded wait time."""
    wait_seconds = _AKSHARE_HISTORY_CALL_TIMEOUT if timeout is None else float(timeout)

    multiprocessing.freeze_support()
    ctx = multiprocessing.get_context(_AKSHARE_TIMEOUT_PROCESS_START_METHOD)
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_akshare_timeout_worker,
        args=(child_conn, func, args, kwargs),
        name=f"akshare-{call_name}",
        daemon=True,
    )

    process.start()
    child_conn.close()

    try:
        if not parent_conn.poll(wait_seconds):
            _terminate_akshare_process(process)
            raise TimeoutError(f"{call_name} call exceeded {wait_seconds:g}s; gave up waiting")

        try:
            ok, value = parent_conn.recv()
        except EOFError as exc:
            raise RuntimeError(f"{call_name} call process returned no result") from exc
    finally:
        parent_conn.close()
        process.join(_AKSHARE_TIMEOUT_PROCESS_JOIN_GRACE)
        _terminate_akshare_process(process)

    if ok:
        return value
    raise value


def _akshare_timeout_worker(conn, func, args, kwargs) -> None:
    try:
        conn.send((True, func(*args, **kwargs)))
    except BaseException as exc:
        try:
            conn.send((False, exc))
        except BaseException:
            try:
                conn.send((False, RuntimeError(f"{type(exc).__name__}: {exc}")))
            except BaseException:
                pass
    finally:
        conn.close()


def _terminate_akshare_process(process) -> None:
    if process.is_alive():
        process.terminate()
        process.join(_AKSHARE_TIMEOUT_PROCESS_JOIN_GRACE)
    if process.is_alive():
        process.kill()
        process.join(_AKSHARE_TIMEOUT_PROCESS_JOIN_GRACE)


class AkshareFetcher(BaseFetcher):
    """
    Akshare data source implementation

    Priority: 1 (highest)
    Data sources:Eastmoney\u7f51\u722c\u866b

    Key strategies:
    - \u6bcf\u6b21request\u524d\u968f\u673a\u4f11\u7720 2.0-5.0 \u79d2
    - \u968f\u673a User-Agent \u8f6e\u6362
    - Retry with exponential backoff after failures; maximum 3 attempts
    """

    name = "AkshareFetcher"
    priority = int(os.getenv("AKSHARE_PRIORITY", "1"))

    def __init__(self, sleep_min: float = 2.0, sleep_max: float = 5.0):
        """
        Initialize AkshareFetcher

        Args:
            sleep_min: minimum sleep seconds
            sleep_max: maximum sleep seconds
        """
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self._last_request_time: Optional[float] = None
        self._history_call_timeout = _AKSHARE_HISTORY_CALL_TIMEOUT
        # Apply Eastmoney patch only when enabled
        if get_config().enable_eastmoney_patch:
            eastmoney_patch()

    def _set_random_user_agent(self) -> None:
        """
        Set a random User-Agent

        Implemented by changing requests Session headers
        This is one of the key anti-scraping strategies
        """
        try:
            import akshare as ak
            # akshare \u5185\u90e8\u4f7f\u7528 requests; \u6211\u4eec\u901a\u8fc7\u73af\u5883\u53d8\u91cfor\u76f4\u63a5\u8bbe\u7f6e\u6765\u5f71\u54cd
            # \u5b9e\u9645\u4e0a akshare \u53ef\u80fd\u4e0d\u76f4\u63a5\u66b4\u9732 session; \u8fd9\u91cc\u901a\u8fc7 fake_useragent \u4f5c\u4e3a\u8865\u5145
            random_ua = random.choice(USER_AGENTS)
            logger.debug(f"\u8bbe\u7f6e User-Agent: {random_ua[:50]}...")
        except Exception as e:
            logger.debug(f"Failed to set User-Agent: {e}")

    def _enforce_rate_limit(self) -> None:
        """
        Enforce rate limiting

        \u7b56\u7565:
        1. Check elapsed time since the previous request
        2. If the interval is too short, add sleep time
        3. Then apply random jitter sleep
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            min_interval = self.sleep_min
            if elapsed < min_interval:
                additional_sleep = min_interval - elapsed
                logger.debug(f"Additional sleep {additional_sleep:.2f} \u79d2")
                time.sleep(additional_sleep)

        # Apply random jitter sleep
        self.random_sleep(self.sleep_min, self.sleep_max)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),  # At most 3 retry attempts
        wait=wait_exponential(multiplier=1, min=2, max=30),  # Exponential backoff: 2, 4, 8... max 30 seconds
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw data from Akshare

        Automatically choose API by code type:
        - US stocks: unsupported; raise and let YfinanceFetcher handle them (Issue #311)
        - Hong Kong stocks: use ak.stock_hk_hist()
        - ETF funds: use ak.fund_etf_hist_em()
        - Ordinary A-shares: use ak.stock_zh_a_hist()

        Flow:
        1. Determine code type: US/HK/ETF/A-share
        2. Set a random User-Agent
        3. Apply rate limiting with random sleep
        4. Call the corresponding akshare API
        5. Process returned data
        """
        # Choose fetch method by code type
        if _is_us_code(stock_code):
            # \u7f8e\u80a1: akshare \u7684 stock_us_daily \u63a5\u53e3\u590d\u6743\u5b58\u5728\u5df2\u77e5question (\u53c2\u89c1 Issue #311)
            # \u4ea4\u7531 YfinanceFetcher \u5904\u7406; \u786e\u4fdd\u590d\u6743\u4ef7\u683c\u4e00\u81f4
            raise DataFetchError(
                f"AkshareFetcher does not support US stocks {stock_code}; use YfinanceFetcher for correct adjusted prices"
            )
        elif _is_hk_code(stock_code):
            return self._fetch_hk_data(stock_code, start_date, end_date)
        elif _is_etf_code(stock_code):
            return self._fetch_etf_data(stock_code, start_date, end_date)
        else:
            return self._fetch_stock_data(stock_code, start_date, end_date)

    def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ordinary A-share historical data

        \u7b56\u7565:
        1. Try Eastmoney API first (ak.stock_zh_a_hist)
        2. After failure, try Sina Finance API (ak.stock_zh_a_daily)
        3. Finally, try Tencent Finance API (ak.stock_zh_a_hist_tx)
        """
        # Attempt list
        methods = [
            (self._fetch_stock_data_em, "Eastmoney"),
            (self._fetch_stock_data_sina, "Sina Finance"),
            (self._fetch_stock_data_tx, "Tencent Finance"),
        ]

        last_error = None

        for fetch_method, source_name in methods:
            try:
                logger.info(f"[DataSource] trying {source_name} to fetch {stock_code}...")
                df = fetch_method(stock_code, start_date, end_date)

                if df is not None and not df.empty:
                    logger.info(f"[DataSource] {source_name} fetch succeeded")
                    return df
            except Exception as e:
                last_error = e
                logger.warning(f"[DataSource] {source_name} fetch failed: {e}")
                # Continue with the next source

        # All sources failed
        raise DataFetchError(f"All Akshare channels failed: {last_error}")

    def _fetch_stock_data_em(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ordinary A-share historical data (Eastmoney)
        Data sources:ak.stock_zh_a_hist()
        """
        import akshare as ak

        # Anti-blocking strategy 1: random User-Agent
        self._set_random_user_agent()

        # Anti-blocking strategy 2: enforced sleep
        self._enforce_rate_limit()

        logger.info(f"[API call] ak.stock_zh_a_hist(symbol={stock_code}, ...)")

        try:
            import time as _time
            api_start = _time.time()

            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"
            )

            api_elapsed = _time.time() - api_start

            if df is not None and not df.empty:
                logger.info(f"[API response] ak.stock_zh_a_hist \u6210\u529f: {len(df)} \u884c, elapsed {api_elapsed:.2f}s")
                return df
            else:
                logger.warning(f"[API response] ak.stock_zh_a_hist returned empty data")
                return pd.DataFrame()

        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '\u9891\u7387', 'rate', 'limit']):
                raise RateLimitError(f"Akshare(EM) may be rate limited: {e}") from e
            raise e

    def _fetch_stock_data_sina(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ordinary A-share historical data (Sina Finance)
        Data sources:ak.stock_zh_a_daily()
        """
        import akshare as ak

        # Convert code format: sh600000, sz000001, bj920748
        symbol = _to_sina_tx_symbol(stock_code)

        self._enforce_rate_limit()

        try:
            df = _akshare_call_with_timeout(
                ak.stock_zh_a_daily,
                symbol=symbol,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq",
                timeout=self._history_call_timeout,
                call_name="ak.stock_zh_a_daily",
            )

            # Normalize Sina data column names
            # \u65b0\u6d6a\u8fd4\u56de: date, open, high, low, close, volume, amount, outstanding_share, turnover
            if df is not None and not df.empty:
                # Ensure date column exists
                if 'date' in df.columns:
                    df = df.rename(columns={'date': '\u65e5\u671f'})

                # Map other columns to match _normalize_data expectations
                # _normalize_data expects: \u65e5\u671f, \u5f00\u76d8, \u6536\u76d8, \u6700High, \u6700Low, \u6210\u4ea4\u91cf, \u6210\u4ea4\u989d
                rename_map = {
                    'open': '\u5f00\u76d8', 'high': '\u6700High', 'low': '\u6700Low',
                    'close': '\u6536\u76d8', 'volume': '\u6210\u4ea4\u91cf', 'amount': '\u6210\u4ea4\u989d'
                }
                df = df.rename(columns=rename_map)

                # Calculate percent change (Sina API\u53ef\u80fd\u4e0d\u8fd4\u56de)
                if '\u6536\u76d8' in df.columns:
                    df['\u6da8\u8dcc\u5e45'] = df['\u6536\u76d8'].pct_change() * 100
                    df['\u6da8\u8dcc\u5e45'] = df['\u6da8\u8dcc\u5e45'].fillna(0)

                return df
            return pd.DataFrame()

        except Exception as e:
            raise e

    def _fetch_stock_data_tx(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ordinary A-share historical data (Tencent Finance)
        Data sources:ak.stock_zh_a_hist_tx()
        """
        import akshare as ak

        # Convert code format: sh600000, sz000001, bj920748
        symbol = _to_sina_tx_symbol(stock_code)

        self._enforce_rate_limit()

        try:
            df = _akshare_call_with_timeout(
                ak.stock_zh_a_hist_tx,
                symbol=symbol,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq",
                timeout=self._history_call_timeout,
                call_name="ak.stock_zh_a_hist_tx",
            )

            # Normalize Tencent data column names
            # \u817e\u8baf\u8fd4\u56de: date, open, close, high, low, volume, amount
            if df is not None and not df.empty:
                rename_map = {
                    'date': '\u65e5\u671f', 'open': '\u5f00\u76d8', 'high': '\u6700High',
                    'low': '\u6700Low', 'close': '\u6536\u76d8', 'volume': '\u6210\u4ea4\u91cf',
                    'amount': '\u6210\u4ea4\u989d'
                }
                df = df.rename(columns=rename_map)

                # Tencent data usually contains '\u6da8\u8dcc\u5e45'; calculate it if absent
                if 'pct_chg' in df.columns:
                    df = df.rename(columns={'pct_chg': '\u6da8\u8dcc\u5e45'})
                elif '\u6536\u76d8' in df.columns:
                    df['\u6da8\u8dcc\u5e45'] = df['\u6536\u76d8'].pct_change() * 100
                    df['\u6da8\u8dcc\u5e45'] = df['\u6da8\u8dcc\u5e45'].fillna(0)

                return df
            return pd.DataFrame()

        except Exception as e:
            raise e

    def _fetch_etf_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ETF historical data

        Data sources:ak.fund_etf_hist_em()

        Args:
            stock_code: ETF \u4ee3\u7801; \u5982 '512400', '159883'
            start_date: start date, format 'YYYY-MM-DD'
            end_date: end date, format 'YYYY-MM-DD'

        Returns:
            ETF historical-data DataFrame
        """
        import akshare as ak

        # Anti-blocking strategy 1: random User-Agent
        self._set_random_user_agent()

        # Anti-blocking strategy 2: enforced sleep
        self._enforce_rate_limit()

        logger.info(f"[API call] ak.fund_etf_hist_em(symbol={stock_code}, period=daily, "
                   f"start_date={start_date.replace('-', '')}, end_date={end_date.replace('-', '')}, adjust=qfq)")

        try:
            import time as _time
            api_start = _time.time()

            # Call akshare to fetch ETF daily data
            df = ak.fund_etf_hist_em(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # forward-adjusted
            )

            api_elapsed = _time.time() - api_start

            # Log response data summary
            if df is not None and not df.empty:
                logger.info(f"[API response] ak.fund_etf_hist_em succeeded: returned {len(df)} rows, elapsed {api_elapsed:.2f}s")
                logger.info(f"[API response] columns: {list(df.columns)}")
                date_column = '\u65e5\u671f'
                logger.info(f"[API response] date range: {df[date_column].iloc[0]} ~ {df[date_column].iloc[-1]}")
                logger.debug(f"[API response] latest 3 rows:\n{df.tail(3).to_string()}")
            else:
                logger.warning(f"[API response] ak.fund_etf_hist_em returned empty data, elapsed {api_elapsed:.2f}s")

            return df

        except Exception as e:
            error_msg = str(e).lower()

            # \u68c0\u6d4b\u53cd\u722c\u5c01\u7981
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '\u9891\u7387', 'rate', 'limit']):
                logger.warning(f"Possible blocking detected: {e}")
                raise RateLimitError(f"Akshare may be rate limited: {e}") from e

            raise DataFetchError(f"Akshare Failed to fetch ETF data: {e}") from e

    def _fetch_us_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch US stock historical data

        Data sources:ak.stock_us_daily() (Sina Finance\u63a5\u53e3)

        Args:
            stock_code: US stock code; \u5982 'AMD', 'AAPL', 'TSLA'
            start_date: start date, format 'YYYY-MM-DD'
            end_date: end date, format 'YYYY-MM-DD'

        Returns:
            US stock historical-data DataFrame
        """
        import akshare as ak

        # Anti-blocking strategy 1: random User-Agent
        self._set_random_user_agent()

        # Anti-blocking strategy 2: enforced sleep
        self._enforce_rate_limit()

        # US stock code\u76f4\u63a5\u4f7f\u7528\u5927\u5199
        symbol = stock_code.strip().upper()

        logger.info(f"[API call] ak.stock_us_daily(symbol={symbol}, adjust=qfq)")

        try:
            import time as _time
            api_start = _time.time()

            # Call akshare to fetch US daily data
            # stock_us_daily \u8fd4\u56deallhistory\u6570\u636e; later filtered by date
            df = ak.stock_us_daily(
                symbol=symbol,
                adjust="qfq"  # forward-adjusted
            )

            api_elapsed = _time.time() - api_start

            # Log response data summary
            if df is not None and not df.empty:
                logger.info(f"[API response] ak.stock_us_daily succeeded: returned {len(df)} rows, elapsed {api_elapsed:.2f}s")
                logger.info(f"[API response] columns: {list(df.columns)}")

                # Filter by date
                df['date'] = pd.to_datetime(df['date'])
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

                if not df.empty:
                    logger.info(f"[API response] \u8fc7\u6ee4\u540edate range: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
                    logger.debug(f"[API response] latest 3 rows:\n{df.tail(3).to_string()}")
                else:
                    logger.warning(f"[API response] filtered data is empty; date range {start_date} ~ {end_date} \u65e0\u6570\u636e")

                # \u8f6c\u6362columns\u4e3aMedium\u6587\u683c\u5f0f\u4ee5\u5339\u914d _normalize_data
                # stock_us_daily \u8fd4\u56de: date, open, high, low, close, volume
                rename_map = {
                    'date': '\u65e5\u671f',
                    'open': '\u5f00\u76d8',
                    'high': '\u6700High',
                    'low': '\u6700Low',
                    'close': '\u6536\u76d8',
                    'volume': '\u6210\u4ea4\u91cf',
                }
                df = df.rename(columns=rename_map)

                # Calculate percent change (\u7f8e\u80a1\u63a5\u53e3\u4e0d\u76f4\u63a5\u8fd4\u56de)
                if '\u6536\u76d8' in df.columns:
                    df['\u6da8\u8dcc\u5e45'] = df['\u6536\u76d8'].pct_change() * 100
                    df['\u6da8\u8dcc\u5e45'] = df['\u6da8\u8dcc\u5e45'].fillna(0)

                # Estimate traded amount (\u7f8e\u80a1\u63a5\u53e3\u4e0d\u8fd4\u56de)
                if '\u6210\u4ea4\u91cf' in df.columns and '\u6536\u76d8' in df.columns:
                    df['\u6210\u4ea4\u989d'] = df['\u6210\u4ea4\u91cf'] * df['\u6536\u76d8']
                else:
                    df['\u6210\u4ea4\u989d'] = 0

                return df
            else:
                logger.warning(f"[API response] ak.stock_us_daily returned empty data, elapsed {api_elapsed:.2f}s")
                return pd.DataFrame()

        except Exception as e:
            error_msg = str(e).lower()

            # \u68c0\u6d4b\u53cd\u722c\u5c01\u7981
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '\u9891\u7387', 'rate', 'limit']):
                logger.warning(f"Possible blocking detected: {e}")
                raise RateLimitError(f"Akshare may be rate limited: {e}") from e

            raise DataFetchError(f"Akshare Failed to fetch US stock data: {e}") from e

    def _fetch_hk_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch Hong Kong stock historical data

        Data sources:ak.stock_hk_hist()

        Args:
            stock_code: Hong Kong stock code; \u5982 '00700', '01810'
            start_date: start date, format 'YYYY-MM-DD'
            end_date: end date, format 'YYYY-MM-DD'

        Returns:
            Hong Kong stock historical-data DataFrame
        """
        import akshare as ak

        # Anti-blocking strategy 1: random User-Agent
        self._set_random_user_agent()

        # Anti-blocking strategy 2: enforced sleep
        self._enforce_rate_limit()

        # Ensure code format is correct: five digits
        code = stock_code.lower().replace('hk', '').zfill(5)

        logger.info(f"[API call] ak.stock_hk_hist(symbol={code}, period=daily, "
                   f"start_date={start_date.replace('-', '')}, end_date={end_date.replace('-', '')}, adjust=qfq)")

        try:
            import time as _time
            api_start = _time.time()

            # Call akshare to fetch Hong Kong daily data
            df = ak.stock_hk_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # forward-adjusted
            )

            api_elapsed = _time.time() - api_start

            # Log response data summary
            if df is not None and not df.empty:
                logger.info(f"[API response] ak.stock_hk_hist succeeded: returned {len(df)} rows, elapsed {api_elapsed:.2f}s")
                logger.info(f"[API response] columns: {list(df.columns)}")
                date_column = '\u65e5\u671f'
                logger.info(f"[API response] date range: {df[date_column].iloc[0]} ~ {df[date_column].iloc[-1]}")
                logger.debug(f"[API response] latest 3 rows:\n{df.tail(3).to_string()}")
            else:
                logger.warning(f"[API response] ak.stock_hk_hist returned empty data, elapsed {api_elapsed:.2f}s")

            return df

        except Exception as e:
            error_msg = str(e).lower()

            # \u68c0\u6d4b\u53cd\u722c\u5c01\u7981
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '\u9891\u7387', 'rate', 'limit']):
                logger.warning(f"Possible blocking detected: {e}")
                raise RateLimitError(f"Akshare may be rate limited: {e}") from e

            raise DataFetchError(f"Akshare Failed to fetch Hong Kong stock data: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize Akshare data

        Akshare \u8fd4\u56de\u7684columns (Medium\u6587):
        \u65e5\u671f, \u5f00\u76d8, \u6536\u76d8, \u6700High, \u6700Low, \u6210\u4ea4\u91cf, \u6210\u4ea4\u989d, \u632f\u5e45, \u6da8\u8dcc\u5e45, \u6da8\u8dcc\u989d, \u6362\u624b\u7387

        \u9700\u8981\u6620\u5c04\u5230\u6807\u51c6columns:
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # columns\u6620\u5c04 (Akshare Medium\u6587columns -> \u6807\u51c6\u82f1\u6587columns)
        column_mapping = {
            '\u65e5\u671f': 'date',
            '\u5f00\u76d8': 'open',
            '\u6536\u76d8': 'close',
            '\u6700High': 'high',
            '\u6700Low': 'low',
            '\u6210\u4ea4\u91cf': 'volume',
            '\u6210\u4ea4\u989d': 'amount',
            '\u6da8\u8dcc\u5e45': 'pct_chg',
        }

        # Rename columns
        df = df.rename(columns=column_mapping)

        # \u6dfb\u52a0stock code\u5217
        df['code'] = stock_code

        # Keep only required columns
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str, source: str = "em") -> Optional[UnifiedRealtimeQuote]:
        """
        Fetch realtime quote data with multiple source support

        Data source priority; configurable:
        1. em: Eastmoney (akshare ak.stock_zh_a_spot_em)- broadest data, including volume ratio, PE, PB, and market cap
        2. sina: Sina Finance (akshare ak.stock_zh_a_spot)- lightweight, basic quotes
        3. tencent: \u817e\u8baf\u76f4\u8fde\u63a5\u53e3 - single-stock query with low load

        Args:
            stock_code: \u80a1\u7968/ETF\u4ee3\u7801
            source: data source type, optional "em", "sina", "tencent"

        Returns:
            UnifiedRealtimeQuote \u5bf9\u8c61; returns None on failure
        """
        circuit_breaker = get_realtime_circuit_breaker()

        # Choose fetch method by code type
        if _is_us_code(stock_code):
            # US stocks do not use Akshare; YfinanceFetcher handles them
            logger.debug(f"[API skip] {stock_code} is a US stock; Akshare does not support US realtime quotes")
            return None
        elif _is_hk_code(stock_code):
            return self._get_hk_realtime_quote(stock_code)
        elif _is_etf_code(stock_code):
            source_key = "akshare_etf"
            if not circuit_breaker.is_available(source_key):
                logger.info(f"[Circuit breaker] \u6570\u636e\u6e90 {source_key} is open; skipping")
                return None
            return self._get_etf_realtime_quote(stock_code)
        else:
            source_key = f"akshare_{source}"
            if not circuit_breaker.is_available(source_key):
                logger.info(f"[Circuit breaker] \u6570\u636e\u6e90 {source_key} is open; skipping")
                return None
            # Ordinary A-share: choose data source based on source
            if source == "sina":
                return self._get_stock_realtime_quote_sina(stock_code)
            elif source == "tencent":
                return self._get_stock_realtime_quote_tencent(stock_code)
            else:
                return self._get_stock_realtime_quote_em(stock_code)

    def _get_stock_realtime_quote_em(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6\u666e\u901a A \u80a1\u5b9e\u65f6\u884c\u60c5\u6570\u636e (Eastmoney\u6570\u636e\u6e90)

        Data sources:ak.stock_zh_a_spot_em()
        Pros: broadest data, including volume ratio, turnover, PE, PB, total and float market cap
        Cons: full-market pull; large payload can timeout or hit rate limits
        """
        import akshare as ak
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_em"

        try:
            # Check cache
            current_time = time.time()
            if (_realtime_cache['data'] is not None and
                current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']):
                df = _realtime_cache['data']
                cache_age = int(current_time - _realtime_cache['timestamp'])
                logger.debug(f"[Cache hit] A\u80a1\u5b9e\u65f6\u884c\u60c5(\u4e1c\u8d22) - cache age {cache_age}s/{_realtime_cache['ttl']}s")
            else:
                # Trigger full refresh
                logger.info(f"[Cache miss] Trigger full refresh A\u80a1\u5b9e\u65f6\u884c\u60c5(\u4e1c\u8d22)")
                last_error: Optional[Exception] = None
                df = None
                for attempt in range(1, 3):
                    try:
                        # Anti-blocking strategy
                        self._set_random_user_agent()
                        self._enforce_rate_limit()

                        logger.info(f"[API call] ak.stock_zh_a_spot_em() fetch A-share realtime quotes... (attempt {attempt}/2)")
                        import time as _time
                        api_start = _time.time()

                        df = ak.stock_zh_a_spot_em()

                        api_elapsed = _time.time() - api_start
                        logger.info(f"[API response] ak.stock_zh_a_spot_em succeeded: returned {len(df)} stocks, elapsed {api_elapsed:.2f}s")
                        circuit_breaker.record_success(source_key)
                        break
                    except Exception as e:
                        last_error = e
                        logger.info(f"[API error] ak.stock_zh_a_spot_em fetch failed (attempt {attempt}/2): {e}")
                        time.sleep(min(2 ** attempt, 5))

                # \u66f4\u65b0\u7f13\u5b58: \u6210\u529f\u7f13\u5b58\u6570\u636e；\u5931\u8d25\u4e5f\u7f13\u5b58\u7a7a\u6570\u636e; \u907f\u514d\u540c\u4e00\u8f6e\u4efb\u52a1\u5bf9\u540c\u4e00\u63a5\u53e3\u53cd\u590drequest
                if df is None:
                    logger.info(f"[API error] ak.stock_zh_a_spot_em finally failed: {last_error}")
                    circuit_breaker.record_failure(source_key, str(last_error))
                    df = pd.DataFrame()
                _realtime_cache['data'] = df
                _realtime_cache['timestamp'] = current_time
                logger.info(f"[Cache update] A\u80a1\u5b9e\u65f6\u884c\u60c5(\u4e1c\u8d22) cache refreshed; TTL={_realtime_cache['ttl']}s")

            if df is None or df.empty:
                logger.info(f"[\u5b9e\u65f6\u884c\u60c5] A-share realtime quote data is empty; skipping {stock_code}")
                return None

            # Find target stock
            row = df[df['\u4ee3\u7801'] == stock_code]
            if row.empty:
                logger.info(f"[API response] Stock not found {stock_code} realtime quote")
                return None

            row = row.iloc[0]

            # Use shared conversion helpers from realtime_types.py
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get('\u540d\u79f0', '')),
                source=RealtimeSource.AKSHARE_EM,
                price=safe_float(row.get('\u6700\u65b0\u4ef7')),
                change_pct=safe_float(row.get('\u6da8\u8dcc\u5e45')),
                change_amount=safe_float(row.get('\u6da8\u8dcc\u989d')),
                volume=safe_int(row.get('\u6210\u4ea4\u91cf')),
                amount=safe_float(row.get('\u6210\u4ea4\u989d')),
                volume_ratio=safe_float(row.get('\u91cf\u6bd4')),
                turnover_rate=safe_float(row.get('\u6362\u624b\u7387')),
                amplitude=safe_float(row.get('\u632f\u5e45')),
                open_price=safe_float(row.get('\u4eca\u5f00')),
                high=safe_float(row.get('\u6700High')),
                low=safe_float(row.get('\u6700Low')),
                pe_ratio=safe_float(row.get('PE ratio-\u52a8\u6001')),
                pb_ratio=safe_float(row.get('PB ratio')),
                total_mv=safe_float(row.get('\u603b\u5e02\u503c')),
                circ_mv=safe_float(row.get('\u6d41\u901a\u5e02\u503c')),
                change_60d=safe_float(row.get('60\u65e5\u6da8\u8dcc\u5e45')),
                high_52w=safe_float(row.get('52\u5468\u6700High')),
                low_52w=safe_float(row.get('52\u5468\u6700Low')),
            )

            logger.info(f"[Realtime quote - Eastmoney] {stock_code} {quote.name}: price={quote.price}, change={quote.change_pct}%, "
                       f"volume_ratio={quote.volume_ratio}, turnover={quote.turnover_rate}%")
            return quote

        except Exception as e:
            logger.info(f"[API error] \u83b7\u53d6 {stock_code} \u5b9e\u65f6\u884c\u60c5(\u4e1c\u8d22)\u5931\u8d25: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None

    def _get_stock_realtime_quote_sina(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6\u666e\u901a A \u80a1\u5b9e\u65f6\u884c\u60c5\u6570\u636e (Sina Finance\u6570\u636e\u6e90)

        Data sources:Sina Finance\u63a5\u53e3 (\u76f4\u8fde; \u5355\u80a1\u7968query)
        \u4f18\u70b9: single-stock query with low load; \u901f\u5ea6\u5feb
        Cons: fewer fields; no volume ratio, PE, or PB

        Endpoint format: http://hq.sinajs.cn/list=sh600519,sz000001
        """
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_sina"
        symbol = _to_sina_tx_symbol(stock_code)
        url = f"http://{SINA_REALTIME_ENDPOINT}={symbol}"
        api_start = time.time()

        try:
            headers = {
                'Referer': 'http://finance.sina.com.cn',
                'User-Agent': random.choice(USER_AGENTS)
            }

            logger.info(
                f"[API call] Sina Finance\u63a5\u53e3\u83b7\u53d6 {stock_code} \u5b9e\u65f6\u884c\u60c5: endpoint={SINA_REALTIME_ENDPOINT}, symbol={symbol}"
            )

            self._enforce_rate_limit()
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            api_elapsed = time.time() - api_start

            if response.status_code != 200:
                failure_message = _build_realtime_failure_message(
                    source_name="\u65b0\u6d6a",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="http_status",
                    detail=f"HTTP {response.status_code}",
                    elapsed=api_elapsed,
                    error_type="HTTPStatus",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            # Parse data: var hq_str_sh600519="\u8d35\u5ddeMoutai,1866.000,1870.000,..."
            content = response.text.strip()
            if '=""' in content or not content:
                failure_message = _build_realtime_failure_message(
                    source_name="\u65b0\u6d6a",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="empty_response",
                    detail="empty quote payload",
                    elapsed=api_elapsed,
                    error_type="EmptyResponse",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            # Extract data inside quotes
            data_start = content.find('"')
            data_end = content.rfind('"')
            if data_start == -1 or data_end == -1:
                failure_message = _build_realtime_failure_message(
                    source_name="\u65b0\u6d6a",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="malformed_payload",
                    detail="quote payload missing quotes",
                    elapsed=api_elapsed,
                    error_type="MalformedPayload",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            data_str = content[data_start+1:data_end]
            fields = data_str.split(',')

            if len(fields) < 32:
                failure_message = _build_realtime_failure_message(
                    source_name="\u65b0\u6d6a",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="insufficient_fields",
                    detail=f"field_count={len(fields)}",
                    elapsed=api_elapsed,
                    error_type="InsufficientFields",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            circuit_breaker.record_success(source_key)

            # Sina data field order:
            # 0:\u540d\u79f0 1:\u4eca\u5f00 2:\u6628\u6536 3:\u6700\u65b0\u4ef7 4:\u6700High 5:\u6700Low 6:\u4e70\u4e00\u4ef7 7:\u5356\u4e00\u4ef7
            # 8:\u6210\u4ea4\u91cf(\u80a1) 9:\u6210\u4ea4\u989d(\u5143) ... 30:\u65e5\u671f 31:\u65f6\u95f4
            # Use shared conversion helpers from realtime_types.py
            price = safe_float(fields[3])
            pre_close = safe_float(fields[2])
            change_pct = None
            change_amount = None
            if price and pre_close and pre_close > 0:
                change_amount = price - pre_close
                change_pct = (change_amount / pre_close) * 100

            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=fields[0],
                source=RealtimeSource.AKSHARE_SINA,
                price=price,
                change_pct=change_pct,
                change_amount=change_amount,
                volume=safe_int(fields[8]),  # \u6210\u4ea4\u91cf (\u80a1)
                amount=safe_float(fields[9]),  # \u6210\u4ea4\u989d (\u5143)
                open_price=safe_float(fields[1]),
                high=safe_float(fields[4]),
                low=safe_float(fields[5]),
                pre_close=pre_close,
            )

            logger.info(
                f"[Realtime quote - Sina] {stock_code} {quote.name}: endpoint={SINA_REALTIME_ENDPOINT}, "
                f"price={quote.price}, change={quote.change_pct}, \u6210\u4ea4\u91cf={quote.volume}, elapsed={api_elapsed:.2f}s"
            )
            return quote

        except Exception as e:
            api_elapsed = time.time() - api_start
            category, detail = _classify_realtime_http_error(e)
            failure_message = _build_realtime_failure_message(
                source_name="\u65b0\u6d6a",
                endpoint=SINA_REALTIME_ENDPOINT,
                stock_code=stock_code,
                symbol=symbol,
                category=category,
                detail=detail,
                elapsed=api_elapsed,
                error_type=type(e).__name__,
            )
            logger.info(failure_message)
            circuit_breaker.record_failure(source_key, failure_message)
            return None

    def _get_stock_realtime_quote_tencent(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6\u666e\u901a A \u80a1\u5b9e\u65f6\u884c\u60c5\u6570\u636e (Tencent Finance\u6570\u636e\u6e90)

        Data sources:Tencent Finance\u63a5\u53e3 (\u76f4\u8fde; \u5355\u80a1\u7968query)
        \u4f18\u70b9: single-stock query with low load; \u5305\u542b\u6362\u624b\u7387
        Cons: no valuation data such as volume ratio, PE, or PB

        Endpoint format: http://qt.gtimg.cn/q=sh600519,sz000001
        """
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_tencent"
        symbol = _to_sina_tx_symbol(stock_code)
        url = f"http://{TENCENT_REALTIME_ENDPOINT}={symbol}"
        api_start = time.time()

        try:
            headers = {
                'Referer': 'http://finance.qq.com',
                'User-Agent': random.choice(USER_AGENTS)
            }

            logger.info(
                f"[API call] Tencent Finance\u63a5\u53e3\u83b7\u53d6 {stock_code} \u5b9e\u65f6\u884c\u60c5: endpoint={TENCENT_REALTIME_ENDPOINT}, symbol={symbol}"
            )

            self._enforce_rate_limit()
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            api_elapsed = time.time() - api_start

            if response.status_code != 200:
                failure_message = _build_realtime_failure_message(
                    source_name="\u817e\u8baf",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="http_status",
                    detail=f"HTTP {response.status_code}",
                    elapsed=api_elapsed,
                    error_type="HTTPStatus",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            content = response.text.strip()
            if '=""' in content or not content:
                failure_message = _build_realtime_failure_message(
                    source_name="\u817e\u8baf",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="empty_response",
                    detail="empty quote payload",
                    elapsed=api_elapsed,
                    error_type="EmptyResponse",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            # Extract data
            data_start = content.find('"')
            data_end = content.rfind('"')
            if data_start == -1 or data_end == -1:
                failure_message = _build_realtime_failure_message(
                    source_name="\u817e\u8baf",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="malformed_payload",
                    detail="quote payload missing quotes",
                    elapsed=api_elapsed,
                    error_type="MalformedPayload",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            data_str = content[data_start+1:data_end]
            fields = data_str.split('~')

            if len(fields) < 45:
                failure_message = _build_realtime_failure_message(
                    source_name="\u817e\u8baf",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="insufficient_fields",
                    detail=f"field_count={len(fields)}",
                    elapsed=api_elapsed,
                    error_type="InsufficientFields",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None

            circuit_breaker.record_success(source_key)

            # Tencent data field order (full):
            # 1:\u540d\u79f0 2:\u4ee3\u7801 3:\u6700\u65b0\u4ef7 4:\u6628\u6536 5:\u4eca\u5f00 6:\u6210\u4ea4\u91cf 7:\u5916\u76d8 8:\u5185\u76d8
            # 9-28:\u4e70\u5356\u4e94\u6863 30:\u65f6\u95f4\u6233 31:\u6da8\u8dcc\u989d 32:\u6da8\u8dcc\u5e45(%) 33:\u6700High 34:\u6700Low 35:\u6536\u76d8/\u6210\u4ea4\u91cf/\u6210\u4ea4\u989d
            # 36:\u6210\u4ea4\u91cf(\u53e3\u5f84\u968f payload \u53d8\u5316) 37:\u6210\u4ea4\u989d(\u4e07) 38:\u6362\u624b\u7387(%) 39:PE ratio 43:\u632f\u5e45(%)
            # 44:\u6d41\u901a\u5e02\u503c(\u4ebf) 45:\u603b\u5e02\u503c(\u4ebf) 46:PB ratio 47:\u6da8\u505c\u4ef7 48:\u8dcc\u505c\u4ef7 49:\u91cf\u6bd4
            # Use shared conversion helpers from realtime_types.py
            amount = _parse_tencent_amount(fields)
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=fields[1] if len(fields) > 1 else "",
                source=RealtimeSource.TENCENT,
                price=safe_float(fields[3]),
                change_pct=safe_float(fields[32]),
                change_amount=safe_float(fields[31]) if len(fields) > 31 else None,
                volume=_normalize_tencent_volume(fields),
                amount=amount,
                open_price=safe_float(fields[5]),
                high=safe_float(fields[33]) if len(fields) > 33 else None,  # \u4fee\u6b63: field 33 is high price
                low=safe_float(fields[34]) if len(fields) > 34 else None,  # \u4fee\u6b63: field 34 is low price
                pre_close=safe_float(fields[4]),
                turnover_rate=safe_float(fields[38]) if len(fields) > 38 else None,
                amplitude=safe_float(fields[43]) if len(fields) > 43 else None,
                volume_ratio=safe_float(fields[49]) if len(fields) > 49 else None,  # \u91cf\u6bd4
                pe_ratio=safe_float(fields[39]) if len(fields) > 39 else None,  # PE ratio
                pb_ratio=safe_float(fields[46]) if len(fields) > 46 else None,  # PB ratio
                circ_mv=safe_float(fields[44]) * 100000000 if len(fields) > 44 and fields[44] else None,  # float market cap (100m CNY to CNY)
                total_mv=safe_float(fields[45]) * 100000000 if len(fields) > 45 and fields[45] else None,  # total market cap (100m CNY to CNY)
            )

            logger.info(
                f"[Realtime quote - Tencent] {stock_code} {quote.name}: endpoint={TENCENT_REALTIME_ENDPOINT}, "
                f"price={quote.price}, change={quote.change_pct}%, volume_ratio={quote.volume_ratio}, "
                f"turnover={quote.turnover_rate}%, elapsed={api_elapsed:.2f}s"
            )
            return quote

        except Exception as e:
            api_elapsed = time.time() - api_start
            category, detail = _classify_realtime_http_error(e)
            failure_message = _build_realtime_failure_message(
                source_name="\u817e\u8baf",
                endpoint=TENCENT_REALTIME_ENDPOINT,
                stock_code=stock_code,
                symbol=symbol,
                category=category,
                detail=detail,
                elapsed=api_elapsed,
                error_type=type(e).__name__,
            )
            logger.info(failure_message)
            circuit_breaker.record_failure(source_key, failure_message)
            return None

    def _get_etf_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        Fetch ETF realtime quote data

        Data sources:ak.fund_etf_spot_em()
        Includes latest price, change, volume, amount, turnover, and more

        Args:
            stock_code: ETF \u4ee3\u7801

        Returns:
            UnifiedRealtimeQuote \u5bf9\u8c61; returns None on failure
        """
        import akshare as ak
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_etf"

        try:
            # Check cache
            current_time = time.time()
            if (_etf_realtime_cache['data'] is not None and
                current_time - _etf_realtime_cache['timestamp'] < _etf_realtime_cache['ttl']):
                df = _etf_realtime_cache['data']
                logger.debug(f"[Cache hit] Using cached ETF realtime quote data")
            else:
                last_error: Optional[Exception] = None
                df = None
                for attempt in range(1, 3):
                    try:
                        # Anti-blocking strategy
                        self._set_random_user_agent()
                        self._enforce_rate_limit()

                        logger.info(f"[API call] ak.fund_etf_spot_em() fetch ETF realtime quotes... (attempt {attempt}/2)")
                        import time as _time
                        api_start = _time.time()

                        df = ak.fund_etf_spot_em()

                        api_elapsed = _time.time() - api_start
                        logger.info(f"[API response] ak.fund_etf_spot_em succeeded: returned {len(df)} ETFs, elapsed {api_elapsed:.2f}s")
                        circuit_breaker.record_success(source_key)
                        break
                    except Exception as e:
                        last_error = e
                        logger.info(f"[API error] ak.fund_etf_spot_em fetch failed (attempt {attempt}/2): {e}")
                        time.sleep(min(2 ** attempt, 5))

                if df is None:
                    logger.info(f"[API error] ak.fund_etf_spot_em finally failed: {last_error}")
                    circuit_breaker.record_failure(source_key, str(last_error))
                    df = pd.DataFrame()
                _etf_realtime_cache['data'] = df
                _etf_realtime_cache['timestamp'] = current_time

            if df is None or df.empty:
                logger.info(f"[\u5b9e\u65f6\u884c\u60c5] ETF realtime quote data is empty; skipping {stock_code}")
                return None

            # Find target ETF
            row = df[df['\u4ee3\u7801'] == stock_code]
            if row.empty:
                logger.info(f"[API response] ETF not found {stock_code} realtime quote")
                return None

            row = row.iloc[0]

            # Use shared conversion helpers from realtime_types.py
            # Build ETF quote data
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get('\u540d\u79f0', '')),
                source=RealtimeSource.AKSHARE_EM,
                price=safe_float(row.get('\u6700\u65b0\u4ef7')),
                change_pct=safe_float(row.get('\u6da8\u8dcc\u5e45')),
                change_amount=safe_float(row.get('\u6da8\u8dcc\u989d')),
                volume=safe_int(row.get('\u6210\u4ea4\u91cf')),
                amount=safe_float(row.get('\u6210\u4ea4\u989d')),
                volume_ratio=safe_float(row.get('\u91cf\u6bd4')),
                turnover_rate=safe_float(row.get('\u6362\u624b\u7387')),
                amplitude=safe_float(row.get('\u632f\u5e45')),
                open_price=safe_float(row.get('\u5f00\u76d8\u4ef7')),
                high=safe_float(row.get('\u6700High\u4ef7')),
                low=safe_float(row.get('\u6700Low\u4ef7')),
                total_mv=safe_float(row.get('\u603b\u5e02\u503c')),
                circ_mv=safe_float(row.get('\u6d41\u901a\u5e02\u503c')),
                high_52w=safe_float(row.get('52\u5468\u6700High')),
                low_52w=safe_float(row.get('52\u5468\u6700Low')),
            )

            logger.info(f"[ETF realtime quote] {stock_code} {quote.name}: price={quote.price}, change={quote.change_pct}%, "
                       f"turnover={quote.turnover_rate}%")
            return quote

        except Exception as e:
            logger.info(f"[API error] \u83b7\u53d6 ETF {stock_code} \u5b9e\u65f6\u884c\u60c5\u5931\u8d25: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None

    def _get_hk_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        Fetch Hong Kong stock realtime quote data

        \u4e3b\u6570\u636e\u6e90: ak.stock_hk_spot_em() (Eastmoney)
        Fallback source: ak.stock_hk_spot() (Sina)
        \u5305\u542b: \u6700\u65b0\u4ef7、\u6da8\u8dcc\u5e45、\u6210\u4ea4\u91cf、\u6210\u4ea4\u989d\u7b49

        Args:
            stock_code: Hong Kong stock code

        Returns:
            UnifiedRealtimeQuote \u5bf9\u8c61; returns None on failure
        """
        import akshare as ak
        circuit_breaker = get_realtime_circuit_breaker()
        em_key = "akshare_hk_em"
        sina_key = "akshare_hk_sina"

        # Anti-blocking strategy
        self._set_random_user_agent()
        self._enforce_rate_limit()

        # Ensure code format is correct: five digits
        raw_code = stock_code.strip().lower()
        if raw_code.endswith('.hk'):
            raw_code = raw_code[:-3]
        if raw_code.startswith('hk'):
            raw_code = raw_code[2:]
        code = raw_code.zfill(5)

        # --- \u4e3b\u6570\u636e\u6e90: Eastmoney ---
        if circuit_breaker.is_available(em_key):
            try:
                logger.info(f"[API call] ak.stock_hk_spot_em() fetch Hong Kong stock realtime quotes...")
                import time as _time
                api_start = _time.time()

                df = ak.stock_hk_spot_em()

                api_elapsed = _time.time() - api_start
                logger.info(f"[API response] ak.stock_hk_spot_em succeeded: returned {len(df)} Hong Kong stocks, elapsed {api_elapsed:.2f}s")
                circuit_breaker.record_success(em_key)

                # Find target Hong Kong stock
                row = df[df['\u4ee3\u7801'] == code]
                if row.empty:
                    logger.info(f"[API response] Hong Kong stock not found {code} realtime quote (stock_hk_spot_em)")
                else:
                    row = row.iloc[0]
                    quote = UnifiedRealtimeQuote(
                        code=stock_code,
                        name=str(row.get('\u540d\u79f0', '')),
                        source=RealtimeSource.AKSHARE_EM,
                        price=safe_float(row.get('\u6700\u65b0\u4ef7')),
                        change_pct=safe_float(row.get('\u6da8\u8dcc\u5e45')),
                        change_amount=safe_float(row.get('\u6da8\u8dcc\u989d')),
                        volume=safe_int(row.get('\u6210\u4ea4\u91cf')),
                        amount=safe_float(row.get('\u6210\u4ea4\u989d')),
                        volume_ratio=safe_float(row.get('\u91cf\u6bd4')),
                        turnover_rate=safe_float(row.get('\u6362\u624b\u7387')),
                        amplitude=safe_float(row.get('\u632f\u5e45')),
                        pe_ratio=safe_float(row.get('PE ratio')),
                        pb_ratio=safe_float(row.get('PB ratio')),
                        total_mv=safe_float(row.get('\u603b\u5e02\u503c')),
                        circ_mv=safe_float(row.get('\u6d41\u901a\u5e02\u503c')),
                        high_52w=safe_float(row.get('52\u5468\u6700High')),
                        low_52w=safe_float(row.get('52\u5468\u6700Low')),
                    )
                    logger.info(f"[HK realtime quote] {stock_code} {quote.name}: price={quote.price}, change={quote.change_pct}%, "
                                f"turnover={quote.turnover_rate}%")
                    return quote

            except Exception as e:
                logger.warning(f"[API error] ak.stock_hk_spot_em \u83b7\u53d6\u6e2f\u80a1 {stock_code} \u5931\u8d25: {e}; trying stock_hk_spot fallback API")
                circuit_breaker.record_failure(em_key, str(e))
        else:
            logger.info(f"[Circuit breaker] \u6570\u636e\u6e90 {em_key} is open; trying fallback path")

        # --- Fallback source: Sina ---
        if not circuit_breaker.is_available(sina_key):
            logger.info(f"[Circuit breaker] \u6570\u636e\u6e90 {sina_key} is open; skipping\u5907\u7528\u94fe\u8def")
            return None

        try:
            logger.info(f"[API call] ak.stock_hk_spot() fetch Hong Kong stock realtime quotes (\u5907\u7528)...")
            import time as _time
            api_start = _time.time()

            df_spot = ak.stock_hk_spot()

            api_elapsed = _time.time() - api_start
            logger.info(f"[API response] ak.stock_hk_spot succeeded: returned {len(df_spot)} Hong Kong stocks, elapsed {api_elapsed:.2f}s")

            row = df_spot[df_spot['\u4ee3\u7801'] == code]
            if row.empty:
                logger.info(f"[API response] Hong Kong stock not found {code} realtime quote (stock_hk_spot)")
                return None

            row = row.iloc[0]
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get('\u540d\u79f0', '')),
                source=RealtimeSource.AKSHARE_EM,
                price=safe_float(row.get('\u6700\u65b0\u4ef7')),
                change_pct=safe_float(row.get('\u6da8\u8dcc\u5e45')),
                change_amount=safe_float(row.get('\u6da8\u8dcc\u989d')),
                volume=safe_int(row.get('\u6210\u4ea4\u91cf')),
                amount=safe_float(row.get('\u6210\u4ea4\u989d')),
            )
            circuit_breaker.record_success(sina_key)
            logger.info(f"[HK realtime quote - fallback] {stock_code} {quote.name}: price={quote.price}, change={quote.change_pct}%")
            return quote

        except Exception as e:
            logger.info(f"[API error] ak.stock_hk_spot fallback API also failed: {e}")
            circuit_breaker.record_failure(sina_key, str(e))
            return None

    def get_chip_distribution(self, stock_code: str) -> Optional[ChipDistribution]:
        """
        Fetch chip distribution data

        Data sources:ak.stock_cyq_em()
        Includes profit ratio, average cost, and chip concentration

        Note: ETFs/indices have no chip distribution data and return None directly

        Args:
            stock_code: stock code

        Returns:
            ChipDistribution \u5bf9\u8c61 (latest day data); returns None on failure
        """
        import akshare as ak

        # US stocks have no chip distribution data through Akshare
        if _is_us_code(stock_code):
            logger.debug(f"[API skip] {stock_code} is a US stock; no chip distribution data")
            return None

        # Hong Kong stocks have no chip distribution data; stock_cyq_em is A-share only
        if _is_hk_code(stock_code):
            logger.debug(f"[API skip] {stock_code} is a Hong Kong stock; no chip distribution data")
            return None

        # ETFs/indices have no chip distribution data
        if _is_etf_code(stock_code):
            logger.debug(f"[API skip] {stock_code} is an ETF/index; no chip distribution data")
            return None

        try:
            # Anti-blocking strategy
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info(f"[API call] ak.stock_cyq_em(symbol={stock_code}) fetch chip distribution...")
            import time as _time
            api_start = _time.time()

            df = ak.stock_cyq_em(symbol=stock_code)

            api_elapsed = _time.time() - api_start

            if df.empty:
                logger.warning(f"[API response] ak.stock_cyq_em returned empty data, elapsed {api_elapsed:.2f}s")
                return None

            logger.info(f"[API response] ak.stock_cyq_em succeeded: returned {len(df)} days of data, elapsed {api_elapsed:.2f}s")
            logger.debug(f"[API response] \u7b79\u7801\u6570\u636ecolumns: {list(df.columns)}")

            # \u53d6latest day data
            latest = df.iloc[-1]

            # Use shared conversion helpers from realtime_types.py
            chip = ChipDistribution(
                code=stock_code,
                date=str(latest.get('\u65e5\u671f', '')),
                profit_ratio=safe_float(latest.get('\u83b7\u5229\u6bd4\u4f8b')),
                avg_cost=safe_float(latest.get('\u5e73\u5747\u6210\u672c')),
                cost_90_low=safe_float(latest.get('90\u6210\u672c-Low')),
                cost_90_high=safe_float(latest.get('90\u6210\u672c-High')),
                concentration_90=safe_float(latest.get('90\u96c6Medium\u5ea6')),
                cost_70_low=safe_float(latest.get('70\u6210\u672c-Low')),
                cost_70_high=safe_float(latest.get('70\u6210\u672c-High')),
                concentration_70=safe_float(latest.get('70\u96c6Medium\u5ea6')),
            )

            logger.info(f"[Chip distribution] {stock_code} date={chip.date}: profit_ratio={chip.profit_ratio:.1%}, "
                       f"avg_cost={chip.avg_cost}, 90%concentration={chip.concentration_90:.2%}, "
                       f"70%concentration={chip.concentration_70:.2%}")
            return chip

        except Exception as e:
            logger.error(f"[API error] \u83b7\u53d6 {stock_code} chip distribution failed: {e}")
            return None

    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        Fetch enhanced data: historical candles, realtime quote, and chip distribution

        Args:
            stock_code: stock code
            days: historical data days

        Returns:
            dictionary containing all data
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
            'chip_distribution': None,
        }

        # Fetch daily data
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"\u83b7\u53d6 {stock_code} daily data failed: {e}")

        # Fetch realtime quote
        result['realtime_quote'] = self.get_realtime_quote(stock_code)

        # fetch chip distribution
        result['chip_distribution'] = self.get_chip_distribution(stock_code)

        return result

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        Fetch major-index realtime quotes via Sina; A-share only
        """
        if region != "cn":
            return None
        import akshare as ak

        # Major index code mapping
        indices_map = {
            'sh000001': 'SSE Composite',
            'sz399001': 'SZSE Component',
            'sz399006': 'ChiNext Index',
            'sh000688': 'STAR 50',
            'sh000016': 'SSE 50',
            'sh000300': 'CSI 300',
        }

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            # \u4f7f\u7528 akshare \u83b7\u53d6\u6307\u6570\u884c\u60c5 (Sina Finance\u63a5\u53e3)
            df = ak.stock_zh_index_spot_sina()

            results = []
            if df is not None and not df.empty:
                for code, name in indices_map.items():
                    # Find matching index
                    row = df[df['\u4ee3\u7801'] == code]
                    if row.empty:
                        # Try lookup with prefix
                        row = df[df['\u4ee3\u7801'].str.contains(code)]

                    if not row.empty:
                        row = row.iloc[0]
                        current = safe_float(row.get('\u6700\u65b0\u4ef7', 0))
                        prev_close = safe_float(row.get('\u6628\u6536', 0))
                        high = safe_float(row.get('\u6700High', 0))
                        low = safe_float(row.get('\u6700Low', 0))

                        # Calculate amplitude
                        amplitude = 0.0
                        if prev_close > 0:
                            amplitude = (high - low) / prev_close * 100

                        results.append({
                            'code': code,
                            'name': name,
                            'current': current,
                            'change': safe_float(row.get('\u6da8\u8dcc\u989d', 0)),
                            'change_pct': safe_float(row.get('\u6da8\u8dcc\u5e45', 0)),
                            'open': safe_float(row.get('\u4eca\u5f00', 0)),
                            'high': high,
                            'low': low,
                            'prev_close': prev_close,
                            'volume': safe_float(row.get('\u6210\u4ea4\u91cf', 0)),
                            'amount': safe_float(row.get('\u6210\u4ea4\u989d', 0)),
                            'amplitude': amplitude,
                        })
            return results

        except Exception as e:
            logger.error(f"[Akshare] failed to fetch index quotes: {e}")
            return None

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """
        Fetch market breadth statistics

        Data source priority:
        1. Eastmoney API (ak.stock_zh_a_spot_em)
        2. Sina API (ak.stock_zh_a_spot)
        """
        import akshare as ak

        # \u4f18\u5148Eastmoney API
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            started_at = time.monotonic()
            logger.info(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot_em action=request_start"
            )
            df = ak.stock_zh_a_spot_em()
            elapsed = time.monotonic() - started_at
            logger.info(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot_em action=request_complete elapsed=%.2fs",
                elapsed,
            )
            if df is not None and not df.empty:
                return self._calc_market_stats(df)
            logger.warning(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot_em action=parse status=empty"
            )
        except Exception as e:
            logger.warning(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot_em action=failed error=%s fallback=ak.stock_zh_a_spot",
                e,
            )

        # \u4e1c\u8d22\u5931\u8d25\u540e; \u5c1d\u8bd5Sina API
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            started_at = time.monotonic()
            logger.info(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot action=request_start"
            )
            df = ak.stock_zh_a_spot()
            elapsed = time.monotonic() - started_at
            logger.info(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot action=request_complete elapsed=%.2fs",
                elapsed,
            )
            if df is not None and not df.empty:
                return self._calc_market_stats(df)
            logger.warning(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot action=parse status=empty"
            )
        except Exception as e:
            logger.error(
                "[MarketStats] component=market_stats provider=AkshareFetcher "
                "api=ak.stock_zh_a_spot action=failed error=%s",
                e,
            )

        return None

    def _calc_market_stats(
        self,
        df: pd.DataFrame,
        ) -> Optional[Dict[str, Any]]:
        """Calculate market breadth statistics from quote DataFrame."""
        import numpy as np

        df = df.copy()

        # 1. Extract base comparison data: \u6700\u65b0\u4ef7、\u6628\u6536
        # \u517c\u5bb9\u4e0d\u540c\u63a5\u53e3\u8fd4\u56de\u7684columns sina/em efinance tushare xtdata
        code_col = next((c for c in ['\u4ee3\u7801', 'stock code', 'ts_code','stock_code'] if c in df.columns), None)
        name_col = next((c for c in ['\u540d\u79f0', '\u80a1\u7968\u540d\u79f0','name','name'] if c in df.columns), None)
        close_col = next((c for c in ['\u6700\u65b0\u4ef7', '\u6700\u65b0\u4ef7', 'close','lastPrice'] if c in df.columns), None)
        pre_close_col = next((c for c in ['\u6628\u6536', '\u6628\u65e5\u6536\u76d8', 'pre_close','lastClose'] if c in df.columns), None)
        amount_col = next((c for c in ['\u6210\u4ea4\u989d', '\u6210\u4ea4\u989d', 'amount','amount'] if c in df.columns), None)

        limit_up_count = 0
        limit_down_count = 0
        up_count = 0
        down_count = 0
        flat_count = 0

        for code, name, current_price, pre_close, amount in zip(
            df[code_col], df[name_col], df[close_col], df[pre_close_col], df[amount_col]
        ):

            # Suspension filtering efinance \u7684\u505c\u724c\u6570\u636e\u6709\u65f6\u5019\u4f1a\u7f3a\u5931\u4ef7\u683c\u663e\u793a\u4e3a '-'; em \u663e\u793a\u4e3anone
            if pd.isna(current_price) or pd.isna(pre_close) or current_price in ['-'] or pre_close in ['-'] or amount == 0:
                continue

            # em、efinance \u4e3astr \u9700\u8981\u8f6c\u6362\u4e3afloat
            current_price = float(current_price)
            pre_close = float(pre_close)

            # Get numeric code without prefix
            pure_code = normalize_stock_code(str(code))

            # A. \u786e\u5b9a\u6bcfstocks\u7684\u6da8\u8dcc\u5e45\u6bd4\u4f8b (\u4f7f\u7528\u7eaf\u6570\u5b57\u4ee3\u7801\u5224\u65ad)
            if is_bse_code(pure_code):
                ratio = 0.30
            elif is_kc_cy_stock(pure_code): #pure_code.startswith(('688', '30')):
                ratio = 0.20
            elif is_st_stock(name): #'ST' in str_name:
                ratio = 0.05
            else:
                ratio = 0.10

            # B. Calculate limit-up/down prices strictly by A-share rules: \u6628\u6536 * (1 ± \u6bd4\u4f8b) -> round to two decimals
            limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
            limit_down_price = np.floor(pre_close * (1 - ratio) * 100 + 0.5) / 100.0

            limit_up_price_Tolerance = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
            limit_down_price_Tolerance = round(abs(pre_close * (1 - ratio) - limit_down_price), 10)

            # C. Exact comparison
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

        # Count statistics
        stats = {
            'up_count': up_count,
            'down_count': down_count,
            'flat_count': flat_count,
            'limit_up_count': limit_up_count,
            'limit_down_count': limit_down_count,
            'total_amount': 0.0,
        }

        # Turnover amount statistics
        if amount_col and amount_col in df.columns:
            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
            stats['total_amount'] = (df[amount_col].sum() / 1e8)

        return stats

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """
        Fetch sector performance rankings

        Data source priority:
        1. Eastmoney API (ak.stock_board_industry_name_em)
        2. Sina API (ak.stock_sector_spot)
        """
        import akshare as ak

        def _get_rank_top_n(df: pd.DataFrame, change_col: str, industry_name: str, n: int) -> Tuple[list, list]:
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])

            # Top gainers
            top = df.nlargest(n, change_col)
            top_sectors = [
                {'name': row[industry_name], 'change_pct': row[change_col]}
                for _, row in top.iterrows()
            ]

            bottom = df.nsmallest(n, change_col)
            bottom_sectors = [
                {'name': row[industry_name], 'change_pct': row[change_col]}
                for _, row in bottom.iterrows()
            ]
            return top_sectors, bottom_sectors

        # \u4f18\u5148Eastmoney API
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[API call] ak.stock_board_industry_name_em() fetch sector rankings...")
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                change_col = '\u6da8\u8dcc\u5e45'
                name = '\u677fchunks\u540d\u79f0'
                return _get_rank_top_n(df, change_col, name, n)

        except Exception as e:
            logger.warning(f"[Akshare] Eastmoney API\u83b7\u53d6\u884c\u4e1asector ranking failed: {e}; \u5c1d\u8bd5Sina API")

        # \u4e1c\u8d22\u5931\u8d25\u540e; \u5c1d\u8bd5Sina API
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[API call] ak.stock_sector_spot() \u83b7\u53d6\u884c\u4e1a\u677fchunks\u6392\u884c(\u65b0\u6d6a)...")
            df = ak.stock_sector_spot(indicator='\u884c\u4e1a')
            if df is None or df.empty:
                return None
            change_col = '\u6da8\u8dcc\u5e45'
            name = '\u677fchunks'
            return _get_rank_top_n(df, change_col, name, n)

        except Exception as e:
            logger.error(f"[Akshare] Sina APIfetch sector rankings\u4e5f\u5931\u8d25: {e}")
            return None

    def get_concept_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """Fetch concept/theme performance rankings."""
        import akshare as ak

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[API call] ak.stock_board_concept_name_em() fetch concept rankings...")
            df = ak.stock_board_concept_name_em()
            if df is None or df.empty:
                return None

            change_col = '\u6da8\u8dcc\u5e45'
            name_col = '\u677fchunks\u540d\u79f0'
            if change_col not in df.columns or name_col not in df.columns:
                return None

            df = df.copy()
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])
            top = df.nlargest(n, change_col)
            bottom = df.nsmallest(n, change_col)
            return (
                [
                    {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                    for _, row in top.iterrows()
                ],
                [
                    {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                    for _, row in bottom.iterrows()
                ],
            )
        except Exception as e:
            logger.warning(f"[Akshare] fetch concept rankings\u5931\u8d25: {e}")
            return None

    def get_hot_stocks(self, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Fetch hot-stock rankings with no-config source fallback."""
        import akshare as ak

        fetch_attempts = (
            ("Eastmoney popularity ranking", lambda top_n: self._get_eastmoney_hot_stocks(ak, top_n)),
            ("Eastmoney surge ranking", lambda top_n: self._get_eastmoney_hot_up_stocks(ak, top_n)),
            ("Xueqiu watchlist ranking", lambda top_n: self._get_xueqiu_hot_stocks(ak, top_n)),
        )
        last_error = ""
        for source, fetch in fetch_attempts:
            try:
                rows = fetch(n)
                if rows:
                    return rows[:n]
            except Exception as e:
                last_error = f"{source}: {e}"
                logger.debug("[Akshare] hot-stock candidate source failed source=%s: %s", source, e)
        if last_error:
            logger.warning("[Akshare] all hot-stock candidate sources failed: %s", last_error)
        return None

    def _get_eastmoney_hot_stocks(self, ak: Any, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Fetch Eastmoney popularity ranking."""
        self._set_random_user_agent()
        self._enforce_rate_limit()

        logger.info("[API call] ak.stock_hot_rank_em() fetch Eastmoney popular stocks...")
        df = ak.stock_hot_rank_em()
        if df is None or df.empty:
            return None

        rows: List[Dict[str, Any]] = []
        for _, row in df.head(n).iterrows():
            rows.append({
                'rank': self._safe_int(row.get('\u5f53\u524d\u6392\u540d')),
                'code': str(row.get('\u4ee3\u7801', '')).strip(),
                'name': str(row.get('\u80a1\u7968\u540d\u79f0', '')).strip(),
                'price': self._safe_float(row.get('\u6700\u65b0\u4ef7')),
                'change_pct': self._safe_float(row.get('\u6da8\u8dcc\u5e45')),
                'source': 'Eastmoney popularity ranking',
            })
        return rows

    def _get_eastmoney_hot_up_stocks(self, ak: Any, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6Eastmoney surge ranking."""
        self._set_random_user_agent()
        self._enforce_rate_limit()

        logger.info("[API call] ak.stock_hot_up_em() \u83b7\u53d6Eastmoney surge ranking...")
        df = ak.stock_hot_up_em()
        if df is None or df.empty:
            return None

        code_col = self._find_first_column(df, ("\u4ee3\u7801", "stock code"))
        name_col = self._find_first_column(df, ("\u80a1\u7968\u540d\u79f0", "\u540d\u79f0", "\u80a1\u7968\u7b80\u79f0"))
        rank_col = self._find_first_column(df, ("\u5f53\u524d\u6392\u540d", "\u6392\u540d", "\u5e8f\u53f7"))
        price_col = self._find_first_column(df, ("\u6700\u65b0\u4ef7", "\u73b0\u4ef7"))
        change_col = self._find_column_containing(df, ("\u6da8\u8dcc\u5e45",))
        if not code_col or not name_col:
            return None

        rows: List[Dict[str, Any]] = []
        for _, row in df.head(n).iterrows():
            rows.append({
                'rank': self._safe_int(row.get(rank_col)) if rank_col else len(rows) + 1,
                'code': str(row.get(code_col, '')).strip(),
                'name': str(row.get(name_col, '')).strip(),
                'price': self._safe_float(row.get(price_col)) if price_col else None,
                'change_pct': self._safe_float(row.get(change_col)) if change_col else None,
                'source': 'Eastmoney surge ranking',
            })
        return rows

    def _get_xueqiu_hot_stocks(self, ak: Any, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """\u83b7\u53d6Xueqiu watchlist ranking\u515c\u5e95.\u8be5\u63a5\u53e3\u8f83\u6162; \u4ec5\u5728\u4eba\u6c14\u699c\u5931\u8d25\u540e\u5c1d\u8bd5."""
        self._set_random_user_agent()
        self._enforce_rate_limit()

        logger.info("[API call] ak.stock_hot_follow_xq() \u83b7\u53d6Xueqiu watchlist ranking...")
        df = ak.stock_hot_follow_xq(symbol='\u6700\u70ed\u95e8')
        if df is None or df.empty:
            return None

        rows: List[Dict[str, Any]] = []
        for idx, (_, row) in enumerate(df.head(n).iterrows(), 1):
            rows.append({
                'rank': idx,
                'code': str(row.get('stock code', '')).strip(),
                'name': str(row.get('\u80a1\u7968\u7b80\u79f0', '')).strip(),
                'price': self._safe_float(row.get('\u6700\u65b0\u4ef7')),
                'change_pct': None,
                'source': 'Xueqiu watchlist ranking',
            })
        return rows

    def get_limit_up_pool(
        self,
        date: Optional[str] = None,
        n: int = 20,
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch limit-up pool, prioritizing consecutive-board count and seal time."""
        import akshare as ak

        query_date = date or datetime.now().strftime('%Y%m%d')
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[API call] ak.stock_zt_pool_em(date=%s) fetch limit-up pool...", query_date)
            df = ak.stock_zt_pool_em(date=query_date)
            if df is None or df.empty:
                return None

            df = df.copy()
            for col in ('\u8fde\u677f\u6570', '\u5c01\u677f\u8d44\u91d1', '\u6210\u4ea4\u989d', '\u6362\u624b\u7387', '\u6da8\u8dcc\u5e45'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            if '\u9996\u6b21\u5c01\u677f\u65f6\u95f4' in df.columns:
                df['\u9996\u6b21\u5c01\u677f\u65f6\u95f4'] = df['\u9996\u6b21\u5c01\u677f\u65f6\u95f4'].map(self._normalize_limit_time_value)
                df['_\u9996\u6b21\u5c01\u677f\u65f6\u95f4\u6392\u5e8f'] = df['\u9996\u6b21\u5c01\u677f\u65f6\u95f4'].where(df['\u9996\u6b21\u5c01\u677f\u65f6\u95f4'] != '', '999999')
            sort_cols = [col for col in ('\u8fde\u677f\u6570', '_\u9996\u6b21\u5c01\u677f\u65f6\u95f4\u6392\u5e8f') if col in df.columns]
            if sort_cols:
                ascending = [False if col == '\u8fde\u677f\u6570' else True for col in sort_cols]
                df = df.sort_values(sort_cols, ascending=ascending)

            rows: List[Dict[str, Any]] = []
            for _, row in df.head(n).iterrows():
                rows.append({
                    'code': str(row.get('\u4ee3\u7801', '')).strip(),
                    'name': str(row.get('\u540d\u79f0', '')).strip(),
                    'change_pct': self._safe_float(row.get('\u6da8\u8dcc\u5e45')),
                    'price': self._safe_float(row.get('\u6700\u65b0\u4ef7')),
                    'amount': self._safe_float(row.get('\u6210\u4ea4\u989d')),
                    'turnover_rate': self._safe_float(row.get('\u6362\u624b\u7387')),
                    'seal_amount': self._safe_float(row.get('\u5c01\u677f\u8d44\u91d1')),
                    'first_limit_time': str(row.get('\u9996\u6b21\u5c01\u677f\u65f6\u95f4', '')).strip(),
                    'last_limit_time': self._normalize_limit_time_value(row.get('\u6700\u540e\u5c01\u677f\u65f6\u95f4')),
                    'break_count': self._safe_int(row.get('\u70b8\u677f\u6b21\u6570')),
                    'limit_stat': str(row.get('\u6da8\u505c\u7edf\u8ba1', '')).strip(),
                    'consecutive_boards': self._safe_int(row.get('\u8fde\u677f\u6570')),
                    'industry': str(row.get('\u6240\u5c5e\u884c\u4e1a', '')).strip(),
                })
            return rows
        except Exception as e:
            logger.warning(f"[Akshare] fetch limit-up pool\u5931\u8d25: {e}")
            return None

    @staticmethod
    def _normalize_limit_time_value(value: Any) -> str:
        """Normalize AkShare HHMMSS-like seal time values to zero-padded HHMMSS."""
        try:
            if pd.isna(value):
                return ""
        except TypeError:
            pass

        text = str(value).strip()
        if not text or text.lower() in {"nan", "nat", "none", "null", "-", "--"}:
            return ""

        if ":" in text:
            parts = text.split(":")
            try:
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                second = int(parts[2]) if len(parts) > 2 else 0
                return f"{hour:02d}{minute:02d}{second:02d}"
            except (TypeError, ValueError):
                return text

        try:
            return f"{int(float(text)):06d}"
        except (TypeError, ValueError):
            digits = "".join(ch for ch in text if ch.isdigit())
            return digits.zfill(6) if digits else text

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _find_first_column(df: pd.DataFrame, candidates: Tuple[str, ...]) -> Optional[str]:
        columns = [str(col) for col in df.columns]
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    @staticmethod
    def _find_column_containing(df: pd.DataFrame, keywords: Tuple[str, ...]) -> Optional[str]:
        for col in df.columns:
            col_text = str(col)
            if all(keyword in col_text for keyword in keywords):
                return col
        return None


if __name__ == "__main__":
    # Test code
    logging.basicConfig(level=logging.DEBUG)

    fetcher = AkshareFetcher()

    # Test ordinary stock
    print("=" * 50)
    print("Test ordinary stock\u6570\u636e\u83b7\u53d6")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('600519')  # Moutai
        print(f"[\u80a1\u7968] fetch succeeded, count {len(df)} rows")
        print(df.tail())
    except Exception as e:
        print(f"[\u80a1\u7968] fetch failed: {e}")

    # Test ETF fund
    print("\n" + "=" * 50)
    print("Test ETF fund\u6570\u636e\u83b7\u53d6")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('512400')  # Nonferrous metals leading ETF
        print(f"[ETF] fetch succeeded, count {len(df)} rows")
        print(df.tail())
    except Exception as e:
        print(f"[ETF] fetch failed: {e}")

    # Test ETF realtime quote
    print("\n" + "=" * 50)
    print("Test ETF realtime quote\u83b7\u53d6")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('512880')  # Securities ETF
        if quote:
            print(f"[ETF\u5b9e\u65f6] {quote.name}: price={quote.price}, \u6da8\u8dcc\u5e45={quote.change_pct}%")
        else:
            print("[ETF\u5b9e\u65f6] No data fetched")
    except Exception as e:
        print(f"[ETF\u5b9e\u65f6] fetch failed: {e}")

    # Test Hong Kong stock historical data
    print("\n" + "=" * 50)
    print("Test Hong Kong stock historical data\u83b7\u53d6")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('00700')  # Tencent Holdings
        print(f"[\u6e2f\u80a1] fetch succeeded, count {len(df)} rows")
        print(df.tail())
    except Exception as e:
        print(f"[\u6e2f\u80a1] fetch failed: {e}")

    # Test Hong Kong stock realtime quote
    print("\n" + "=" * 50)
    print("Test Hong Kong stock realtime quote\u83b7\u53d6")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('00700')  # Tencent Holdings
        if quote:
            print(f"[\u6e2f\u80a1\u5b9e\u65f6] {quote.name}: price={quote.price}, \u6da8\u8dcc\u5e45={quote.change_pct}%")
        else:
            print("[\u6e2f\u80a1\u5b9e\u65f6] No data fetched")
    except Exception as e:
        print(f"[\u6e2f\u80a1\u5b9e\u65f6] fetch failed: {e}")

    # Test market statistics
    print("\n" + "=" * 50)
    print("Testing get_market_stats (akshare)")
    print("=" * 50)
    try:
        stats = fetcher.get_market_stats()
        if stats:
            print(f"Market Stats successfully computed:")
            print(f"Up: {stats['up_count']} (Limit Up: {stats['limit_up_count']})")
            print(f"Down: {stats['down_count']} (Limit Down: {stats['limit_down_count']})")
            print(f"Flat: {stats['flat_count']}")
            print(f"Total Amount: {stats['total_amount']:.2f} hundred million CNY")
        else:
            print("Failed to compute market stats.")
    except Exception as e:
        print(f"Failed to compute market stats: {e}")

    # Test chip distribution data
    print("\n" + "=" * 50)
    print("Test chip distribution data\u83b7\u53d6")
    print("=" * 50)
    try:
        chip = fetcher.get_chip_distribution('600519')  # Moutai
    except Exception as e:
        print(f"[Chip distribution] fetch failed: {e}")

    # Test sector ranking
    print("\n" + "=" * 50)
    print("Test sector ranking\u83b7\u53d6")
    print("=" * 50)
    try:
        rankings = fetcher.get_sector_rankings(n=5)
        if rankings:
            top, bottom = rankings
            print("Top gainers Top 5:")
            for sector in top:
                print(f"{sector['name']}: {sector['change_pct']}%")
            print("\nTop losers Top 5:")
            for sector in bottom:
                print(f"{sector['name']}: {sector['change_pct']}%")
        else:
            print("No sector ranking data fetched")
    except Exception as e:
        print(f"[\u884c\u4e1a\u677fchunks\u6392\u540d] fetch failed: {e}")
