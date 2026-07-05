# -*- coding: utf-8 -*-
"""
===================================
TushareFetcher - \u5907\u7528data source 1 (Priority 2)
===================================

\u6570\u636esource: Tushare Pro API (\u6316\u5730\u5154)
\u7279\u70b9: \u9700\u8981 Token、\u6709request\u914d\u989dlimit
\u4f18\u70b9: \u6570\u636e\u8d28\u91cfHigh、\u63a5\u53e3\u7a33\u5b9a

\u6d41\u63a7strategy:
1. \u5b9e\u73b0"\u6bcf\u5206\u949f\u8c03\u7528\u8ba1\u6570\u5668"
2. \u8d85\u8fc7\u514d\u8d39\u914d\u989d (80\u6b21/\u5206)\u65f6; \u5f3a\u5236\u4f11\u7720\u5230\u4e0b\u4e00\u5206\u949f
3. \u4f7f\u7528 tenacity \u5b9e\u73b0index\u9000\u907f\u91cd\u8bd5
"""

import json as _json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS,is_bse_code, is_st_stock, is_kc_cy_stock, normalize_stock_code, _is_hk_market
from .realtime_types import UnifiedRealtimeQuote, ChipDistribution
from src.config import get_config
import os
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# ETF code prefixes by exchange
# Shanghai: 51xxxx, 52xxxx, 56xxxx, 58xxxx
# Shenzhen: 15xxxx, 16xxxx, 18xxxx
_ETF_SH_PREFIXES = ('51', '52', '56', '58')
_ETF_SZ_PREFIXES = ('15', '16', '18')
_ETF_ALL_PREFIXES = _ETF_SH_PREFIXES + _ETF_SZ_PREFIXES


def _is_etf_code(stock_code: str) -> bool:
    """
    Check if the code is an ETF fund code.

    ETF code ranges:
    - Shanghai ETF: 51xxxx, 52xxxx, 56xxxx, 58xxxx
    - Shenzhen ETF: 15xxxx, 16xxxx, 18xxxx
    """
    code = normalize_stock_code(stock_code)
    return code.startswith(_ETF_ALL_PREFIXES) and len(code) == 6


def _is_us_code(stock_code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3aUS stock

    US stockcode\u89c4\u5219:
    - 1-5\u4e2a\u5927\u5199\u5b57\u6bcd; \u5982 'AAPL', 'TSLA'
    - \u53ef\u80fd\u5305\u542b '.'; \u5982 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class _TushareHttpClient:
    """Lightweight Tushare Pro client that does not require the tushare SDK."""

    def __init__(self, token: str, timeout: int = 30, api_url: str = "http://api.tushare.pro") -> None:
        self._token = token
        self._timeout = timeout
        self._api_url = api_url

    def query(self, api_name: str, fields: str = "", **kwargs) -> pd.DataFrame:
        req_params = {
            "api_name": api_name,
            "token": self._token,
            "params": kwargs,
            "fields": fields,
        }
        res = requests.post(self._api_url, json=req_params, timeout=self._timeout)
        if res.status_code != 200:
            raise Exception(f"Tushare API HTTP {res.status_code}")

        result = _json.loads(res.text)
        if result.get("code") != 0:
            raise Exception(result.get("msg") or f"Tushare API error code {result.get('code')}")

        data = result.get("data") or {}
        columns = data.get("fields") or []
        items = data.get("items") or []
        return pd.DataFrame(items, columns=columns)

    def __getattr__(self, api_name: str):
        if api_name.startswith("_"):
            raise AttributeError(api_name)

        def caller(**kwargs) -> pd.DataFrame:
            return self.query(api_name, **kwargs)

        return caller


class TushareFetcher(BaseFetcher):
    """
    Tushare Pro data source\u5b9e\u73b0

    \u4f18\u5148\u7ea7: 2
    \u6570\u636esource: Tushare Pro API

    \u5173\u952estrategy:
    - \u6bcf\u5206\u949f\u8c03\u7528\u8ba1\u6570\u5668; \u9632\u6b62\u8d85\u51fa\u914d\u989d
    - \u8d85\u8fc7 80 \u6b21/\u5206\u949f\u65f6\u5f3a\u5236waiting
    - failed\u540eindex\u9000\u907f\u91cd\u8bd5

    \u914d\u989d\u8bf4\u660e (Tushare \u514d\u8d39user):
    - \u6bcf\u5206\u949f\u6700\u591a 80 \u6b21request
    - \u6bcf\u5929\u6700\u591a 500 \u6b21request
    """

    name = "TushareFetcher"
    priority = int(os.getenv("TUSHARE_PRIORITY", "2"))  # default\u4f18\u5148\u7ea7; \u4f1a\u5728 __init__ Medium\u6839\u636econfig\u52a8\u6001\u8c03\u6574

    def __init__(self, rate_limit_per_minute: int = 80):
        """
        \u521d\u59cb\u5316 TushareFetcher

        Args:
            rate_limit_per_minute: \u6bcf\u5206\u949f\u6700\u5927request\u6570 (default80; Tushare\u514d\u8d39\u914d\u989d)
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self._call_count = 0  # \u5f53\u524d\u5206\u949f\u5185\u7684\u8c03\u7528\u6b21\u6570
        self._minute_start: Optional[float] = None  # \u5f53\u524d\u8ba1\u6570\u5468\u671f\u5f00\u59cb\u65f6\u95f4
        self._api: Optional[object] = None  # Tushare API \u5b9e\u4f8b
        self.date_list: Optional[List[str]] = None  # \u4ea4\u6613\u65e5\u5217\u8868cache (\u5012\u5e8f; \u6700\u65b0date\u5728\u524d)
        self._date_list_end: Optional[str] = None  # cache\u5bf9\u5e94\u7684\u622a\u6b62date; \u7528\u4e8e\u8de8\u65e5\u5237\u65b0

        # \u5c1d\u8bd5\u521d\u59cb\u5316 API
        self._init_api()

        # \u6839\u636e API \u521d\u59cb\u5316result\u52a8\u6001\u8c03\u6574\u4f18\u5148\u7ea7
        self.priority = self._determine_priority()

    def _init_api(self) -> None:
        """
        \u521d\u59cb\u5316 Tushare API

        \u5982\u679c Token not configured; \u6b64data source\u5c06unavailable.
        \u8fd9\u91cc\u76f4\u63a5\u4f7f\u7528\u5185\u7f6e HTTP client; \u907f\u514d\u8fd0\u884c\u65f6\u5f3a\u4f9d\u8d56 tushare SDK;
        \u4ece\u800c\u51cf\u5c11 Docker / PyInstaller / \u591a\u865a\u62df\u73af\u5883\u573a\u666f\u4e0b\u56e0\u7f3a\u5305\u5bfc\u81f4\u7684initialization failed.
        """
        config = get_config()

        if not config.tushare_token:
            logger.warning("Tushare Token not configured; \u6b64data sourceunavailable")
            return

        try:
            self._api = self._build_api_client(config.tushare_token)
            logger.info("Tushare API initialization succeeded")
        except Exception as e:
            logger.error(f"Tushare API initialization failed: {e}")
            self._api = None

    def _build_api_client(self, token: str) -> _TushareHttpClient:
        """
        Build a lightweight Tushare Pro client over direct HTTP requests.

        The project already normalizes all Pro calls through the same request
        contract, so we do not need the official tushare SDK during runtime.
        """
        client = _TushareHttpClient(token=token)
        logger.debug("Tushare API client configured for direct HTTP calls")
        return client

    def _determine_priority(self) -> int:
        """
        \u6839\u636e Token config\u548c API \u521d\u59cb\u5316status\u786e\u5b9a\u4f18\u5148\u7ea7

        strategy:
        - Token config\u4e14 API initialization succeeded: \u4f18\u5148\u7ea7 -1 (\u7edd\u5bf9\u6700High; \u4f18\u4e8e efinance)
        - other\u60c5\u51b5: \u4f18\u5148\u7ea7 2 (default)

        Returns:
            \u4f18\u5148\u7ea7\u6570\u5b57 (0=\u6700High; \u6570\u5b57\u8d8a\u5927\u4f18\u5148\u7ea7\u8d8aLow)
        """
        config = get_config()

        if config.tushare_token and self._api is not None:
            # Token config\u4e14 API initialization succeeded; \u63d0\u5347\u4e3a\u6700High\u4f18\u5148\u7ea7
            logger.info("✅ \u68c0\u6d4b\u5230 TUSHARE_TOKEN \u4e14 API initialization succeeded; Tushare data source\u4f18\u5148\u7ea7\u63d0\u5347\u4e3a\u6700High (Priority -1)")
            return -1

        # Token not configuredor API initialization failed; \u4fdd\u6301default\u4f18\u5148\u7ea7
        return 2

    def is_available(self) -> bool:
        """
        \u68c0checkdata source\u662f\u5426\u53ef\u7528

        Returns:
            True \u8868\u793a\u53ef\u7528; False \u8868\u793aunavailable
        """
        return self._api is not None

    def _check_rate_limit(self) -> None:
        """
        \u68c0check\u5e76\u6267\u884c\u901f\u7387limit

        \u6d41\u63a7strategy:
        1. \u68c0check\u662f\u5426\u8fdb\u5165\u65b0\u7684\u4e00\u5206\u949f
        2. \u5982\u679c\u662f; \u91cd\u7f6e\u8ba1\u6570\u5668
        3. \u5982\u679c\u5f53\u524d\u5206\u949f\u8c03\u7528\u6b21\u6570\u8d85\u8fc7limit; \u5f3a\u5236\u4f11\u7720
        """
        current_time = time.time()

        # \u68c0check\u662f\u5426\u9700\u8981\u91cd\u7f6e\u8ba1\u6570\u5668 (\u65b0\u7684\u4e00\u5206\u949f)
        if self._minute_start is None:
            self._minute_start = current_time
            self._call_count = 0
        elif current_time - self._minute_start >= 60:
            # \u5df2\u7ecf\u8fc7\u4e86\u4e00\u5206\u949f; \u91cd\u7f6e\u8ba1\u6570\u5668
            self._minute_start = current_time
            self._call_count = 0
            logger.debug("\u901f\u7387limit\u8ba1\u6570\u5668\u5df2\u91cd\u7f6e")

        # \u68c0check\u662f\u5426\u8d85\u8fc7\u914d\u989d
        if self._call_count >= self.rate_limit_per_minute:
            # \u8ba1\u7b97\u9700\u8981waiting\u7684\u65f6\u95f4 (\u5230\u4e0b\u4e00\u5206\u949f)
            elapsed = current_time - self._minute_start
            sleep_time = max(0, 60 - elapsed) + 1  # +1 \u79d2\u7f13\u51b2

            logger.warning(
                f"Tushare \u8fbe\u5230\u901f\u7387limit ({self._call_count}/{self.rate_limit_per_minute} \u6b21/\u5206\u949f); "
                f"waiting {sleep_time:.1f} \u79d2..."
            )

            time.sleep(sleep_time)

            # \u91cd\u7f6e\u8ba1\u6570\u5668
            self._minute_start = time.time()
            self._call_count = 0

        # \u589e\u52a0\u8c03\u7528\u8ba1\u6570
        self._call_count += 1
        logger.debug(f"Tushare \u5f53\u524d\u5206\u949f\u8c03\u7528\u6b21\u6570: {self._call_count}/{self.rate_limit_per_minute}")

    def _call_api_with_rate_limit(self, method_name: str, **kwargs) -> pd.DataFrame:
        """\u7edf\u4e00\u901a\u8fc7\u901f\u7387limit\u5305\u88c5 Tushare API \u8c03\u7528."""
        if self._api is None:
            raise DataFetchError("Tushare API not initialized; check token config")

        self._check_rate_limit()
        method = getattr(self._api, method_name)
        return method(**kwargs)

    def _get_china_now(self) -> datetime:
        """\u8fd4\u56de\u4e0a\u6d77\u65f6\u533a\u5f53\u524d\u65f6\u95f4; \u65b9\u4fbf\u6d4b\u8bd5\u8986\u76d6\u8de8\u65e5\u5237\u65b0\u903b\u8f91."""
        return datetime.now(ZoneInfo("Asia/Shanghai"))

    def _get_trade_dates(self, end_date: Optional[str] = None) -> List[str]:
        """\u6309\u81ea\u7136\u65e5\u5237\u65b0\u4ea4\u6613\u65e5\u5386cache; \u907f\u514d\u670d\u52a1\u8de8\u65e5\u540e\u7ee7\u7eed\u590d\u7528\u65e7\u65e5\u5386."""
        if self._api is None:
            return []

        china_now = self._get_china_now()
        requested_end_date = end_date or china_now.strftime("%Y%m%d")

        if self.date_list is not None and self._date_list_end == requested_end_date:
            return self.date_list

        start_date = (china_now - timedelta(days=20)).strftime("%Y%m%d")
        df_cal = self._call_api_with_rate_limit(
            "trade_cal",
            exchange="SSE",
            start_date=start_date,
            end_date=requested_end_date,
        )

        if df_cal is None or df_cal.empty or "cal_date" not in df_cal.columns:
            logger.warning("[Tushare] trade_cal \u8fd4\u56de\u4e3a\u7a7a; \u65e0\u6cd5\u66f4\u65b0\u4ea4\u6613\u65e5\u5386cache")
            self.date_list = []
            self._date_list_end = requested_end_date
            return self.date_list

        trade_dates = sorted(
            df_cal[df_cal["is_open"] == 1]["cal_date"].astype(str).tolist(),
            reverse=True,
        )
        self.date_list = trade_dates
        self._date_list_end = requested_end_date
        return trade_dates

    @staticmethod
    def _pick_trade_date(trade_dates: List[str], use_today: bool) -> Optional[str]:
        """\u6839\u636e\u53ef\u7528\u4ea4\u6613\u65e5\u5217\u8868\u9009\u62e9\u5f53\u5929or\u524d\u4e00\u4ea4\u6613\u65e5."""
        if not trade_dates:
            return None
        if use_today or len(trade_dates) == 1:
            return trade_dates[0]
        return trade_dates[1]

    @staticmethod
    def _detect_exchange_hint(stock_code: str) -> Optional[str]:
        """Return SH/SZ/BJ when the raw user input carries an explicit exchange hint."""
        upper = (stock_code or "").strip().upper()
        if upper.startswith(("SH", "SS")) or upper.endswith((".SH", ".SS")):
            return "SH"
        if upper.startswith("SZ") or upper.endswith(".SZ"):
            return "SZ"
        if upper.startswith("BJ") or upper.endswith(".BJ"):
            return "BJ"
        return None

    @classmethod
    def _get_legacy_realtime_symbol(cls, stock_code: str) -> str:
        """Build the legacy tushare symbol while preserving explicit SH/SZ hints."""
        code = normalize_stock_code(stock_code)
        exchange_hint = cls._detect_exchange_hint(stock_code)

        if code == '000001' and exchange_hint == 'SH':
            return 'sh000001'
        if code == '399001':
            return 'sz399001'
        if code == '399006':
            return 'sz399006'
        if code == '000300':
            return 'sh000300'
        if is_bse_code(code):
            return f"bj{code}"
        return code

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        \u8f6c\u6362 A \u80a1 / ETF / \u5317\u4ea4\u6240\u7b49\u4e3a Tushare ts_code (\u4e0d\u542bHK stock\u903b\u8f91).

        Tushare \u8981\u6c42\u7684\u683c\u5f0f\u793a\u4f8b:
        - \u6caa\u5e02\u80a1\u7968: 600519.SH
        - \u6df1\u5e02\u80a1\u7968: 000001.SZ
        - \u6caa\u5e02 ETF: 510050.SH
        - \u6df1\u5e02 ETF: 159919.SZ

        Args:
            stock_code: \u539f\u59cbcode; \u5982 '600519', '000001', '563230'

        Returns:
            Tushare \u683c\u5f0fcode; \u5982 '600519.SH', '000001.SZ'
        """
        raw_code = stock_code.strip()

        # Already has suffix.
        if '.' in raw_code:
            upper = raw_code.upper()
            code = normalize_stock_code(raw_code)
            exchange_hint = self._detect_exchange_hint(raw_code)
            if exchange_hint in ("SH", "SZ", "BJ") and code.isdigit():
                return f"{code}.{exchange_hint}"

            ts_code = upper
            if ts_code.endswith('.SS'):
                return f"{ts_code[:-3]}.SH"
            return ts_code

        if _is_us_code(raw_code):
            raise DataFetchError(f"TushareFetcher does not supportUS stock {raw_code}; please use AkshareFetcher or YfinanceFetcher")

        if _is_hk_market(raw_code):
            #raise DataFetchError(f"TushareFetcher does not supportHK stock {raw_code}; please use AkshareFetcher")
            return normalize_stock_code(raw_code)

        code = normalize_stock_code(raw_code)
        exchange_hint = self._detect_exchange_hint(raw_code)

        if exchange_hint == "SH":
            return f"{code}.SH"
        if exchange_hint == "SZ":
            return f"{code}.SZ"
        if exchange_hint == "BJ":
            return f"{code}.BJ"

        # ETF: determine exchange by prefix
        if code.startswith(_ETF_SH_PREFIXES) and len(code) == 6:
            return f"{code}.SH"
        if code.startswith(_ETF_SZ_PREFIXES) and len(code) == 6:
            return f"{code}.SZ"

        # BSE (Beijing Stock Exchange): 8xxxxx, 4xxxxx, 920xxx
        if is_bse_code(code):
            return f"{code}.BJ"

        # Regular stocks
        # Shanghai: 600xxx, 601xxx, 603xxx, 605xxx, 688xxx (STAR Market)
        # Shenzhen: 000xxx, 001xxx, 002xxx, 003xxx, 300xxx, 301xxx (ChiNext)
        if code.startswith(('600', '601', '603', '605', '688')):
            return f"{code}.SH"
        elif code.startswith(('000', '001', '002', '003', '300', '301')):
            return f"{code}.SZ"
        else:
            logger.warning(f"Unable to determine\u80a1\u7968 {code} \u7684market; default\u4f7f\u7528\u6df1\u5e02")
            return f"{code}.SZ"

    def _convert_hk_stock_code_for_tushare(self, stock_code: str) -> str:
        """
        \u5c06user\u8f93\u5165\u8f6c\u4e3a Tushare Pro \u63a5\u53e3\u6240\u9700\u7684 ts_code (\u542bHK stock nnnnn.HK).

        - \u975eHK stock: \u59d4\u6258 _convert_stock_code (A \u80a1 / ETF / \u5317\u4ea4\u6240\u7b49).
        - HK stock: \u4ece HK00700、00700、00700.HK \u7b49\u5f62\u5f0f\u5f52\u4e00\u4e3a 5 characters\u6570\u5b57 + .HK.
        """
        raw_code = stock_code.strip()
        if _is_hk_market(raw_code):
            if "." in raw_code:
                ts_code = raw_code.upper()
                if ts_code.endswith(".SS"):
                    return f"{ts_code[:-3]}.SH"
                if ts_code.endswith(".HK"):
                    return ts_code
            digits = re.sub(r"\D", "", raw_code)
            if not digits:
                raise DataFetchError(f"Unable to identifyHK stockcode {raw_code}")
            code = digits[-5:].rjust(5, "0")
            return f"{code}.HK"
        return self._convert_stock_code(stock_code)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u4ece Tushare \u83b7\u53d6\u539f\u59cb\u6570\u636e

        \u6839\u636ecode\u7c7b\u578b\u9009\u62e9\u4e0d\u540c\u63a5\u53e3:
        - \u666e\u901a\u80a1\u7968: daily()
        - ETF \u57fa\u91d1: fund_daily()

        \u6d41\u7a0b:
        1. \u68c0check API \u662f\u5426\u53ef\u7528
        2. \u68c0check\u662f\u5426\u4e3aUS stock (does not support)
        3. \u6267\u884c\u901f\u7387limit\u68c0check
        4. \u8f6c\u6362stock code\u683c\u5f0f
        5. \u6839\u636ecode\u7c7b\u578b\u9009\u62e9\u63a5\u53e3\u5e76\u8c03\u7528
        """
        if self._api is None:
            raise DataFetchError("Tushare API not initialized; check token config")

        # US stocks not supported
        if _is_us_code(stock_code):
            raise DataFetchError(f"TushareFetcher does not supportUS stock {stock_code}; please use AkshareFetcher or YfinanceFetcher")

        # Rate-limit check
        self._check_rate_limit()

        is_hk = _is_hk_market(stock_code)
         # \u5224\u65ad\u662f\u5426\u4e3a ETF / HK stock; \u4ee5\u9009\u62e9\u4e0d\u540c\u63a5\u53e3
        is_etf = _is_etf_code(stock_code)
        if is_hk:
            ts_code = self._convert_hk_stock_code_for_tushare(stock_code)
            api_name = "hk_daily"
        else:
            ts_code = self._convert_stock_code(stock_code)
            api_name = "fund_daily" if is_etf else "daily"

        # Convert date format (Tushare requires YYYYMMDD)
        ts_start = start_date.replace('-', '')
        ts_end = end_date.replace('-', '')



        logger.debug(f"\u8c03\u7528 Tushare {api_name}({ts_code}, {ts_start}, {ts_end})")

        try:
            if is_hk:
                # HK stock\u4f7f\u7528 hk_daily \u63a5\u53e3
                df = self._api.hk_daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )
            elif is_etf:
                # ETF uses fund_daily interface
                df = self._api.fund_daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )
            else:
                # Regular A-share stocks use daily interface
                df = self._api.daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )

            return df

        except Exception as e:
            error_msg = str(e).lower()

            # \u68c0\u6d4bquota exceeded
            if any(keyword in error_msg for keyword in ['quota', '\u914d\u989d', 'limit', '\u6743\u9650']):
                logger.warning(f"Tushare \u914d\u989d\u53ef\u80fd\u8d85\u9650: {e}")
                raise RateLimitError(f"Tushare quota exceeded: {e}") from e

            raise DataFetchError(f"Tushare data fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        \u6807\u51c6\u5316 Tushare \u6570\u636e

        Tushare daily / fund_daily \u8fd4\u56de\u7684\u5217\u540d:
        ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount

        \u9700\u8981\u6620\u5c04\u5230\u6807\u51c6\u5217\u540d:
        date, open, high, low, close, volume, amount, pct_chg

        \u5355characters\u7f29\u653e\u4ec5\u9002\u7528\u4e8e A \u80a1 (\u53ca ETF \u7b49\u4f7f\u7528\u540c\u4e00\u5957\u5355characters\u7684\u63a5\u53e3):
        - vol \u6309「\u624b」\u8ba1; \u4e58\u4ee5 100 \u8f6c\u4e3a「\u80a1」
        - amount \u6309「\u5343\u5143」\u8ba1; \u4e58\u4ee5 1000 \u8f6c\u4e3a「\u5143」

        HK stock hk_daily \u8fd4\u56de\u7684 vol / amount \u5df2\u662f\u53ef\u76f4\u63a5\u4f7f\u7528\u7684\u91cf\u7ea7; \u4e0d\u505a\u4e0a\u8ff0\u7f29\u653e.
        """
        df = df.copy()
        is_hk = _is_hk_market(stock_code)

        # \u5217\u540d\u6620\u5c04
        column_mapping = {
            'trade_date': 'date',
            'vol': 'volume',
            # open, high, low, close, amount, pct_chg \u5217\u540d\u76f8\u540c
        }

        df = df.rename(columns=column_mapping)

        # \u8f6c\u6362date\u683c\u5f0f (YYYYMMDD -> YYYY-MM-DD)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

        # volume / amount: \u4ec5 A \u80a1\u7c7b\u63a5\u53e3\u505a\u5355characters\u6362\u7b97 (HK stock hk_daily \u4e0d\u6362\u7b97)
        if 'volume' in df.columns and not is_hk:
            df['volume'] = df['volume'] * 100

        if 'amount' in df.columns and not is_hk:
            df['amount'] = df['amount'] * 1000

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

        \u4f7f\u7528 Tushare \u7684 stock_basic \u63a5\u53e3\u83b7\u53d6\u80a1\u7968\u57fa\u672cinfo

        Args:
            stock_code: stock code

        Returns:
            stock name; failed\u8fd4\u56de None
        """
        if self._api is None:
            logger.warning("Tushare API not initialized; \u65e0\u6cd5\u83b7\u53d6stock name")
            return None

        # \u68c0checkcache
        if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]

        # \u521d\u59cb\u5316cache
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}

        try:
            # \u901f\u7387limit\u68c0check
            self._check_rate_limit()


            # \u6839\u636emarket/\u7c7b\u578b\u9009\u62e9\u57fa\u7840info\u63a5\u53e3
            if _is_hk_market(stock_code):
                ts_code = self._convert_hk_stock_code_for_tushare(stock_code)
                # HK stock: \u4f7f\u7528 hk_basic
                df = self._api.hk_basic(
                    ts_code=ts_code,
                    fields='ts_code,name'
                )
            elif _is_etf_code(stock_code):
                ts_code = self._convert_stock_code(stock_code)
                # ETF: \u4f7f\u7528 fund_basic
                df = self._api.fund_basic(
                    ts_code=ts_code,
                    fields='ts_code,name'
                )
            else:
                ts_code = self._convert_stock_code(stock_code)
                # A \u80a1\u80a1\u7968: \u4f7f\u7528 stock_basic
                df = self._api.stock_basic(
                    ts_code=ts_code,
                    fields='ts_code,name'
                )

            if df is not None and not df.empty:
                name = df.iloc[0]['name']
                self._stock_name_cache[stock_code] = name
                logger.debug(f"Tushare \u83b7\u53d6stock namesuccess: {stock_code} -> {name}")
                return name

        except Exception as e:
            logger.warning(f"Tushare \u83b7\u53d6stock namefailed {stock_code}: {e}")

        return None

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        \u83b7\u53d6\u80a1\u7968\u5217\u8868

        \u4f7f\u7528 Tushare \u7684 stock_basic \u63a5\u53e3\u83b7\u53d6 A \u80a1\u5217\u8868 (\u4e0d\u542bHK stock).

        Returns:
            \u5305\u542b code, name, industry, area, market \u5217\u7684 DataFrame; failed\u8fd4\u56de None
        """
        if self._api is None:
            logger.warning("Tushare API not initialized; \u65e0\u6cd5\u83b7\u53d6\u80a1\u7968\u5217\u8868")
            return None

        try:
            self._check_rate_limit()

            df = self._api.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,name,industry,area,market'
            )

            if df is None or df.empty:
                return None

            df = df.copy()
            df['code'] = df['ts_code'].astype(str).str.split('.').str[0]

            if not hasattr(self, '_stock_name_cache'):
                self._stock_name_cache = {}
            for _, row in df.iterrows():
                self._stock_name_cache[row['code']] = row['name']

            logger.info(f"Tushare \u83b7\u53d6\u80a1\u7968\u5217\u8868success: {len(df)} \u6761")
            return df[['code', 'name', 'industry', 'area', 'market']]

        except Exception as e:
            logger.warning(f"Tushare \u83b7\u53d6\u80a1\u7968\u5217\u8868failed: {e}")

        return None

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        \u83b7\u53d6realtime quote

        strategy:
        1. \u4f18\u5148\u5c1d\u8bd5 Pro \u63a5\u53e3 (\u9700\u89812000\u79ef\u5206): \u6570\u636e\u5168; \u7a33\u5b9aHigh
        2. failed\u964d\u7ea7\u5230\u65e7\u7248\u63a5\u53e3: \u95e8\u69dbLow; \u6570\u636e\u8f83\u5c11

        Args:
            stock_code: stock code

        Returns:
            UnifiedRealtimeQuote \u5bf9\u8c61; failed\u8fd4\u56de None
        """
        if self._api is None:
            return None

        # HK stocks not supported by Tushare
        if _is_hk_market(stock_code):
            logger.debug(f"TushareFetcher skippingHK stockrealtime quote {stock_code}")
            return None

        normalized_code = normalize_stock_code(stock_code)

        from .realtime_types import (
            RealtimeSource,
            safe_float, safe_int
        )

        # \u901f\u7387limit\u68c0check
        self._check_rate_limit()

        # \u5c1d\u8bd5 Pro \u63a5\u53e3
        try:
            ts_code = self._convert_stock_code(stock_code)
            # \u5c1d\u8bd5\u8c03\u7528 Pro \u5b9e\u65f6\u63a5\u53e3 (\u9700\u8981\u79ef\u5206)
            df = self._api.quotation(ts_code=ts_code)

            if df is not None and not df.empty:
                row = df.iloc[0]
                logger.debug(f"Tushare Pro realtime quotefetch succeeded: {stock_code}")

                return UnifiedRealtimeQuote(
                    code=normalized_code,
                    name=str(row.get('name', '')),
                    source=RealtimeSource.TUSHARE,
                    price=safe_float(row.get('price')),
                    change_pct=safe_float(row.get('pct_chg')),  # Pro \u63a5\u53e3\u901a\u5e38\u76f4\u63a5\u8fd4\u56dechange\u5e45
                    change_amount=safe_float(row.get('change')),
                    volume=safe_int(row.get('vol')),
                    amount=safe_float(row.get('amount')),
                    high=safe_float(row.get('high')),
                    low=safe_float(row.get('low')),
                    open_price=safe_float(row.get('open')),
                    pre_close=safe_float(row.get('pre_close')),
                    turnover_rate=safe_float(row.get('turnover_ratio')), # Pro \u63a5\u53e3\u53ef\u80fd\u6709turnover
                    pe_ratio=safe_float(row.get('pe')),
                    pb_ratio=safe_float(row.get('pb')),
                    total_mv=safe_float(row.get('total_mv')),
                )
        except Exception as e:
            # \u4ec5\u8bb0\u5f55\u8c03\u8bd5log; \u4e0d\u62a5\u9519; continuing to try\u964d\u7ea7
            logger.debug(f"Tushare Pro realtime quoteunavailable (\u53ef\u80fd\u662f\u79ef\u5206\u4e0d\u8db3): {e}")

        # \u964d\u7ea7: \u5c1d\u8bd5\u65e7\u7248\u63a5\u53e3
        try:
            import tushare as ts

            symbol = self._get_legacy_realtime_symbol(stock_code)

            # \u8c03\u7528\u65e7\u7248\u5b9e\u65f6\u63a5\u53e3 (ts.get_realtime_quotes)
            df = ts.get_realtime_quotes(symbol)

            if df is None or df.empty:
                return None

            row = df.iloc[0]

            # \u8ba1\u7b97change\u5e45
            price = safe_float(row['price'])
            pre_close = safe_float(row['pre_close'])
            change_pct = 0.0
            change_amount = 0.0

            if price and pre_close and pre_close > 0:
                change_amount = price - pre_close
                change_pct = (change_amount / pre_close) * 100

            # \u6784\u5efa\u7edf\u4e00\u5bf9\u8c61
            return UnifiedRealtimeQuote(
                code=normalized_code,
                name=str(row['name']),
                source=RealtimeSource.TUSHARE,
                price=price,
                change_pct=round(change_pct, 2),
                change_amount=round(change_amount, 2),
                volume=safe_int(row['volume']) // 100,  # \u8f6c\u6362\u4e3a\u624b
                amount=safe_float(row['amount']),
                high=safe_float(row['high']),
                low=safe_float(row['low']),
                open_price=safe_float(row['open']),
                pre_close=pre_close,
            )

        except Exception as e:
            logger.warning(f"Tushare (\u65e7\u7248) \u83b7\u53d6realtime quotefailed {stock_code}: {e}")
            return None

    def get_main_indices(self, region: str = "cn") -> Optional[List[dict]]:
        """
        \u83b7\u53d6\u4e3b\u8981indexrealtime quote (Tushare Pro); \u4ec5\u652f\u6301 A \u80a1
        """
        if region != "cn":
            return None
        if self._api is None:
            return None

        from .realtime_types import safe_float

        # index\u6620\u5c04: Tusharecode -> name
        indices_map = {
            '000001.SH': '\u4e0a\u8bc1index',
            '399001.SZ': '\u6df1\u8bc1\u6210\u6307',
            '399006.SZ': '\u521b\u4e1a\u677f\u6307',
            '000688.SH': '\u79d1\u521b50',
            '000016.SH': '\u4e0a\u8bc150',
            '000300.SH': '\u6caa\u6df1300',
        }

        try:
            self._check_rate_limit()

            # Tushare index_daily \u83b7\u53d6history\u6570\u636e; \u5b9e\u65f6\u6570\u636e\u9700\u7528other\u63a5\u53e3or\u4f30\u7b97
            # \u7531\u4e8e Tushare \u514d\u8d39user\u53ef\u80fd\u65e0\u6cd5\u83b7\u53d6indexrealtime quote; \u8fd9\u91cc\u4f5c\u4e3a\u5907\u9009
            # \u4f7f\u7528 index_daily \u83b7\u53d6\u6700\u8fd1\u4ea4\u6613\u65e5\u6570\u636e

            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - pd.Timedelta(days=5)).strftime('%Y%m%d')

            results = []

            # batch\u83b7\u53d6\u6240\u6709index\u6570\u636e
            for ts_code, name in indices_map.items():
                try:
                    df = self._api.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    if df is not None and not df.empty:
                        row = df.iloc[0] # \u6700\u65b0\u4e00\u5929

                        current = safe_float(row['close'])
                        prev_close = safe_float(row['pre_close'])

                        results.append({
                            'code': ts_code.split('.')[0], # \u517c\u5bb9 sh000001 \u683c\u5f0f\u9700\u8f6c\u6362; \u8fd9\u91cc\u4fdd\u6301\u7eaf\u6570\u5b57
                            'name': name,
                            'current': current,
                            'change': safe_float(row['change']),
                            'change_pct': safe_float(row['pct_chg']),
                            'open': safe_float(row['open']),
                            'high': safe_float(row['high']),
                            'low': safe_float(row['low']),
                            'prev_close': prev_close,
                            'volume': safe_float(row['vol']),
                            'amount': safe_float(row['amount']) * 1000, # \u5343\u5143\u8f6c\u5143
                            'amplitude': 0.0 # Tushare index_daily \u4e0d\u76f4\u63a5\u8fd4\u56de\u632f\u5e45
                        })
                except Exception as e:
                    logger.debug(f"Tushare \u83b7\u53d6index {name} failed: {e}")
                    continue

            if results:
                return results
            else:
                logger.warning("[Tushare] \u672a\u83b7\u53d6\u5230index\u884c\u60c5\u6570\u636e")

        except Exception as e:
            logger.error(f"[Tushare] \u83b7\u53d6index\u884c\u60c5failed: {e}")

        return None

    def get_market_stats(self) -> Optional[dict]:
        """
        \u83b7\u53d6marketchange\u7edf\u8ba1 (Tushare Pro)
        2000\u79ef\u5206 \u6bcf\u5929\u8bbfask\u8be5\u63a5\u53e3 ts.pro_api().rt_k \u4e24\u6b21
        \u63a5\u53e3limit\u89c1: https://tushare.pro/document/1?doc_id=108
        """
        if self._api is None:
            return None

        try:
            logger.info("[Tushare] ts.pro_api() \u83b7\u53d6market\u7edf\u8ba1...")

            # \u83b7\u53d6\u5f53\u524dMedium\u56fd\u65f6\u95f4; \u5224\u65ad\u662f\u5426\u5728\u4ea4\u6613\u65f6\u95f4\u5185
            china_now = self._get_china_now()
            current_clock = china_now.strftime("%H:%M")
            current_date = china_now.strftime("%Y%m%d")

            trade_dates = self._get_trade_dates(current_date)
            if not trade_dates:
                return None

            if current_date in trade_dates:
                if current_clock < '09:30' or current_clock > '16:30':
                    use_realtime = False
                else:
                    use_realtime = True
            else:
                use_realtime = False

            # \u82e5\u5b9e\u76d8\u7684\u65f6\u5019\u4f7f\u7528 \u5219\u4f7f\u7528other\u53ef\u4ee5\u5b9e\u76d8\u83b7\u53d6\u7684data source akshare、efinance
            if use_realtime:
                try:
                    df = self._call_api_with_rate_limit("rt_k", ts_code='3*.SZ,6*.SH,0*.SZ,92*.BJ')
                    if df is not None and not df.empty:
                        return self._calc_market_stats(df)

                except Exception as e:
                    logger.error(f"[Tushare] ts.pro_api().rt_k \u5c1d\u8bd5\u83b7\u53d6\u5b9e\u65f6\u6570\u636efailed: {e}")
                    return None
            else:

                if current_date not in trade_dates:
                    last_date = self._pick_trade_date(trade_dates, use_today=True)  # \u62ff\u6700\u8fd1\u7684date
                else:
                    if current_clock < '09:30':
                        last_date = self._pick_trade_date(trade_dates, use_today=False)  # \u62ff\u53d6\u524d\u4e00\u5929data
                    else:  # \u5373 '> 16:30'
                        last_date = self._pick_trade_date(trade_dates, use_today=True)  # \u62ff\u53d6\u5f53\u5929data

                if last_date is None:
                    return None

                try:
                    df = self._call_api_with_rate_limit(
                        "daily",
                        ts_code='3*.SZ,6*.SH,0*.SZ,92*.BJ',
                        start_date=last_date,
                        end_date=last_date,
                    )
                    # \u4e3a\u9632\u6b62\u4e0d\u540c\u63a5\u53e3\u8fd4\u56de\u7684\u5217\u540d\u5927\u5c0f\u5199\u4e0d\u4e00\u81f4 (\u4f8b\u5982 rt_k \u8fd4\u56de\u5c0f\u5199; daily \u8fd4\u56de\u5927\u5199); \u7edf\u4e00\u5c06\u5217\u540d\u8f6c\u4e3a\u5c0f\u5199
                    df.columns = [col.lower() for col in df.columns]

                    # \u83b7\u53d6\u80a1\u7968\u57fa\u7840info (\u5305\u542bcode\u548cname)
                    df_basic = self._call_api_with_rate_limit("stock_basic", fields='ts_code,name')
                    df = pd.merge(df, df_basic, on='ts_code', how='left')
                    # \u5c06 daily\u7684 amount \u5217\u7684\u503c\u4e58\u4ee5 1000 \u6765\u548cotherdata source\u4fdd\u6301\u4e00\u81f4
                    if 'amount' in df.columns:
                        df['amount'] = df['amount'] * 1000

                    if df is not None and not df.empty:
                        return self._calc_market_stats(df)
                except Exception as e:
                    logger.error(f"[Tushare] ts.pro_api().daily data fetch failed: {e}")



        except Exception as e:
            logger.error(f"[Tushare] \u83b7\u53d6market\u7edf\u8ba1failed: {e}")

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

    def get_trade_time(self,early_time='09:30',late_time='16:30') -> Optional[str]:
        '''
        \u83b7\u53d6\u5f53\u524d\u65f6\u95f4\u53ef\u4ee5\u83b7\u5f97\u6570\u636e\u7684\u5f00\u59cb\u65f6\u95f4date

        Args:
                early_time: default '09:30'
                late_time: default '16:30'
                early_time-late_time \u4e4b\u95f4\u4e3a\u4f7f\u7528\u4e0a\u4e00\u4e2a\u4ea4\u6613\u65e5\u6570\u636e\u7684\u65f6\u95f4\u6bb5; other\u65f6\u95f4\u4e3a\u4f7f\u7528\u5f53\u5929\u6570\u636e\u7684\u65f6\u95f4\u6bb5
        Returns:
                start_date: \u53ef\u4ee5\u83b7\u5f97\u6570\u636e\u7684\u5f00\u59cbdate
        '''
        china_now = self._get_china_now()
        china_date = china_now.strftime("%Y%m%d")
        china_clock = china_now.strftime("%H:%M")

        trade_dates = self._get_trade_dates(china_date)
        if not trade_dates:
            return None

        if china_date in trade_dates:
            if  early_time < china_clock < late_time: # \u4f7f\u7528\u4e0a\u4e00\u4e2a\u4ea4\u6613\u65e5\u6570\u636e\u7684\u65f6\u95f4\u6bb5
                use_today = False
            else:
                use_today = True
        else:
            # \u975e\u4ea4\u6613\u65e5:  today\u4e0d\u5728trade_datesMedium; trade_dates[0]\u5c31\u662f\u6700\u8fd1\u4ea4\u6613\u65e5
            use_today = True

        start_date = self._pick_trade_date(trade_dates, use_today=use_today)
        if start_date is None:
            return None

        if not use_today:
            logger.info(f"[Tushare] \u5f53\u524d\u65f6\u95f4 {china_clock} \u53ef\u80fd\u65e0\u6cd5\u83b7\u53d6\u5f53\u5929chip distribution; \u5c1d\u8bd5\u83b7\u53d6\u524d\u4e00\u4e2a\u4ea4\u6613\u65e5data {start_date}")

        return start_date

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[list, list]]:
        """
        \u83b7\u53d6industrysectorchange\u699c (Tushare Pro)

        data source\u4f18\u5148\u7ea7:
        1. \u540c\u82b1\u987a\u63a5\u53e3 (ts.pro_api().moneyflow_ind_ths)
        2. \u4e1c\u8d22\u63a5\u53e3 (ts.pro_api().moneyflow_ind_dc)
        \u6ce8\u610f: \u6bcf\u4e2a\u63a5\u53e3\u7684industry\u5206\u7c7b\u548csector\u5b9a\u4e49\u4e0d\u540c; \u4f1a\u5bfc\u81f4result\u4e24\u8005\u4e0d\u4e00\u81f4
        """
        def _get_rank_top_n(df: pd.DataFrame, change_col: str, industry_name: str, n: int) -> Tuple[list, list]:
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])

            # \u6da8\u5e45\u524dn
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

        # 15:30\u4e4b\u540e\u624d\u6709\u5f53\u5929\u6570\u636e
        start_date = self.get_trade_time(early_time='00:00', late_time='15:30')
        if not start_date:
            return None

        # \u4f18\u5148\u540c\u82b1\u987a\u63a5\u53e3
        logger.info("[Tushare] ts.pro_api().moneyflow_ind_ths \u83b7\u53d6sector\u6392\u884c(\u540c\u82b1\u987a)...")
        try:
            df = self._call_api_with_rate_limit("moneyflow_ind_ths", trade_date=start_date)
            if df is not None and not df.empty:
                change_col = 'pct_change'
                name = 'industry'
                if change_col in df.columns:
                    return _get_rank_top_n(df, change_col, name, n)
        except Exception as e:
            logger.warning(f"[Tushare] \u83b7\u53d6\u540c\u82b1\u987aindustrysectorchange\u699cfailed: {e} \u5c1d\u8bd5\u4e1c\u8d22\u63a5\u53e3")

        # \u540c\u82b1\u987a\u63a5\u53e3failed; \u964d\u7ea7\u5c1d\u8bd5\u4e1c\u8d22\u63a5\u53e3
        logger.info("[Tushare] ts.pro_api().moneyflow_ind_dc \u83b7\u53d6sector\u6392\u884c(\u4e1c\u8d22)...")
        try:
            df = self._call_api_with_rate_limit("moneyflow_ind_dc", trade_date=start_date)
            if df is not None and not df.empty:
                df = df[df['content_type'] == 'industry']  # \u8fc7\u6ee4\u51faindustrysector
                change_col = 'pct_change'
                name = 'name'
                if change_col in df.columns:
                    return _get_rank_top_n(df, change_col, name, n)
        except Exception as e:
            logger.warning(f"[Tushare] \u83b7\u53d6\u4e1c\u8d22industrysectorchange\u699cfailed: {e}")
            return None

        # \u83b7\u53d6\u4e3a\u7a7aor\u8005\u63a5\u53e3\u8c03\u7528failed; \u8fd4\u56de None
        return None




    def get_chip_distribution(self, stock_code: str) -> Optional[ChipDistribution]:
        """
        \u83b7\u53d6chip distribution\u6570\u636e

        \u6570\u636esource: ts.pro_api().cyq_chips()
        \u5305\u542b: \u83b7\u5229\u6bd4\u4f8b、\u5e73\u5747\u6210\u672c、\u7b79\u7801\u96c6Medium\u5ea6

        \u6ce8\u610f: ETF/index\u6ca1\u6709chip distribution\u6570\u636e; \u4f1a\u76f4\u63a5\u8fd4\u56de None；HK stockdoes not support; \u76f4\u63a5\u8fd4\u56de None.
        5000\u79ef\u5206\u4ee5\u4e0b\u6bcf\u5929\u8bbfask15\u6b21,\u6bcf\u5c0f\u65f6\u8bbfask5\u6b21

        Args:
            stock_code: stock code

        Returns:
            ChipDistribution \u5bf9\u8c61 (\u6700\u65b0\u4ea4\u6613\u65e5data); fetch failed\u8fd4\u56de None

        """
        if _is_us_code(stock_code):
            logger.warning(f"[Tushare] TushareFetcher does not supportUS stock {stock_code} \u7684chip distribution")
            return None

        if _is_etf_code(stock_code):
            logger.warning(f"[Tushare] TushareFetcher does not support ETF {stock_code} \u7684chip distribution")
            return None

        if _is_hk_market(stock_code):
            logger.warning(f"[Tushare] TushareFetcher does not supportHK stock {stock_code} \u7684chip distribution")
            return None

        try:
            # 19\u70b9\u4e4b\u540e\u624d\u6709\u5f53\u5929\u6570\u636e
            start_date = self.get_trade_time(early_time='00:00', late_time='19:00')
            if not start_date:
                return None

            ts_code = self._convert_stock_code(stock_code)

            df = self._call_api_with_rate_limit(
                "cyq_chips",
                ts_code=ts_code,
                start_date=start_date,
                end_date=start_date,
            )
            if df is not None and not df.empty:
                daily_df = self._call_api_with_rate_limit(
                    "daily",
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=start_date,
                )
                if daily_df is None or daily_df.empty:
                    return None
                current_price = daily_df.iloc[0]['close']
                metrics = self.compute_cyq_metrics(df, current_price)

                chip = ChipDistribution(
                    code=stock_code,
                    date=datetime.strptime(start_date, '%Y%m%d').strftime('%Y-%m-%d'),
                    profit_ratio=metrics['\u83b7\u5229\u6bd4\u4f8b'],
                    avg_cost=metrics['\u5e73\u5747\u6210\u672c'],
                    cost_90_low=metrics['90\u6210\u672c-Low'],
                    cost_90_high=metrics['90\u6210\u672c-High'],
                    concentration_90=metrics['90\u96c6Medium\u5ea6'],
                    cost_70_low=metrics['70\u6210\u672c-Low'],
                    cost_70_high=metrics['70\u6210\u672c-High'],
                    concentration_70=metrics['70\u96c6Medium\u5ea6'],
                )

                logger.info(f"[chip distribution] {stock_code} date={chip.date}: \u83b7\u5229\u6bd4\u4f8b={chip.profit_ratio:.1%}, "
                        f"\u5e73\u5747\u6210\u672c={chip.avg_cost}, 90%\u96c6Medium\u5ea6={chip.concentration_90:.2%}, "
                        f"70%\u96c6Medium\u5ea6={chip.concentration_70:.2%}")
                return chip

        except Exception as e:
            logger.warning(f"[Tushare] \u83b7\u53d6chip distributionfailed {stock_code}: {e}")
            return None

    def compute_cyq_metrics(self, df: pd.DataFrame, current_price: float) -> dict:
        """
        \u57fa\u4e8e Tushare \u7684chip distribution\u660e\u7ec6\u8868 (cyq_chips) \u8ba1\u7b97\u5e38\u7528\u7b79\u7801\u6307\u6807
        :param df: \u5305\u542b 'price' \u548c 'percent' \u5217\u7684 DataFrame
        :param current_price: \u80a1\u7968\u5f53\u5929\u7684\u5f53\u524d\u4ef7/\u6536\u76d8\u4ef7 (\u7528\u4e8e\u8ba1\u7b97\u83b7\u5229\u6bd4\u4f8b)
        :return: \u5305\u542b\u5404\u9879\u7b79\u7801\u6307\u6807\u7684\u5b57\u5178
        """
        import numpy as np
        # 1. \u786e\u4fdd\u6309price\u4ece\u5c0f\u5230\u5927\u6392\u5e8f (Tushare \u8fd4\u56dedata\u5f80\u5f80\u662f\u7eaf\u5012\u5e8f\u7684)
        df_sorted = df.sort_values(by='price', ascending=True).reset_index(drop=True)

        # 2. \u9632\u6b62\u539f\u59cb\u6570\u636e percent \u603b\u548c\u4ea7\u751f\u6d6e\u70b9\u6570\u8bef\u5dee; \u5f52\u4e00\u5316\u5230 100%
        total_percent = df_sorted['percent'].sum()

        df_sorted['norm_percent'] = df_sorted['percent'] / total_percent * 100

        # 3. \u8ba1\u7b97\u7b79\u7801\u7684\u7d2f\u79ef\u5206\u5e03
        df_sorted['cumsum'] = df_sorted['norm_percent'].cumsum()

        # --- \u83b7\u5229\u6bd4\u4f8b ---
        # \u6240\u6709price <= \u5f53\u524d\u4ef7\u7684\u7b79\u7801\u4e4b\u548c
        winner_rate = df_sorted[df_sorted['price'] <= current_price]['norm_percent'].sum()

        # --- \u5e73\u5747\u6210\u672c ---
        # price\u7684\u52a0\u6743\u5e73\u5747\u503c
        avg_cost = np.average(df_sorted['price'], weights=df_sorted['norm_percent'])

        # --- \u8f85\u52a9\u51fd\u6570: \u6c42\u6307\u5b9a\u7d2f\u79ef\u6bd4\u4f8b\u5904\u7684price ---
        def get_percentile_price(target_pct):
            # \u5bfb\u627e\u7d2f\u79ef\u6c42\u548c\u7b2c\u4e00\u6b21\u5927\u4e8e\u7b49\u4e8e\u76ee\u6807\u767e\u5206\u6bd4\u7684\u884c\u7d22\u5f15
            idx = df_sorted['cumsum'].searchsorted(target_pct)
            idx = min(idx, len(df_sorted) - 1) # \u9632\u6b62\u8d8a\u754c
            return df_sorted.loc[idx, 'price']

        # --- 90% \u6210\u672c\u533a\u4e0e\u96c6Medium\u5ea6 ---
        # \u53bb\u5934\u53bb\u5c3e\u5404 5%
        cost_90_low = get_percentile_price(5)
        cost_90_high = get_percentile_price(95)
        if (cost_90_high + cost_90_low) != 0:
            concentration_90 = (cost_90_high - cost_90_low) / (cost_90_high + cost_90_low) * 100
        else:
            concentration_90 = 0.0

        # --- 70% \u6210\u672c\u533a\u4e0e\u96c6Medium\u5ea6 ---
        # \u53bb\u5934\u53bb\u5c3e\u5404 15%
        cost_70_low = get_percentile_price(15)
        cost_70_high = get_percentile_price(85)
        if (cost_70_high + cost_70_low) != 0:
            concentration_70 = (cost_70_high - cost_70_low) / (cost_70_high + cost_70_low) * 100
        else:
            concentration_70 = 0.0

        # \u8fd4\u56de\u683c\u5f0f\u5316result
        return {
            "\u83b7\u5229\u6bd4\u4f8b": round(winner_rate/100, 4), # /100 \u4e0eakshare\u4fdd\u6301\u4e00\u81f4; \u8fd4\u56de\u5c0f\u6570\u683c\u5f0f
            "\u5e73\u5747\u6210\u672c": round(avg_cost, 4),
            "90\u6210\u672c-Low": round(cost_90_low, 4),
            "90\u6210\u672c-High": round(cost_90_high, 4),
            "90\u96c6Medium\u5ea6": round(concentration_90/100, 4),
            "70\u6210\u672c-Low": round(cost_70_low, 4),
            "70\u6210\u672c-High": round(cost_70_high, 4),
            "70\u96c6Medium\u5ea6": round(concentration_70/100, 4)
        }



if __name__ == "__main__":
    # \u6d4b\u8bd5code
    logging.basicConfig(level=logging.DEBUG)

    fetcher = TushareFetcher()

    try:
        # \u6d4b\u8bd5history\u6570\u636e
        df = fetcher.get_daily_data('600519')  # \u8305\u53f0
        print(f"fetch succeeded; \u5171 {len(df)} \u6761\u6570\u636e")
        print(df.tail())

        # \u6d4b\u8bd5stock name
        name = fetcher.get_stock_name('600519')
        print(f"stock name: {name}")

    except Exception as e:
        print(f"fetch failed: {e}")

    # \u6d4b\u8bd5market\u7edf\u8ba1
    print("\n" + "=" * 50)
    print("Testing get_market_stats (tushare)")
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


    # \u6d4b\u8bd5chip distribution\u6570\u636e
    print("\n" + "=" * 50)
    print("\u6d4b\u8bd5chip distribution\u6570\u636e\u83b7\u53d6")
    print("=" * 50)
    try:
        chip = fetcher.get_chip_distribution('600519')  # \u8305\u53f0
    except Exception as e:
        print(f"[chip distribution] fetch failed: {e}")

    # \u6d4b\u8bd5industrysector\u6392\u540d
    print("\n" + "=" * 50)
    print("\u6d4b\u8bd5industrysector\u6392\u540d\u83b7\u53d6")
    print("=" * 50)
    try:
        rankings = fetcher.get_sector_rankings(n=5)
        if rankings:
            top, bottom = rankings
            print("\u6da8\u5e45\u699c Top 5:")
            for sector in top:
                print(f"{sector['name']}: {sector['change_pct']}%")
            print("\n\u8dcc\u5e45\u699c Top 5:")
            for sector in bottom:
                print(f"{sector['name']}: {sector['change_pct']}%")
        else:
            print("\u672a\u83b7\u53d6\u5230industrysector\u6392\u540d\u6570\u636e")
    except Exception as e:
        print(f"[industrysector\u6392\u540d] fetch failed: {e}")
