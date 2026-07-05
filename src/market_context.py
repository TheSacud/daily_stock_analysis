# -*- coding: utf-8 -*-
"""
Market context detection for LLM prompts.

Detects the market (A-shares, HK, US) from a stock code and returns
market-specific role descriptions so prompts are not hardcoded to a
single market.

Fixes: https://github.com/ZhuLinsen/daily_stock_analysis/issues/644
"""

import re
from typing import Optional

from src.services.market_symbol_utils import get_suffix_market


def detect_market(stock_code: Optional[str]) -> str:
    """Detect market from stock code.

    Returns:
        One of 'cn', 'hk', 'us', or 'cn' as fallback.
    """
    if not stock_code:
        return "cn"

    code = stock_code.strip().upper()

    # HK stocks: HK00700, 00700.HK, or 5-digit pure numbers
    if code.startswith("HK") or code.endswith(".HK"):
        return "hk"
    lower = code.lower()
    if lower.endswith(".hk"):
        return "hk"
    # 5-digit pure numbers are HK (A-shares are 6-digit)
    if code.isdigit() and len(code) == 5:
        return "hk"

    # Suffix-only Yahoo symbols for JP/KR/TW. Bare Korean/Taiwan numeric
    # codes keep existing fallback semantics to avoid cross-market collisions.
    suffix_market = get_suffix_market(code)
    if suffix_market:
        return suffix_market

    # US stocks: 1-5 uppercase letters (AAPL, TSLA, GOOGL)
    # Also handles suffixed forms like BRK.B
    if re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code):
        return "us"

    # Default: A-shares (6-digit numbers like 600519, 000001)
    return "cn"


# -- Market-specific role descriptions --

_MARKET_ROLES = {
    "cn": {
        "zh": " A \u80a1",
        "en": "China A-shares",
    },
    "hk": {
        "zh": "HK stock",
        "en": "Hong Kong stock",
    },
    "us": {
        "zh": "US stock",
        "en": "US stock",
    },
    "jp": {
        "zh": "JP stock",
        "en": "Japan stock",
    },
    "kr": {
        "zh": "KR stock",
        "en": "Korea stock",
    },
    "tw": {
        "zh": "TW stock",
        "en": "Taiwan stock",
    },
}

_MARKET_GUIDELINES = {
    "cn": {
        "zh": (
            "- this runanalyze\u5bf9\u8c61\u4e3a **A \u80a1** (Medium\u56fd\u6caa\u6df1\u4ea4\u6613\u6240\u4e0a\u5e02\u80a1\u7968).\n"
            "- \u8bf7\u5173\u6ce8 A \u80a1\u7279\u6709\u7684change\u505c\u673a\u5236 (±10%/±20%/±30%)、T+1 \u4ea4\u6613\u5236\u5ea6\u53ca\u76f8\u5173\u653f\u7b56\u56e0\u7d20."
        ),
        "en": (
            "- This analysis covers a **China A-share** (listed on Shanghai/Shenzhen exchanges).\n"
            "- Consider A-share-specific rules: daily price limits (±10%/±20%/±30%), T+1 settlement, and PRC policy factors."
        ),
    },
    "hk": {
        "zh": (
            "- this runanalyze\u5bf9\u8c61\u4e3a **HK stock** (\u9999\u6e2f\u4ea4\u6613\u6240\u4e0a\u5e02\u80a1\u7968).\n"
            "- HK stock\u65e0change\u505climit; \u652f\u6301 T+0 \u4ea4\u6613; \u9700\u5173\u6ce8\u6e2f\u5e01\u6c47\u7387、\u5357\u5317\u5411\u8d44\u91d1\u6d41\u53ca\u8054\u4ea4\u6240\u7279\u6709\u89c4\u5219."
        ),
        "en": (
            "- This analysis covers a **Hong Kong stock** (listed on HKEX).\n"
            "- HK stocks have no daily price limits, allow T+0 trading. Consider HKD FX, Southbound/Northbound flows, and HKEX-specific rules."
        ),
    },
    "us": {
        "zh": (
            "- this runanalyze\u5bf9\u8c61\u4e3a **US stock** (\u7f8e\u56fd\u4ea4\u6613\u6240\u4e0a\u5e02\u80a1\u7968).\n"
            "- US stock\u65e0change\u505climit (\u4f46\u6709\u7194\u65ad\u673a\u5236); \u652f\u6301 T+0 \u4ea4\u6613\u548c\u76d8\u524d\u76d8\u540e\u4ea4\u6613; \u9700\u5173\u6ce8\u7f8e\u5143\u6c47\u7387、\u7f8e\u8054\u50a8\u653f\u7b56\u53ca SEC \u76d1\u7ba1\u52a8\u6001."
        ),
        "en": (
            "- This analysis covers a **US stock** (listed on NYSE/NASDAQ).\n"
            "- US stocks have no daily price limits (but have circuit breakers), allow T+0 and pre/after-market trading. Consider USD FX, Fed policy, and SEC regulations."
        ),
    },
    "jp": {
        "zh": (
            "- this runanalyze\u5bf9\u8c61\u4e3a **JP stock** (\u65e5\u672c\u4ea4\u6613\u6240\u4e0a\u5e02\u80a1\u7968; Yahoo Finance suffix \u5982 `.T`).\n"
            "- \u8bf7\u6309\u65e5\u672cmarket\u8bed\u5883analyze; \u5173\u6ce8\u65e5\u5143\u6c47\u7387、\u65e5\u672c\u592e\u884c\u653f\u7b56、\u516c\u53f8\u6cbb\u7406\u4e0eindustry\u5468\u671f；\u4e0d\u8981\u5957\u7528 A \u80a1change\u505c、\u5317\u5411\u8d44\u91d1、\u9f99\u864e\u699c、\u878d\u8d44\u878d\u5238\u7b49 A \u80a1\u4e13\u5c5econcept."
        ),
        "en": (
            "- This analysis covers a **Japan stock** (Yahoo Finance suffix such as `.T`).\n"
            "- Use Japan-market context: JPY FX, BOJ policy, corporate governance, and sector cycles; do not apply China A-share concepts such as daily price-limit boards, Northbound flows, Dragon Tiger lists, or margin-financing narratives."
        ),
    },
    "kr": {
        "zh": (
            "- this runanalyze\u5bf9\u8c61\u4e3a **KR stock** (\u97e9\u56fd\u4ea4\u6613\u6240/KOSDAQ \u4e0a\u5e02\u80a1\u7968; \u5fc5\u987b\u5e26 `.KS` / `.KQ` \u540e\u7f00).\n"
            "- \u8bf7\u6309\u97e9\u56fdmarket\u8bed\u5883analyze; \u5173\u6ce8\u97e9\u5143\u6c47\u7387、\u97e9\u56fd\u592e\u884c\u653f\u7b56、\u534a\u5bfc\u4f53/\u4e92\u8054\u7f51\u4ea7\u4e1a\u5468\u671f\u4e0e\u97e9\u56fd\u4ea4\u6613\u5236\u5ea6；\u4e0d\u8981\u5957\u7528 A \u80a1change\u505c、\u5317\u5411\u8d44\u91d1、\u9f99\u864e\u699c、\u878d\u8d44\u878d\u5238\u7b49 A \u80a1\u4e13\u5c5econcept."
        ),
        "en": (
            "- This analysis covers a **Korea stock** (KOSPI/KOSDAQ suffix `.KS` / `.KQ`).\n"
            "- Use Korea-market context: KRW FX, Bank of Korea policy, semiconductor/internet cycles, and local trading rules; do not apply China A-share concepts such as daily price-limit boards, Northbound flows, Dragon Tiger lists, or margin-financing narratives."
        ),
    },
    "tw": {
        "zh": (
            "- this runanalyze\u5bf9\u8c61\u4e3a **TW stock** (\u53f0\u6e7e\u8bc1\u5238\u4ea4\u6613\u6240\u4e0a\u5e02 `.TW`; or\u53f0\u6e7e\u67dc\u4e70Medium\u5fc3\u4e0a\u67dc `.TWO`).\n"
            "- \u8bf7\u6309\u53f0\u6e7emarket\u8bed\u5883analyze; \u5173\u6ce8\u65b0\u53f0\u5e01 (TWD)\u6c47\u7387、\u53f0\u6e7e\u592e\u884c\u653f\u7b56、\u534a\u5bfc\u4f53/\u7535\u5b50\u4ee3\u5de5\u4ea7\u4e1a\u94fe、"
            "\u4e09\u5927\u6cd5\u4eba (\u5916\u8d44／\u6295\u4fe1／\u81ea\u8425\u5546)\u4e70\u5356\u8d85、\u878d\u8d44\u878d\u5238\u4e0e\u5f53\u51b2; \u4ee5\u53ca TWSE/TPEx ±10% change\u505c\u5236\u5ea6；"
            "\u4e0d\u8981\u5957\u7528 A \u80a1\u4e13\u5c5e\u7684\u5317\u5411\u8d44\u91d1、\u9f99\u864e\u699c\u7b49concept (TW stock\u7684\u6cd5\u4eba\u7ed3\u6784\u4e0e\u8d44\u91d1\u6d41\u53e3\u5f84\u4e0e A \u80a1\u4e0d\u540c)."
        ),
        "en": (
            "- This analysis covers a **Taiwan stock** (TWSE-listed `.TW`, or TPEx/OTC `.TWO`).\n"
            "- Use Taiwan-market context: TWD FX, Central Bank of the ROC policy, the semiconductor/"
            "electronics-foundry supply chain, the three institutional investor groups (foreign / "
            "investment-trust / dealer), margin trading and day trading, and the TWSE/TPEx ±10% daily "
            "price limit; do not apply China A-share-specific concepts such as Northbound flows or Dragon Tiger lists."
        ),
    },
}


def get_market_role(stock_code: Optional[str], lang: str = "zh") -> str:
    """Return market-specific role description for LLM prompt.

    Args:
        stock_code: The stock code being analyzed.
        lang: 'zh' or 'en'.

    Returns:
        Role string like 'A \u80a1\u6295\u8d44analyze' or 'US stock investment analysis'.
    """
    market = detect_market(stock_code)
    lang_key = "en" if lang in ("en", "ko") else "zh"
    return _MARKET_ROLES.get(market, _MARKET_ROLES["cn"])[lang_key]


def get_market_guidelines(stock_code: Optional[str], lang: str = "zh") -> str:
    """Return market-specific analysis guidelines for LLM prompt.

    Args:
        stock_code: The stock code being analyzed.
        lang: 'zh' or 'en'.

    Returns:
        Multi-line string with market-specific guidelines.
    """
    market = detect_market(stock_code)
    lang_key = "en" if lang in ("en", "ko") else "zh"
    return _MARKET_GUIDELINES.get(market, _MARKET_GUIDELINES["cn"])[lang_key]
