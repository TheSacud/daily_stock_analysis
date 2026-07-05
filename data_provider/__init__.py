# -*- coding: utf-8 -*-
"""
===================================
data sourcestrategy\u5c42 - \u5305\u521d\u59cb\u5316
===================================

\u672c\u5305\u5b9e\u73b0strategymode\u7ba1\u7406\u591a\u4e2adata source; \u5b9e\u73b0:
1. \u7edf\u4e00data\u83b7\u53d6\u63a5\u53e3
2. \u81ea\u52a8\u6545\u969c\u5207\u6362
3. \u9632\u5c01\u7981\u6d41\u63a7strategy

data source\u4f18\u5148\u7ea7 (\u52a8\u6001\u8c03\u6574):
【config\u4e86 TUSHARE_TOKEN \u65f6】
1. TushareFetcher (Priority 0) - 🔥 \u6700High\u4f18\u5148\u7ea7 (\u52a8\u6001\u63d0\u5347)
2. EfinanceFetcher (Priority 0) - \u540c\u4f18\u5148\u7ea7
3. AkshareFetcher (Priority 1) - \u6765\u81ea akshare library
4. PytdxFetcher (Priority 2) - \u6765\u81ea pytdx library (Tongdaxin)
5. BaostockFetcher (Priority 3) - \u6765\u81ea baostock library
6. YfinanceFetcher (Priority 4) - \u6765\u81ea yfinance library

【not configured TUSHARE_TOKEN \u65f6】
1. EfinanceFetcher (Priority 0) - \u6700High\u4f18\u5148\u7ea7; \u6765\u81ea efinance library
2. AkshareFetcher (Priority 1) - \u6765\u81ea akshare library
3. PytdxFetcher (Priority 2) - \u6765\u81ea pytdx library (Tongdaxin)
4. TushareFetcher (Priority 2) - \u6765\u81ea tushare library (unavailable)
5. BaostockFetcher (Priority 3) - \u6765\u81ea baostock library
6. YfinanceFetcher (Priority 4) - \u6765\u81ea yfinance library
7. LongbridgeFetcher (Priority 5) - Longbridge OpenAPI (US stock/HK stock\u515c\u5e95)

\u63d0\u793a: \u4f18\u5148\u7ea7\u6570\u5b57\u8d8a\u5c0f\u8d8a\u4f18\u5148; \u540c\u4f18\u5148\u7ea7\u6309\u521d\u59cb\u5316\u987a\u5e8f\u6392\u5217
"""

from .base import BaseFetcher, DataFetcherManager
from .efinance_fetcher import EfinanceFetcher
from .tencent_fetcher import TencentFetcher
from .akshare_fetcher import AkshareFetcher, is_hk_stock_code
from .tushare_fetcher import TushareFetcher
from .pytdx_fetcher import PytdxFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher
from .longbridge_fetcher import LongbridgeFetcher
from .finnhub_fetcher import FinnhubFetcher
from .alphavantage_fetcher import AlphaVantageFetcher
from .us_index_mapping import is_us_index_code, is_us_stock_code, get_us_index_yf_symbol, US_INDEX_MAPPING

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'EfinanceFetcher',
    'TencentFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'PytdxFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
    'LongbridgeFetcher',
    'FinnhubFetcher',
    'AlphaVantageFetcher',
    'is_us_index_code',
    'is_us_stock_code',
    'is_hk_stock_code',
    'get_us_index_yf_symbol',
    'US_INDEX_MAPPING',
]
