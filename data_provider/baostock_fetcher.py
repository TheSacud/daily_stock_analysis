# -*- coding: utf-8 -*-
"""
===================================
BaostockFetcher - \u5907\u7528data source 2 (Priority 3)
===================================

\u6570\u636esource: \u8bc1\u5238\u5b9d (Baostock)
\u7279\u70b9: \u514d\u8d39、\u65e0\u9700 Token、\u9700\u8981\u767b\u5f55\u7ba1\u7406
\u4f18\u70b9: \u7a33\u5b9a、\u65e0\u914d\u989dlimit

\u5173\u952estrategy:
1. \u7ba1\u7406 bs.login() \u548c bs.logout() \u751f\u547d\u5468\u671f
2. \u4f7f\u7528\u4e0a\u4e0b\u6587\u7ba1\u7406\u5668\u9632\u6b62\u8fde\u63a5\u6cc4\u9732
3. failed\u540eindex\u9000\u907f\u91cd\u8bd5
"""

import logging
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Generator

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
    STANDARD_COLUMNS,
    is_bse_code,
    normalize_stock_code,
    _is_hk_market,
)
import os

logger = logging.getLogger(__name__)


def _is_us_code(stock_code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3aUS stock

    US stockcode\u89c4\u5219:
    - 1-5\u4e2a\u5927\u5199\u5b57\u6bcd; \u5982 'AAPL', 'TSLA'
    - \u53ef\u80fd\u5305\u542b '.'; \u5982 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class BaostockFetcher(BaseFetcher):
    """
    Baostock data source\u5b9e\u73b0

    \u4f18\u5148\u7ea7: 3
    \u6570\u636esource: \u8bc1\u5238\u5b9d Baostock API

    \u5173\u952estrategy:
    - \u4f7f\u7528\u4e0a\u4e0b\u6587\u7ba1\u7406\u5668\u7ba1\u7406\u8fde\u63a5\u751f\u547d\u5468\u671f
    - \u6bcf\u6b21request\u90fd\u91cd\u65b0\u767b\u5f55/\u767b\u51fa; \u9632\u6b62\u8fde\u63a5\u6cc4\u9732
    - failed\u540eindex\u9000\u907f\u91cd\u8bd5

    Baostock \u7279\u70b9:
    - \u514d\u8d39、\u65e0\u9700\u6ce8\u518c
    - \u9700\u8981\u663e\u5f0f\u767b\u5f55/\u767b\u51fa
    - \u6570\u636e\u66f4\u65b0\u7565\u6709\u5ef6\u8fdf (T+1)
    """

    name = "BaostockFetcher"
    priority = int(os.getenv("BAOSTOCK_PRIORITY", "3"))

    def __init__(self):
        """\u521d\u59cb\u5316 BaostockFetcher"""
        self._bs_module = None

    def _get_baostock(self):
        """
        \u5ef6\u8fdfload baostock \u6a21chunks

        \u53ea\u5728\u9996\u6b21\u4f7f\u7528\u65f6\u5bfc\u5165; \u907f\u514dis not installed\u65f6\u62a5\u9519
        """
        if self._bs_module is None:
            import baostock as bs
            self._bs_module = bs
        return self._bs_module

    @contextmanager
    def _baostock_session(self) -> Generator:
        """
        Baostock \u8fde\u63a5\u4e0a\u4e0b\u6587\u7ba1\u7406\u5668

        \u786e\u4fdd:
        1. \u8fdb\u5165\u4e0a\u4e0b\u6587\u65f6\u81ea\u52a8\u767b\u5f55
        2. \u9000\u51fa\u4e0a\u4e0b\u6587\u65f6\u81ea\u52a8\u767b\u51fa
        3. \u5f02\u5e38\u65f6\u4e5f\u80fd\u6b63\u786e\u767b\u51fa

        \u4f7f\u7528\u793a\u4f8b:
            with self._baostock_session():
                # \u5728\u8fd9\u91cc\u6267\u884c\u6570\u636equery
        """
        bs = self._get_baostock()
        login_result = None

        try:
            # \u767b\u5f55 Baostock
            login_result = bs.login()

            if login_result.error_code != '0':
                raise DataFetchError(f"Baostock login failed: {login_result.error_msg}")

            logger.debug("Baostock login succeeded")

            yield bs

        finally:
            # \u786e\u4fdd\u767b\u51fa; \u9632\u6b62\u8fde\u63a5\u6cc4\u9732
            try:
                logout_result = bs.logout()
                if logout_result.error_code == '0':
                    logger.debug("Baostock logout succeeded")
                else:
                    logger.warning(f"Baostock logout exception: {logout_result.error_msg}")
            except Exception as e:
                logger.warning(f"Baostock error during logout: {e}")

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        \u8f6c\u6362stock code\u4e3a Baostock \u683c\u5f0f

        Baostock \u8981\u6c42\u7684\u683c\u5f0f:
        - \u6caa\u5e02: sh.600519
        - \u6df1\u5e02: sz.000001

        Args:
            stock_code: \u539f\u59cbcode; \u5982 '600519', '000001'

        Returns:
            Baostock \u683c\u5f0fcode; \u5982 'sh.600519', 'sz.000001'
        """
        raw_code = stock_code.strip()
        upper = raw_code.upper()

        # HK stocks are not supported by Baostock
        if _is_hk_market(raw_code):
            raise DataFetchError(f"BaostockFetcher does not supportHK stock {raw_code}; please use AkshareFetcher")

        # \u4fdd\u7559\u65e2\u6709\u5c0f\u5199 baostock \u683c\u5f0f\u8f93\u5165\u7684\u5185\u90e8\u5bb9\u9519; \u4f46userconfig\u4ecd\u63a8\u8350 6 characters\u88f8code.
        if raw_code.startswith(('sh.', 'sz.')):
            return raw_code.lower()

        exchange_hint = None
        if upper.startswith(('SH', 'SS')) or upper.endswith(('.SH', '.SS')):
            exchange_hint = 'sh'
        elif upper.startswith('SZ') or upper.endswith('.SZ'):
            exchange_hint = 'sz'

        code = normalize_stock_code(raw_code)

        if exchange_hint in ('sh', 'sz') and code.isdigit() and len(code) == 6:
            return f"{exchange_hint}.{code}"

        # ETF: Shanghai ETF (51xx, 52xx, 56xx, 58xx) -> sh; Shenzhen ETF (15xx, 16xx, 18xx) -> sz
        if len(code) == 6:
            if code.startswith(('51', '52', '56', '58')):
                return f"sh.{code}"
            if code.startswith(('15', '16', '18')):
                return f"sz.{code}"

        # \u6839\u636ecodeprefix\u5224\u65admarket
        if code.startswith(('600', '601', '603', '605', '688')):
            return f"sh.{code}"
        elif code.startswith(('000', '001', '002', '003', '300', '301')):
            return f"sz.{code}"
        else:
            logger.warning(f"Unable to determine\u80a1\u7968 {code} \u7684market; default\u4f7f\u7528\u6df1\u5e02")
            return f"sz.{code}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        \u4ece Baostock \u83b7\u53d6\u539f\u59cb\u6570\u636e

        \u4f7f\u7528 query_history_k_data_plus() \u83b7\u53d6daily data\u6570\u636e

        \u6d41\u7a0b:
        1. \u68c0check\u662f\u5426\u4e3aUS stock (does not support)
        2. \u4f7f\u7528\u4e0a\u4e0b\u6587\u7ba1\u7406\u5668\u7ba1\u7406\u8fde\u63a5
        3. \u8f6c\u6362stock code\u683c\u5f0f
        4. \u8c03\u7528 API query\u6570\u636e
        5. \u5c06result\u8f6c\u6362\u4e3a DataFrame
        """
        # US stockdoes not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        if _is_us_code(stock_code):
            raise DataFetchError(f"BaostockFetcher does not supportUS stock {stock_code}; please use AkshareFetcher or YfinanceFetcher")

        # HK stockdoes not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        if _is_hk_market(stock_code):
            raise DataFetchError(f"BaostockFetcher does not supportHK stock {stock_code}; please use AkshareFetcher")

        # \u5317\u4ea4\u6240does not support; \u629b\u51fa\u5f02\u5e38\u8ba9 DataFetcherManager \u5207\u6362\u5230otherdata source
        if is_bse_code(stock_code):
            raise DataFetchError(
                f"BaostockFetcher does not support\u5317\u4ea4\u6240 {stock_code}; \u5c06\u81ea\u52a8\u5207\u6362otherdata source"
            )

        # \u8f6c\u6362code\u683c\u5f0f
        bs_code = self._convert_stock_code(stock_code)

        logger.debug(f"\u8c03\u7528 Baostock query_history_k_data_plus({bs_code}, {start_date}, {end_date})")

        with self._baostock_session() as bs:
            try:
                # querydaily data\u6570\u636e
                # adjustflag: 1-\u540e\u590d\u6743; 2-\u524d\u590d\u6743; 3-\u4e0d\u590d\u6743
                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,open,high,low,close,volume,amount,pctChg",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",  # daily data
                    adjustflag="2"  # \u524d\u590d\u6743
                )

                if rs.error_code != '0':
                    raise DataFetchError(f"Baostock query failed: {rs.error_msg}")

                # \u8f6c\u6362\u4e3a DataFrame
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())

                if not data_list:
                    raise DataFetchError(f"Baostock found no data for {stock_code} data")

                df = pd.DataFrame(data_list, columns=rs.fields)

                return df

            except Exception as e:
                if isinstance(e, DataFetchError):
                    raise
                raise DataFetchError(f"Baostock data fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        \u6807\u51c6\u5316 Baostock \u6570\u636e

        Baostock \u8fd4\u56de\u7684\u5217\u540d:
        date, open, high, low, close, volume, amount, pctChg

        \u9700\u8981\u6620\u5c04\u5230\u6807\u51c6\u5217\u540d:
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # \u5217\u540d\u6620\u5c04 (\u53ea\u9700\u8981\u5904\u7406 pctChg)
        column_mapping = {
            'pctChg': 'pct_chg',
        }

        df = df.rename(columns=column_mapping)

        # \u6570\u503c\u7c7b\u578b\u8f6c\u6362 (Baostock \u8fd4\u56de\u7684\u90fd\u662f\u5b57\u7b26\u4e32)
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

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

        \u4f7f\u7528 Baostock \u7684 query_stock_basic \u63a5\u53e3\u83b7\u53d6\u80a1\u7968\u57fa\u672cinfo

        Args:
            stock_code: stock code

        Returns:
            stock name; failed\u8fd4\u56de None
        """
        # \u68c0checkcache
        if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]

        # \u521d\u59cb\u5316cache
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}

        try:
            bs_code = self._convert_stock_code(stock_code)

            with self._baostock_session() as bs:
                # query\u80a1\u7968\u57fa\u672cinfo
                rs = bs.query_stock_basic(code=bs_code)

                if rs.error_code == '0':
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())

                    if data_list:
                        # Baostock \u8fd4\u56de\u7684\u5b57\u6bb5: code, code_name, ipoDate, outDate, type, status
                        fields = rs.fields
                        name_idx = fields.index('code_name') if 'code_name' in fields else None
                        if name_idx is not None and len(data_list[0]) > name_idx:
                            name = data_list[0][name_idx]
                            self._stock_name_cache[stock_code] = name
                            logger.debug(f"Baostock \u83b7\u53d6stock namesuccess: {stock_code} -> {name}")
                            return name

        except Exception as e:
            logger.warning(f"Baostock \u83b7\u53d6stock namefailed {stock_code}: {e}")

        return None

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        \u83b7\u53d6\u80a1\u7968\u5217\u8868

        \u4f7f\u7528 Baostock \u7684 query_stock_basic \u63a5\u53e3\u83b7\u53d6all\u80a1\u7968\u5217\u8868

        Returns:
            \u5305\u542b code, name \u5217\u7684 DataFrame; failed\u8fd4\u56de None
        """
        try:
            with self._baostock_session() as bs:
                # query\u6240\u6709\u80a1\u7968\u57fa\u672cinfo
                rs = bs.query_stock_basic()

                if rs.error_code == '0':
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())

                    if data_list:
                        df = pd.DataFrame(data_list, columns=rs.fields)

                        # \u8f6c\u6362code\u683c\u5f0f (\u53bb\u9664 sh. or sz. prefix)
                        df['code'] = df['code'].apply(lambda x: x.split('.')[1] if '.' in x else x)
                        df = df.rename(columns={'code_name': 'name'})

                        # \u66f4\u65b0cache
                        if not hasattr(self, '_stock_name_cache'):
                            self._stock_name_cache = {}
                        for _, row in df.iterrows():
                            self._stock_name_cache[row['code']] = row['name']

                        logger.info(f"Baostock \u83b7\u53d6\u80a1\u7968\u5217\u8868success: {len(df)} \u6761")
                        return df[['code', 'name']]

        except Exception as e:
            logger.warning(f"Baostock \u83b7\u53d6\u80a1\u7968\u5217\u8868failed: {e}")

        return None


if __name__ == "__main__":
    # \u6d4b\u8bd5code
    logging.basicConfig(level=logging.DEBUG)

    fetcher = BaostockFetcher()

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
