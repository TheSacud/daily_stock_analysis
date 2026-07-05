# -*- coding: utf-8 -*-
from __future__ import annotations

"""
===================================
stock code\u4e0ename\u6620\u5c04
===================================

Shared stock code -> name mapping, used by analyzer, data_provider, and name_to_code_resolver.
"""

# Stock code -> name mapping (common stocks)
STOCK_NAME_MAP = {
    # === A-shares ===
    "600519": "\u8d35\u5dde\u8305\u53f0",
    "000001": "\u5e73\u5b89\u94f6\u884c",
    "300750": "\u5b81\u5fb7\u65f6\u4ee3",
    "002594": "\u6bd4\u4e9a\u8fea",
    "600036": "\u62db\u5546\u94f6\u884c",
    "601318": "Medium\u56fd\u5e73\u5b89",
    "000858": "\u4e94\u7cae\u6db2",
    "600276": "\u6052\u745e\u533b\u836f",
    "601012": "\u9686\u57fa\u7eff\u80fd",
    "002475": "\u7acb\u8baf\u7cbe\u5bc6",
    "300059": "Eastmoney",
    "002415": "\u6d77\u5eb7\u5a01\u89c6",
    "600900": "\u957f\u6c5f\u7535\u529b",
    "601166": "\u5174\u4e1a\u94f6\u884c",
    "600028": "Medium\u56fd\u77f3\u5316",
    "600030": "Medium\u4fe1\u8bc1\u5238",
    "600031": "\u4e09\u4e00\u91cd\u5de5",
    "600050": "Medium\u56fd\u8054\u901a",
    "600104": "\u4e0a\u6c7d\u96c6\u56e2",
    "600111": "\u5317\u65b9\u7a00\u571f",
    "600150": "Medium\u56fd\u8239\u8236",
    "600309": "\u4e07\u534e\u5316\u5b66",
    "600406": "\u56fd\u7535\u5357\u745e",
    "600690": "\u6d77\u5c14\u667a\u5bb6",
    "600760": "Medium\u822a\u6c88\u98de",
    "600809": "\u5c71\u897f\u6c7e\u9152",
    "600887": "\u4f0a\u5229\u80a1\u4efd",
    "600930": "\u534e\u7535\u65b0\u80fd",
    "601088": "Medium\u56fd\u795e\u534e",
    "601127": "\u8d5b\u529b\u65af",
    "601211": "\u56fd\u6cf0\u6d77\u901a",
    "601225": "\u9655\u897f\u7164\u4e1a",
    "601288": "\u519c\u4e1a\u94f6\u884c",
    "601328": "\u4ea4\u901a\u94f6\u884c",
    "601398": "\u5de5\u5546\u94f6\u884c",
    "601601": "Medium\u56fd\u592a\u4fdd",
    "601628": "Medium\u56fd\u4eba\u5bff",
    "601658": "\u90ae\u50a8\u94f6\u884c",
    "601668": "Medium\u56fd\u5efa\u7b51",
    "601728": "Medium\u56fd\u7535\u4fe1",
    "601816": "\u4eac\u6caaHigh\u94c1",
    "601857": "Medium\u56fd\u77f3\u6cb9",
    "601888": "Medium\u56fdMedium\u514d",
    "601899": "\u7d2b\u91d1\u77ff\u4e1a",
    "601919": "Medium\u8fdc\u6d77\u63a7",
    "601985": "Medium\u56fd\u6838\u7535",
    "601988": "Medium\u56fd\u94f6\u884c",
    "603019": "Medium\u79d1\u66d9\u5149",
    "603259": "\u836f\u660e\u5eb7\u5fb7",
    "603501": "\u8c6a\u5a01\u96c6\u56e2",
    "603993": "\u6d1b\u9633\u94bc\u4e1a",
    "688008": "\u6f9c\u8d77\u79d1\u6280",
    "688012": "Medium\u5fae\u516c\u53f8",
    "688041": "\u6d77\u5149info",
    "688111": "\u91d1\u5c71\u529e\u516c",
    "688256": "\u5bd2\u6b66\u7eaa",
    "688981": "Medium\u82af\u56fd\u9645",
    # === US stocks ===
    "AAPL": "\u82f9\u679c",
    "TSLA": "\u7279\u65af\u62c9",
    "MSFT": "\u5fae\u8f6f",
    "GOOGL": "\u8c37\u6b4cA",
    "GOOG": "\u8c37\u6b4cC",
    "AMZN": "\u4e9a\u9a6c\u900a",
    "NVDA": "\u82f1\u4f1f\u8fbe",
    "META": "Meta",
    "AMD": "AMD",
    "INTC": "\u82f1\u7279\u5c14",
    "BABA": "\u963f\u91cc\u5df4\u5df4",
    "PDD": "\u62fc\u591a\u591a",
    "JD": "\u4eac\u4e1c",
    "BIDU": "\u767e\u5ea6",
    "NIO": "\u851a\u6765",
    "XPEV": "\u5c0f\u9e4f\u6c7d\u8f66",
    "LI": "\u7406\u60f3\u6c7d\u8f66",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",
    # === HK stocks (5-digit) ===
    "00700": "\u817e\u8baf\u63a7\u80a1",
    "03690": "\u7f8e\u56e2",
    "01810": "\u5c0f\u7c73\u96c6\u56e2",
    "09988": "\u963f\u91cc\u5df4\u5df4",
    "09618": "\u4eac\u4e1c\u96c6\u56e2",
    "09888": "\u767e\u5ea6\u96c6\u56e2",
    "01024": "\u5feb\u624b",
    "00981": "Medium\u82af\u56fd\u9645",
    "02015": "\u7406\u60f3\u6c7d\u8f66",
    "09868": "\u5c0f\u9e4f\u6c7d\u8f66",
    "00005": "\u6c47\u4e30\u63a7\u80a1",
    "01299": "\u53cb\u90a6\u4fdd\u9669",
    "00941": "Medium\u56fd\u79fb\u52a8",
    "00883": "Medium\u56fd\u6d77\u6d0b\u77f3\u6cb9",
}


def is_meaningful_stock_name(name: str | None, stock_code: str) -> bool:
    """Return whether a stock name is useful for display or caching."""
    if not name:
        return False

    normalized_name = str(name).strip()
    if not normalized_name:
        return False

    normalized_code = (stock_code or "").strip().upper()
    if normalized_name.upper() == normalized_code:
        return False

    if normalized_name.startswith("\u80a1\u7968"):
        return False

    placeholder_values = {
        "N/A",
        "NA",
        "NONE",
        "NULL",
        "--",
        "-",
        "UNKNOWN",
        "TICKER",
    }
    if normalized_name.upper() in placeholder_values:
        return False

    return True
