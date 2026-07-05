# -*- coding: utf-8 -*-
"""
===================================
PytdxFetcher - Tongdaxindata source (Priority 2)
===================================

\u6570\u636esource: Tongdaxin\u884c\u60c5\u670d\u52a1\u5668 (pytdx library)
\u7279\u70b9: \u514d\u8d39、\u65e0\u9700 Token、\u76f4\u8fde\u884c\u60c5\u670d\u52a1\u5668
\u4f18\u70b9: \u5b9e\u65f6\u6570\u636e、\u7a33\u5b9a、\u65e0\u914d\u989dlimit

\u5173\u952estrategy:
1. \u591a\u670d\u52a1\u5668\u81ea\u52a8\u5207\u6362
2. \u8fde\u63a5\u8d85\u65f6\u81ea\u52a8\u91cd\u8fde
3. failed\u540eindex\u9000\u907f\u91cd\u8bd5
"""

import logging
import re
import time
from contextlib import contextmanager
from typing import Optional, Generator, List, Tuple

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import (
    BaseFetcher,
    DataFetchError,
    DataSourceUnavailableError,
    STANDARD_COLUMNS,
    is_bse_code,
    normalize_stock_code,
    _is_hk_market,
)
import os

logger = logging.getLogger(__name__)

_PYTDX_CONNECTION_COOLDOWN_SECONDS = 15.0


def _parse_hosts_from_env() -> Optional[List[Tuple[str, int]]]:
    """
    \u4ece\u73af\u5883\u53d8\u91cf\u6784\u5efaTongdaxin\u670d\u52a1\u5668\u5217\u8868.

    \u4f18\u5148\u7ea7:
    1. PYTDX_SERVERS: \u9017\u53f7\u5206\u9694 "ip:port,ip:port" (\u5982 "192.168.1.1:7709,10.0.0.1:7709")
    2. PYTDX_HOST + PYTDX_PORT: \u5355\u4e2a\u670d\u52a1\u5668
    3. \u5747not configured\u65f6\u8fd4\u56de None (\u8c03\u7528\u65b9\u4f7f\u7528 DEFAULT_HOSTS)
    """
    servers = os.getenv("PYTDX_SERVERS", "").strip()
    if servers:
        result = []
        for part in servers.split(","):
            part = part.strip()
            if ":" in part:
                host, port_str = part.rsplit(":", 1)
                host, port_str = host.strip(), port_str.strip()
                if host and port_str:
                    try:
                        result.append((host, int(port_str)))
                    except ValueError:
                        logger.warning(f"Invalid PYTDX_SERVERS entry: {part}")
            else:
                logger.warning(f"Invalid PYTDX_SERVERS entry (missing port): {part}")
        if result:
            return result

    host = os.getenv("PYTDX_HOST", "").strip()
    port_str = os.getenv("PYTDX_PORT", "").strip()
    if host and port_str:
        try:
            return [(host, int(port_str))]
        except ValueError:
            logger.warning(f"Invalid PYTDX_HOST/PYTDX_PORT: {host}:{port_str}")

    return None


def _is_us_code(stock_code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3aUS stock

    US stockcode\u89c4\u5219:
    - 1-5\u4e2a\u5927\u5199\u5b57\u6bcd; \u5982 'AAPL', 'TSLA'
    - \u53ef\u80fd\u5305\u542b '.'; \u5982 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class PytdxFetcher(BaseFetcher):
    """
    Tongdaxindata source\u5b9e\u73b0

    \u4f18\u5148\u7ea7: 2 (\u4e0e Tushare \u540c\u7ea7)
    \u6570\u636esource: Tongdaxin\u884c\u60c5\u670d\u52a1\u5668

    \u5173\u952estrategy:
    - \u81ea\u52a8\u9009\u62e9\u6700\u4f18\u670d\u52a1\u5668
    - \u8fde\u63a5failed\u81ea\u52a8\u5207\u6362\u670d\u52a1\u5668
    - failed\u540eindex\u9000\u907f\u91cd\u8bd5

    Pytdx \u7279\u70b9:
    - \u514d\u8d39、\u65e0\u9700\u6ce8\u518c
    - \u76f4\u8fde\u884c\u60c5\u670d\u52a1\u5668
    - \u652f\u6301realtime quote\u548chistory\u6570\u636e
    - \u652f\u6301stock namequery
    """

    name = "PytdxFetcher"
    priority = int(os.getenv("PYTDX_PRIORITY", "2"))

    # defaultTongdaxin\u884c\u60c5\u670d\u52a1\u5668\u5217\u8868
    DEFAULT_HOSTS = [
        ("119.147.212.81", 7709),  # \u6df1\u5733
        ("112.74.214.43", 7727),   # \u6df1\u5733
        ("221.231.141.60", 7709),  # \u4e0a\u6d77
        ("101.227.73.20", 7709),   # \u4e0a\u6d77
        ("101.227.77.254", 7709),  # \u4e0a\u6d77
        ("14.215.128.18", 7709),   # \u5e7f\u5dde
        ("59.173.18.140", 7709),   # \u6b66\u6c49
        ("180.153.39.51", 7709),   # \u676d\u5dde
    ]
    # Pytdx get_security_list returns at most 1000 items per page
    SECURITY_LIST_PAGE_SIZE = 1000

    def __init__(self, hosts: Optional[List[Tuple[str, int]]] = None):
        """
        \u521d\u59cb\u5316 PytdxFetcher

        Args:
            hosts: \u670d\u52a1\u5668\u5217\u8868 [(host, port), ...].\u82e5\u672a\u4f20\u5165; \u4f18\u5148\u4f7f\u7528\u73af\u5883\u53d8\u91cf
                   PYTDX_SERVERS (ip:port,ip:port)or PYTDX_HOST+PYTDX_PORT;
                   \u5426\u5219\u4f7f\u7528\u5185\u7f6e DEFAULT_HOSTS.
        """
        if hosts is not None:
            self._hosts = hosts
        else:
            env_hosts = _parse_hosts_from_env()
            self._hosts = env_hosts if env_hosts else self.DEFAULT_HOSTS
        self._api = None
        self._connected = False
        self._current_host_idx = 0
        self._stock_list_cache = None  # \u80a1\u7968\u5217\u8868cache
        self._stock_name_cache = {}    # stock namecache {code: name}
        self._unavailable_until = 0.0
        self._last_unavailable_reason = ""

    def _is_in_connection_cooldown(self) -> bool:
        return time.time() < self._unavailable_until

    def _mark_connection_cooldown(self, reason: str) -> None:
        self._unavailable_until = time.time() + _PYTDX_CONNECTION_COOLDOWN_SECONDS
        self._last_unavailable_reason = str(reason or "").strip()
        logger.info(
            "Pytdx \u8fde\u63a5failed; \u8fdb\u5165\u51b7\u5374 %.0fs: %s",
            _PYTDX_CONNECTION_COOLDOWN_SECONDS,
            self._last_unavailable_reason or "unknown",
        )

    def is_available_for_request(self, capability: str = "") -> bool:
        return not self._is_in_connection_cooldown()

    def _get_pytdx(self):
        """
        \u5ef6\u8fdfload pytdx \u6a21chunks

        \u53ea\u5728\u9996\u6b21\u4f7f\u7528\u65f6\u5bfc\u5165; \u907f\u514dis not installed\u65f6\u62a5\u9519
        """
        try:
            from pytdx.hq import TdxHq_API
            return TdxHq_API
        except ImportError:
            logger.warning("pytdx is not installed; please run: pip install pytdx")
            return None

    @contextmanager
    def _pytdx_session(self) -> Generator:
        """
        Pytdx \u8fde\u63a5\u4e0a\u4e0b\u6587\u7ba1\u7406\u5668

        \u786e\u4fdd:
        1. \u8fdb\u5165\u4e0a\u4e0b\u6587\u65f6\u81ea\u52a8\u8fde\u63a5
        2. \u9000\u51fa\u4e0a\u4e0b\u6587\u65f6\u81ea\u52a8\u65ad\u5f00
        3. \u5f02\u5e38\u65f6\u4e5f\u80fd\u6b63\u786e\u65ad\u5f00

        \u4f7f\u7528\u793a\u4f8b:
            with self._pytdx_session() as api:
                # \u5728\u8fd9\u91cc\u6267\u884c\u6570\u636equery
        """
        if self._is_in_connection_cooldown():
            raise DataSourceUnavailableError(
                f"Pytdx temporarily unavailable: {self._last_unavailable_reason or 'connection cooldown'}"
            )

        TdxHq_API = self._get_pytdx()
        if TdxHq_API is None:
            raise DataFetchError("pytdx library is not installed")

        api = TdxHq_API()
        connected = False

        try:
            # \u5c1d\u8bd5\u8fde\u63a5\u670d\u52a1\u5668 (\u81ea\u52a8\u9009\u62e9\u6700\u4f18)
            for i in range(len(self._hosts)):
                host_idx = (self._current_host_idx + i) % len(self._hosts)
                host, port = self._hosts[host_idx]

                try:
                    if api.connect(host, port, time_out=5):
                        connected = True
                        self._current_host_idx = host_idx
                        logger.debug(f"Pytdx \u8fde\u63a5success: {host}:{port}")
                        break
                except Exception as e:
                    logger.debug(f"Pytdx \u8fde\u63a5 {host}:{port} failed: {e}")
                    continue

            if not connected:
                self._mark_connection_cooldown("Pytdx cannot connect to any server")
                raise DataFetchError("Pytdx cannot connect to any server")

            yield api

        finally:
            # \u786e\u4fdd\u65ad\u5f00\u8fde\u63a5
            try:
                api.disconnect()
                logger.debug("Pytdx \u8fde\u63a5\u5df2\u65ad\u5f00")
            except Exception as e:
                logger.warning(f"Pytdx \u65ad\u5f00\u8fde\u63a5\u65f6\u51fa\u9519: {e}")

    def _get_market_code(self, stock_code: str) -> Tuple[int, str]:
        """
        \u6839\u636estock code\u5224\u65admarket

        Pytdx marketcode:
        - 0: \u6df1\u5733
        - 1: \u4e0a\u6d77

        Args:
            stock_code: stock code

        Returns:
            (market, code) \u5143\u7ec4
        """
        raw_code = stock_code.strip()
        upper = raw_code.upper()
        prefix, separator, suffix = raw_code.partition(".")
        if separator and prefix:
            prefix_upper = prefix.strip().upper()
            if prefix_upper in ('SH', 'SS'):
                normalized = normalize_stock_code(suffix.strip())
                if normalized.isdigit() and len(normalized) == 6:
                    return 1, normalized
            if prefix_upper == 'SZ':
                normalized = normalize_stock_code(suffix.strip())
                if normalized.isdigit() and len(normalized) == 6:
                    return 0, normalized

        code = normalize_stock_code(raw_code)

        if upper.startswith(('SH', 'SS')) or upper.endswith(('.SH', '.SS')):
            return 1, code
        if upper.startswith('SZ') or upper.endswith('.SZ'):
            return 0, code

        # \u6839\u636ecodeprefix\u5224\u65admarket
        # \u4e0a\u6d77: 60xxxx, 68xxxx (\u79d1\u521b\u677f)
        # \u6df1\u5733: 00xxxx, 30xxxx (\u521b\u4e1a\u677f), 002xxx (Medium\u5c0f\u677f)
        if code.startswith(('60', '68')):
            return 1, code  # \u4e0a\u6d77
        else:
            return 0, code  # \u6df1\u5733

    def _build_stock_list_cache(self, api) -> None:
        """
        Build a full stock code -> name cache from paginated security lists.
        """
        self._stock_list_cache = {}

        for market in (0, 1):
            start = 0
            while True:
                stocks = api.get_security_list(market, start) or []
                for stock in stocks:
                    code = stock.get('code')
                    name = stock.get('name')
                    if code and name:
                        self._stock_list_cache[code] = name

                if len(stocks) < self.SECURITY_LIST_PAGE_SIZE:
                    break

                start += self.SECURITY_LIST_PAGE_SIZE

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u4eceTongdaxin\u83b7\u53d6\u539f\u59cb\u6570\u636e

        \u4f7f\u7528 get_security_bars() \u83b7\u53d6daily data\u6570\u636e

        \u6d41\u7a0b:
        1. \u68c0check\u662f\u5426\u4e3aUS stock (does not support)
        2. \u4f7f\u7528\u4e0a\u4e0b\u6587\u7ba1\u7406\u5668\u7ba1\u7406\u8fde\u63a5
        3. \u5224\u65admarketcode
        4. \u8c03\u7528 API \u83b7\u53d6 K \u7ebf\u6570\u636e
        """
        # US stockdoes not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        if _is_us_code(stock_code):
            raise DataFetchError(f"PytdxFetcher does not supportUS stock {stock_code}; please use AkshareFetcher or YfinanceFetcher")

        # HK stockdoes not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        if _is_hk_market(stock_code):
            raise DataFetchError(f"PytdxFetcher does not supportHK stock {stock_code}; please use AkshareFetcher")

        # \u5317\u4ea4\u6240does not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        if is_bse_code(stock_code):
            raise DataFetchError(
                f"PytdxFetcher does not support\u5317\u4ea4\u6240 {stock_code}; \u5c06\u81ea\u52a8\u5207\u6362otherdata source"
            )

        market, code = self._get_market_code(stock_code)

        # \u8ba1\u7b97\u9700\u8981\u83b7\u53d6\u7684\u4ea4\u6613\u65e5count (\u4f30\u7b97)
        from datetime import datetime as dt
        start_dt = dt.strptime(start_date, '%Y-%m-%d')
        end_dt = dt.strptime(end_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days
        count = min(max(days * 5 // 7 + 10, 30), 800)  # \u4f30\u7b97\u4ea4\u6613\u65e5; \u6700\u5927 800 \u6761

        logger.debug(f"\u8c03\u7528 Pytdx get_security_bars(market={market}, code={code}, count={count})")

        with self._pytdx_session() as api:
            try:
                # \u83b7\u53d6\u65e5 K \u7ebf\u6570\u636e
                # category: 9-daily data, 0-5\u5206\u949f, 1-15\u5206\u949f, 2-30\u5206\u949f, 3-1\u5c0f\u65f6
                data = api.get_security_bars(
                    category=9,  # daily data
                    market=market,
                    code=code,
                    start=0,  # \u4ece\u6700\u65b0\u5f00\u59cb
                    count=count
                )

                if data is None or len(data) == 0:
                    raise DataFetchError(f"Pytdx found no data for {stock_code} data")

                # \u8f6c\u6362\u4e3a DataFrame
                df = api.to_df(data)

                # \u8fc7\u6ee4date\u8303\u56f4
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]

                return df

            except Exception as e:
                if isinstance(e, DataFetchError):
                    raise
                raise DataFetchError(f"Pytdx data fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        \u6807\u51c6\u5316 Pytdx \u6570\u636e

        Pytdx \u8fd4\u56de\u7684\u5217\u540d:
        datetime, open, high, low, close, vol, amount

        \u9700\u8981\u6620\u5c04\u5230\u6807\u51c6\u5217\u540d:
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # \u5217\u540d\u6620\u5c04
        column_mapping = {
            'datetime': 'date',
            'vol': 'volume',
        }

        df = df.rename(columns=column_mapping)

        # \u8ba1\u7b97change\u5e45 (pytdx \u4e0d\u8fd4\u56dechange\u5e45; \u9700\u8981\u81ea\u5df1\u8ba1\u7b97)
        if 'pct_chg' not in df.columns and 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)

        # \u6dfb\u52a0stock code\u5217
        df['code'] = stock_code

        # \u53ea\u4fdd\u7559\u9700\u8981\u7684\u5217
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        \u83b7\u53d6stock name

        Args:
            stock_code: stock code

        Returns:
            stock name; failed\u8fd4\u56de None
        """
        # HK stockdoes not support (pytdx \u4e0d\u542bHK stock\u6570\u636e)
        if _is_hk_market(stock_code):
            return None

        # \u5148\u68c0checkcache
        if stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]

        try:
            market, code = self._get_market_code(stock_code)

            with self._pytdx_session() as api:
                # \u83b7\u53d6\u80a1\u7968\u5217\u8868 (cache)
                if self._stock_list_cache is None:
                    self._build_stock_list_cache(api)

                # check\u627estock name
                name = self._stock_list_cache.get(code)
                if name:
                    self._stock_name_cache[stock_code] = name
                    return name

                # \u5c1d\u8bd5\u4f7f\u7528 get_finance_info
                finance_info = api.get_finance_info(market, code)
                if finance_info and 'name' in finance_info:
                    name = finance_info['name']
                    self._stock_name_cache[stock_code] = name
                    return name

        except Exception as e:
            logger.debug(f"Pytdx \u83b7\u53d6stock namefailed {stock_code}: {e}")

        return None

    def get_realtime_quote(self, stock_code: str) -> Optional[dict]:
        """
        \u83b7\u53d6realtime quote

        Args:
            stock_code: stock code

        Returns:
            realtime quote\u6570\u636e\u5b57\u5178; failed\u8fd4\u56de None
        """
        if is_bse_code(stock_code):
            raise DataFetchError(
                f"PytdxFetcher does not support\u5317\u4ea4\u6240 {stock_code}; \u5c06\u81ea\u52a8\u5207\u6362otherdata source"
            )
        try:
            market, code = self._get_market_code(stock_code)

            with self._pytdx_session() as api:
                data = api.get_security_quotes([(market, code)])

                if data and len(data) > 0:
                    quote = data[0]
                    return {
                        'code': stock_code,
                        'name': quote.get('name', ''),
                        'price': quote.get('price', 0),
                        'open': quote.get('open', 0),
                        'high': quote.get('high', 0),
                        'low': quote.get('low', 0),
                        'pre_close': quote.get('last_close', 0),
                        'volume': quote.get('vol', 0),
                        'amount': quote.get('amount', 0),
                        'bid_prices': [quote.get(f'bid{i}', 0) for i in range(1, 6)],
                        'ask_prices': [quote.get(f'ask{i}', 0) for i in range(1, 6)],
                    }
        except Exception as e:
            logger.warning(f"Pytdx \u83b7\u53d6realtime quotefailed {stock_code}: {e}")

        return None


if __name__ == "__main__":
    # \u6d4b\u8bd5code
    logging.basicConfig(level=logging.DEBUG)

    fetcher = PytdxFetcher()

    try:
        # \u6d4b\u8bd5history\u6570\u636e
        df = fetcher.get_daily_data('600519')  # \u8305\u53f0
        print(f"fetch succeeded; \u5171 {len(df)} \u6761\u6570\u636e")
        print(df.tail())

        # \u6d4b\u8bd5stock name
        name = fetcher.get_stock_name('600519')
        print(f"stock name: {name}")

        # \u6d4b\u8bd5realtime quote
        quote = fetcher.get_realtime_quote('600519')
        print(f"realtime quote: {quote}")

    except Exception as e:
        print(f"fetch failed: {e}")
