# -*- coding: utf-8 -*-
"""
===================================
US stockindex\u4e0estock code\u5de5\u5177
===================================

\u63d0\u4f9b:
1. US stockindexcode\u6620\u5c04 (\u5982 SPX -> ^GSPC)
2. US stockstock code\u8bc6\u522b (AAPL、TSLA \u7b49)

US stockindex\u5728 Yahoo Finance Medium\u9700\u4f7f\u7528 ^ prefix; \u4e0estock code\u4e0d\u540c.
"""

import re

# US stockcode\u6b63\u5219: 1-5 \u4e2a\u5927\u5199\u5b57\u6bcd; optional .X \u540e\u7f00 (\u5982 BRK.B)
_US_STOCK_PATTERN = re.compile(r'^[A-Z]{1,5}(\.[A-Z])?$')


# user\u8f93\u5165 -> (Yahoo Finance \u7b26\u53f7, Medium\u6587name)
US_INDEX_MAPPING = {
    # \u6807\u666e 500
    'SPX': ('^GSPC', '\u6807\u666e500index'),
    '^GSPC': ('^GSPC', '\u6807\u666e500index'),
    'GSPC': ('^GSPC', '\u6807\u666e500index'),
    # \u9053\u743c\u65af\u5de5\u4e1a\u5e73\u5747index
    'DJI': ('^DJI', '\u9053\u743c\u65af\u5de5\u4e1aindex'),
    '^DJI': ('^DJI', '\u9053\u743c\u65af\u5de5\u4e1aindex'),
    'DJIA': ('^DJI', '\u9053\u743c\u65af\u5de5\u4e1aindex'),
    # \u7eb3\u65af\u8fbe\u514b\u7efc\u5408index
    'IXIC': ('^IXIC', '\u7eb3\u65af\u8fbe\u514b\u7efc\u5408index'),
    '^IXIC': ('^IXIC', '\u7eb3\u65af\u8fbe\u514b\u7efc\u5408index'),
    'NASDAQ': ('^IXIC', '\u7eb3\u65af\u8fbe\u514b\u7efc\u5408index'),
    # \u7eb3\u65af\u8fbe\u514b 100
    'NDX': ('^NDX', '\u7eb3\u65af\u8fbe\u514b100index'),
    '^NDX': ('^NDX', '\u7eb3\u65af\u8fbe\u514b100index'),
    # VIX \u6ce2\u52a8\u7387index
    'VIX': ('^VIX', 'VIX\u6050\u614cindex'),
    '^VIX': ('^VIX', 'VIX\u6050\u614cindex'),
    # \u7f57\u7d20 2000
    'RUT': ('^RUT', '\u7f57\u7d202000index'),
    '^RUT': ('^RUT', '\u7f57\u7d202000index'),
}


def is_us_index_code(code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3aUS stockindex\u7b26\u53f7.

    Args:
        code: \u80a1\u7968/indexcode; \u5982 'SPX', 'DJI'

    Returns:
        True \u8868\u793a\u662f\u5df2\u77e5US stockindex\u7b26\u53f7; \u5426\u5219 False

    Examples:
        >>> is_us_index_code('SPX')
        True
        >>> is_us_index_code('AAPL')
        False
    """
    return (code or '').strip().upper() in US_INDEX_MAPPING


def is_us_stock_code(code: str) -> bool:
    """
    \u5224\u65adcode\u662f\u5426\u4e3aUS stock\u80a1\u7968\u7b26\u53f7 (\u6392\u9664US stockindex).

    US stockstock code\u4e3a 1-5 \u4e2a\u5927\u5199\u5b57\u6bcd; optional .X \u540e\u7f00\u5982 BRK.B.
    US stockindex (SPX、DJI \u7b49)\u660e\u786e\u6392\u9664.

    Args:
        code: stock code; \u5982 'AAPL', 'TSLA', 'BRK.B'

    Returns:
        True \u8868\u793a\u662fUS stock\u80a1\u7968\u7b26\u53f7; \u5426\u5219 False

    Examples:
        >>> is_us_stock_code('AAPL')
        True
        >>> is_us_stock_code('TSLA')
        True
        >>> is_us_stock_code('BRK.B')
        True
        >>> is_us_stock_code('SPX')
        False
        >>> is_us_stock_code('600519')
        False
    """
    normalized = (code or '').strip().upper()
    # US stockindex\u4e0d\u662f\u80a1\u7968
    if normalized in US_INDEX_MAPPING:
        return False
    return bool(_US_STOCK_PATTERN.match(normalized))


def get_us_index_yf_symbol(code: str) -> tuple:
    """
    \u83b7\u53d6US stockindex\u7684 Yahoo Finance \u7b26\u53f7\u4e0eMedium\u6587name.

    Args:
        code: user\u8f93\u5165; \u5982 'SPX', '^GSPC', 'DJI'

    Returns:
        (yf_symbol, chinese_name) \u5143\u7ec4; \u672a\u627e\u5230\u65f6\u8fd4\u56de (None, None).

    Examples:
        >>> get_us_index_yf_symbol('SPX')
        ('^GSPC', '\u6807\u666e500index')
        >>> get_us_index_yf_symbol('AAPL')
        (None, None)
    """
    normalized = (code or '').strip().upper()
    return US_INDEX_MAPPING.get(normalized, (None, None))
