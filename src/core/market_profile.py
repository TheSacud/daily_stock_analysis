# -*- coding: utf-8 -*-
"""
market reviewmarket\u533a\u57dfconfig

\u5b9a\u4e49\u5404market\u533a\u57df\u7684index、newssearch\u8bcd、Prompt \u63d0\u793a\u7b49\u5143\u6570\u636e;
\u4f9b MarketAnalyzer \u6309 region \u5207\u6362 A \u80a1/HK stock/US stock/\u65e5\u97e9\u590d\u76d8\u884c\u4e3a.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class MarketProfile:
    """market reviewmarket\u533a\u57dfconfig"""

    region: str  # "cn" | "hk" | "us" | "jp" | "kr"
    # \u7528\u4e8e\u5224\u65ad\u6574\u4f53\u8d70\u52bf\u7684indexcode; cn \u7528\u4e0a\u8bc1 000001; us \u7528\u6807\u666e SPX
    mood_index_code: str
    # newssearch\u5173\u952e\u8bcd
    news_queries: List[str]
    # index\u70b9\u8bc4 Prompt \u63d0\u793a\u8bed
    prompt_index_hint: str
    # market\u6982\u51b5\u662f\u5426\u5305\u542bchange\u5bb6\u6570、\u6da8\u505c\u8dcc\u505c (A \u80a1\u6709; US stock\u65e0)
    has_market_stats: bool
    # market\u6982\u51b5\u662f\u5426\u5305\u542bsectorchange (A \u80a1\u6709; US stock\u6682\u65e0)
    has_sector_rankings: bool


CN_PROFILE = MarketProfile(
    region="cn",
    mood_index_code="000001",
    news_queries=[
        "A-share \u5927\u76d8 \u590d\u76d8",
        "\u80a1\u5e02 \u884c\u60c5 analyze",
        "A-share market \u70ed\u70b9 sector",
    ],
    prompt_index_hint="analyze\u4e0a\u8bc1、\u6df1\u8bc1、\u521b\u4e1a\u677f\u7b49\u5404index\u8d70\u52bf\u7279\u70b9",
    has_market_stats=True,
    has_sector_rankings=True,
)

US_PROFILE = MarketProfile(
    region="us",
    mood_index_code="SPX",
    news_queries=[
        "US stock \u5927\u76d8",
        "US stock market",
        "S&P 500 NASDAQ",
    ],
    prompt_index_hint="analyze\u6807\u666e500、\u7eb3\u65af\u8fbe\u514b、\u9053\u6307\u7b49\u5404index\u8d70\u52bf\u7279\u70b9",
    has_market_stats=False,
    has_sector_rankings=False,
)

HK_PROFILE = MarketProfile(
    region="hk",
    mood_index_code="HSI",
    news_queries=[
        "HK stock \u5927\u76d8 \u590d\u76d8",
        "Hong Kong stock market",
        "\u6052\u751findex \u884c\u60c5",
    ],
    prompt_index_hint="analyze\u6052\u751findex、\u6052\u751f\u79d1\u6280index、\u56fd\u4f01index\u7b49\u5404index\u8d70\u52bf\u7279\u70b9",
    has_market_stats=False,
    has_sector_rankings=False,
)

JP_PROFILE = MarketProfile(
    region="jp",
    mood_index_code="N225",
    news_queries=[
        "\u65e5\u672c\u80a1\u5e02 \u65e5\u7ecf225",
        "Japan stock market Nikkei TOPIX",
        "\u65e5\u7ecf225 \u4e1c\u8bc1index \u884c\u60c5",
    ],
    prompt_index_hint="analyze\u65e5\u7ecf225、\u4e1c\u8bc1index\u7b49\u65e5\u672c\u4e3b\u8981index\u8d70\u52bf\u7279\u70b9",
    has_market_stats=False,
    has_sector_rankings=False,
)

KR_PROFILE = MarketProfile(
    region="kr",
    mood_index_code="KS11",
    news_queries=[
        "\u97e9\u56fd\u80a1\u5e02 KOSPI",
        "Korea stock market KOSPI KOSDAQ",
        "KOSPI KOSDAQ \u884c\u60c5",
    ],
    prompt_index_hint="analyze KOSPI、KOSDAQ \u7b49\u97e9\u56fd\u4e3b\u8981index\u8d70\u52bf\u7279\u70b9",
    has_market_stats=False,
    has_sector_rankings=False,
)


def get_profile(region: str) -> MarketProfile:
    """\u6839\u636e region \u8fd4\u56de\u5bf9\u5e94\u7684 MarketProfile"""
    if region == "us":
        return US_PROFILE
    if region == "hk":
        return HK_PROFILE
    if region == "jp":
        return JP_PROFILE
    if region == "kr":
        return KR_PROFILE
    return CN_PROFILE
