#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Stock Index from CSV File

Input:
  - Tushare format: data/stock_list_{a,hk,us}.csv
  - Seed format: scripts/stock_index_seeds/stock_list_{jp,kr}.csv
  - AkShare format: logs/stock_basic_*.csv

Output: apps/dsa-web/public/stocks.index.json

Usage:
    python3 scripts/generate_index_from_csv.py              # \u9ed8\u8ba4\u4f7f\u7528 Tushare
    python3 scripts/generate_index_from_csv.py --source akshare
    python3 scripts/generate_index_from_csv.py --test       # \u6d4b\u8bd5\u6a21\u5f0f
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pypinyin import lazy_pinyin, Style
    PYPINYIN_AVAILABLE = True
except ImportError:
    lazy_pinyin = None
    Style = None
    PYPINYIN_AVAILABLE = False


def require_pypinyin() -> bool:
    """Ensure pypinyin is available before generating autocomplete assets."""
    if PYPINYIN_AVAILABLE:
        return True

    print("[Error] pypinyin not available; cannot generate stock autocomplete index.")
    print("[Info] Install dependencies with: pip install -r requirements.txt")
    return False


def load_csv_data(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Load stock data from AkShare format CSV file

    Args:
        csv_path: CSV file path

    Returns:
        List of stock data
    """
    stocks = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row['ts_code'].strip()
            symbol = row['symbol'].strip()
            name = row['name'].strip()

            # Skip invalid rows.
            if not ts_code or not symbol or not name:
                continue

            stocks.append({
                'ts_code': ts_code,
                'symbol': symbol,
                'name': name,
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'list_date': row.get('list_date', ''),
            })

    return stocks


def load_tushare_data(data_dir: Path) -> List[Dict[str, Any]]:
    """
    \u4ece Tushare CSV \u6587\u4ef6\u52a0\u8f7d\u591a\u5e02\u573a\u80a1\u7968\u6570\u636e

    Args:
        data_dir: \u6570\u636e\u76ee\u5f55\u8def\u5f84

    Returns:
        \u5408\u5e76\u540e\u7684\u80a1\u7968\u5217\u8868
    """
    all_stocks = []
    seed_dir = Path(__file__).parent / 'stock_index_seeds'
    default_data_dir = Path(__file__).parent.parent / 'data'
    use_seed_fallback = data_dir.resolve() == default_data_dir.resolve()

    def _csv_path(file_name: str) -> Path:
        data_path = data_dir / file_name
        if data_path.exists() or not use_seed_fallback:
            return data_path
        return seed_dir / file_name

    market_files = {
        'CN': data_dir / 'stock_list_a.csv',
        'HK': data_dir / 'stock_list_hk.csv',
        'US': data_dir / 'stock_list_us.csv',
        'JP': _csv_path('stock_list_jp.csv'),
        'KR': _csv_path('stock_list_kr.csv'),
    }

    for market_name, csv_file in market_files.items():
        if not csv_file.exists():
            print(f"[Warning] \u672a\u627e\u5230\u6587\u4ef6：{csv_file}")
            continue

        print(f"  \u6b63\u5728\u8bfb\u53d6 {market_name} \u5e02\u573a\u6570\u636e：{csv_file.name}")

        try:
            file_stocks = []
            selected_us_stocks: Dict[str, tuple[Dict[str, Any], int]] = {}
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # \u4f20\u5165\u5e02\u573a\u53c2\u6570\u4ee5\u4f18\u5316\u5224\u65ad（\u5bf9\u4e8e\u7279\u6b8a\u683c\u5f0f\u5982 DUMMY）
                    parsed = parse_stock_row(row, market_name)
                    if not parsed:
                        continue

                    if market_name == 'US':
                        # Tushare us_basic may include historical rows for a reused ticker.
                        # Keep one deterministic row per ts_code before generating the index.
                        delist_priority = get_us_delist_priority(row)
                        existing = selected_us_stocks.get(parsed['ts_code'])
                        if existing is None or delist_priority > existing[1]:
                            selected_us_stocks[parsed['ts_code']] = (parsed, delist_priority)
                        continue

                    if parsed:
                        all_stocks.append(parsed)
                        file_stocks.append(parsed)

            if market_name == 'US':
                file_stocks = [item for item, _priority in selected_us_stocks.values()]
                all_stocks.extend(file_stocks)

            print(f"    ✓ {market_name} \u5e02\u573a\u8bfb\u53d6\u5b8c\u6210：{len(file_stocks)} \u53ea\u80a1\u7968")

        except Exception as e:
            print(f"    [Error] \u8bfb\u53d6 {csv_file.name} \u5931\u8d25：{e}")

    return all_stocks


def get_us_delist_priority(row: Dict[str, str]) -> int:
    """
    \u4e3a\u590d\u7528 ticker \u7684\u7f8e\u80a1\u8bb0\u5f55\u751f\u6210\u53bb\u91cd\u4f18\u5148\u7ea7。

    Tushare us_basic \u5bfc\u51fa\u7684 delist_date \u5bf9\u5f53\u524d\u8bb0\u5f55\u5e76\u4e0d\u603b\u662f\u7a33\u5b9a：
    - \u7a7a\u5b57\u7b26\u4e32\u901a\u5e38\u8868\u793a\u5f53\u524d\u4ecd\u5728\u4f7f\u7528\u7684 ticker
    - ``NaT`` \u591a\u89c1\u4e8e\u5386\u53f2\u8bb0\u5f55\u6216\u65e5\u671f\u5360\u4f4d\u503c
    - \u5b9e\u9645\u65e5\u671f\u8868\u793a\u660e\u786e\u9000\u5e02

    \u56e0\u6b64\u524d\u7f6e\u53bb\u91cd\u65f6\u4f18\u5148\u9009\u62e9：
    1. delist_date \u4e3a\u7a7a
    2. delist_date \u4e3a NaT
    3. delist_date \u4e3a\u5b9e\u9645\u65e5\u671f

    \u540c\u4f18\u5148\u7ea7\u65f6\u4fdd\u7559 CSV \u4e2d\u6700\u5148\u51fa\u73b0\u7684\u8bb0\u5f55，\u907f\u514d\u5728\u4fe1\u606f\u4e0d\u8db3\u65f6\u968f\u610f\u5207\u6362\u540d\u79f0。
    """
    delist_date = (row.get('delist_date') or '').strip()
    if not delist_date:
        return 2
    if delist_date.upper() == 'NAT':
        return 1
    return 0


def load_akshare_data(logs_dir: Path) -> List[Dict[str, Any]]:
    """
    \u4ece AkShare CSV \u6587\u4ef6\u52a0\u8f7d\u80a1\u7968\u6570\u636e

    Args:
        logs_dir: \u65e5\u5fd7\u76ee\u5f55\u8def\u5f84

    Returns:
        \u80a1\u7968\u5217\u8868

    \u8bf4\u660e：
        AkShare \u8fd9\u6761\u8f93\u5165\u8def\u5f84\u4fdd\u7559\u5176\u539f\u59cb name \u5b57\u6bb5，\u4e0d\u989d\u5916\u5957\u7528
        Tushare A \u80a1\u90a3\u5957 XD / XR / DR \u72b6\u6001\u524d\u7f00\u4fee\u6b63\u903b\u8f91。\u8fd9\u91cc\u7684\u76ee\u6807\u662f
        \u590d\u7528 AkShare \u5df2\u8f93\u51fa\u7684\u5c55\u793a\u540d，\u800c\u4e0d\u662f\u5bf9\u5176\u505a\u4e8c\u6b21\u5f52\u4e00\u5316。
    """
    csv_files = list(logs_dir.glob("stock_basic_*.csv"))

    if not csv_files:
        print("[Error] \u672a\u627e\u5230 CSV \u6587\u4ef6：logs/stock_basic_*.csv")
        return []

    # \u4f7f\u7528\u6700\u65b0\u7684 CSV \u6587\u4ef6
    csv_file = sorted(csv_files)[-1]
    print(f"  \u6b63\u5728\u8bfb\u53d6 AkShare \u6570\u636e：{csv_file.name}")

    stocks = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row['ts_code'].strip()
            symbol = row['symbol'].strip()
            name = row['name'].strip()

            # Skip invalid rows.
            if not ts_code or not symbol or not name:
                continue

            stocks.append({
                'ts_code': ts_code,
                'symbol': symbol,
                'name': name,
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'list_date': row.get('list_date', ''),
            })

    print(f"    ✓ \u5171\u8bfb\u53d6 {len(stocks)} \u53ea\u80a1\u7968")
    return stocks


def generate_pinyin(name: str) -> tuple:
    """
    Generate pinyin for stock name

    Args:
        name: Stock name

    Returns:
        Tuple of (pinyin_full, pinyin_abbr)
    """
    if not PYPINYIN_AVAILABLE:
        raise RuntimeError("pypinyin is required to generate stock autocomplete index")

    try:
        normalized_name = normalize_name_for_pinyin(name)

        # Full pinyin spelling.
        py_full = lazy_pinyin(normalized_name, style=Style.NORMAL)
        pinyin_full = ''.join(py_full)

        # Pinyin abbreviation.
        py_abbr = lazy_pinyin(normalized_name, style=Style.FIRST_LETTER)
        pinyin_abbr = ''.join(py_abbr)

        return (pinyin_full, pinyin_abbr)
    except Exception as e:
        print(f"[Warning] Failed to generate pinyin for {name}: {e}")
        return (None, None)


def normalize_name_for_pinyin(name: str) -> str:
    """
    Normalize stock name to avoid special prefixes and full-width characters polluting pinyin index

    Args:
        name: Original stock name

    Returns:
        Normalized name for pinyin generation
    """
    normalized = unicodedata.normalize('NFKC', name).strip()

    # Strip common A-share prefixes while preserving the core name.
    normalized = re.sub(r'^(?:\*?ST|N)+', '', normalized, flags=re.IGNORECASE)

    return normalized.strip() or unicodedata.normalize('NFKC', name).strip()


def normalize_stock_name_for_index(name: str, market: str) -> str:
    """
    Normalize stock names before writing the long-lived autocomplete index.

    For A-shares (including BSE), ``XD``/``XR``/``DR`` are
    ex-dividend/ex-rights trading-day prefixes. They should not be stored in
    the official static index because they can become stale almost immediately.
    New-stock prefixes such as ``N``/``C`` and risk-warning prefixes such as
    ``ST``/``*ST`` are preserved; they should be refreshed by the next
    stock-list update.
    """
    normalized = unicodedata.normalize('NFKC', str(name or '')).strip()
    if market in {'CN', 'BSE'}:
        normalized = re.sub(r'^(?:XD|XR|DR)\s*', '', normalized, flags=re.IGNORECASE)
    return normalized.strip()


def extract_symbol_from_ts_code(ts_code: str, market: str) -> Optional[str]:
    """
    \u4ece ts_code \u63d0\u53d6 displayCode

    - A\u80a1：000001.SZ → 000001
    - \u6e2f\u80a1：00700.HK → 00700
    - \u7f8e\u80a1：AAPL → AAPL
    - \u65e5\u80a1/\u97e9\u80a1：7203.T / 005930.KS → \u4fdd\u7559\u540e\u7f00，\u907f\u514d\u4e0e\u5176\u4ed6\u5e02\u573a\u88f8\u4ee3\u7801\u51b2\u7a81

    Args:
        ts_code: TS\u4ee3\u7801
        market: \u5e02\u573a\u4ee3\u7801

    Returns:
        displayCode \u6216 None
    """
    if not ts_code:
        return None

    if market in {'US', 'JP', 'KR'}:
        # \u7f8e\u80a1\u5e38\u89c1 class/share \u540e\u7f00、\u65e5\u97e9 Yahoo \u540e\u7f00\u90fd\u662f\u4ee3\u7801\u8eab\u4efd\u7684\u4e00\u90e8\u5206。
        return ts_code

    if '.' in ts_code:
        # A\u80a1\u548c\u6e2f\u80a1：\u53bb\u9664\u540e\u7f00
        return ts_code.split('.')[0]

    return ts_code


def get_stock_name(row: Dict[str, str], market: str) -> Optional[str]:
    """
    \u83b7\u53d6\u80a1\u7968\u540d\u79f0

    - A\u80a1/\u6e2f\u80a1/\u65e5\u80a1/\u97e9\u80a1：\u4f7f\u7528 name \u5b57\u6bb5
    - \u7f8e\u80a1：\u4f7f\u7528 enname \u5b57\u6bb5（\u82f1\u6587\u540d\u79f0）

    Args:
        row: CSV \u884c\u6570\u636e
        market: \u5e02\u573a\u4ee3\u7801

    Returns:
        \u80a1\u7968\u540d\u79f0\u6216 None
    """
    if market == 'US':
        # \u7f8e\u80a1\u4f7f\u7528\u82f1\u6587\u540d\u79f0
        name = row.get('enname', '').strip()
        return name if name else None
    else:
        # A\u80a1\u548c\u6e2f\u80a1\u4f7f\u7528\u4e2d\u6587\u540d\u79f0
        name = row.get('name', '').strip()
        name = normalize_stock_name_for_index(name, market)
        return name if name else None


def parse_aliases(row: Dict[str, str]) -> List[str]:
    """Parse optional seed aliases from a CSV row."""
    raw_aliases = (row.get('aliases') or row.get('alias') or '').strip()
    if not raw_aliases:
        return []

    aliases: List[str] = []
    for alias in re.split(r'[|;,，、]+', raw_aliases):
        normalized = unicodedata.normalize('NFKC', alias).strip()
        if normalized and normalized not in aliases:
            aliases.append(normalized)
    return aliases


def parse_stock_row(row: Dict[str, str], preferred_market: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    \u89e3\u6790\u5355\u884c\u80a1\u7968\u6570\u636e

    - \u7f8e\u80a1 DUMMY \u8fc7\u6ee4（\u4e25\u683c\u8fc7\u6ee4）
    - \u7a7a\u503c\u6821\u9a8c
    - \u81ea\u52a8\u5224\u65ad\u5e02\u573a\u7c7b\u578b（\u5f53\u65e0\u6cd5\u5224\u65ad\u65f6\u4f7f\u7528 preferred_market）
    - \u8fd4\u56de\u7edf\u4e00\u683c\u5f0f\u7684\u5b57\u5178

    Args:
        row: CSV \u884c\u6570\u636e
        preferred_market: \u5f53 ts_code \u65e0\u6cd5\u5224\u65ad\u5e02\u573a\u65f6\u4f7f\u7528（\u5982\u7f8e\u80a1 DUMMY \u8bb0\u5f55）

    Returns:
        \u89e3\u6790\u540e\u7684\u80a1\u7968\u5b57\u5178，\u65e0\u6548\u6570\u636e\u8fd4\u56de None
    """
    ts_code = row.get('ts_code', '').strip()

    if not ts_code:
        return None

    # \u81ea\u52a8\u5224\u65ad\u5e02\u573a\u7c7b\u578b
    market = determine_market(ts_code)

    # \u5982\u679c ts_code \u6ca1\u6709\u540e\u7f00（\u65e0\u6cd5\u51c6\u786e\u5224\u65ad），\u4e14\u63d0\u4f9b\u4e86 preferred_market，\u5219\u4f7f\u7528\u5b83
    # \u8fd9\u4e3b\u8981\u7528\u4e8e\u5904\u7406\u7f8e\u80a1\u7684\u7279\u6b8a\u683c\u5f0f（\u5982 DUMMY \u8bb0\u5f55）
    if '.' not in ts_code and preferred_market:
        market = preferred_market

    # \u7f8e\u80a1\u7279\u6b8a\u5904\u7406：\u4e25\u683c\u8fc7\u6ee4 DUMMY \u8bb0\u5f55
    if market == 'US':
        enname = row.get('enname', '').strip()
        if not enname or 'DUMMY' in enname.upper():
            return None

    # \u83b7\u53d6\u80a1\u7968\u540d\u79f0
    name = get_stock_name(row, market)
    if not name:
        return None

    # \u63d0\u53d6 displayCode
    display_code = extract_symbol_from_ts_code(ts_code, market)
    if not display_code:
        return None

    return {
        'ts_code': ts_code,
        'symbol': display_code,
        'name': name,
        'market': market,
        'aliases': parse_aliases(row),
    }


def determine_market(ts_code: str) -> str:
    """
    Determine market based on code

    Args:
        ts_code: Trading code (e.g., 000001.SZ, AAPL, BRK.B, 7203.T, 005930.KS)

    Returns:
        Market code (CN, HK, US, BSE, JP, KR)
    """
    if '.' in ts_code:
        # \u6709\u540e\u7f00\u7684\u60c5\u51b5
        suffix = ts_code.split('.')[1]
        # \u68c0\u67e5\u662f\u5426\u4e3a\u4e2d\u56fd\u5e02\u573a\u540e\u7f00
        if suffix in ['SH', 'SZ']:
            return 'CN'
        elif suffix == 'HK':
            return 'HK'
        elif suffix == 'BJ':
            return 'BSE'
        elif suffix == 'T':
            return 'JP'
        elif suffix in ['KS', 'KQ']:
            return 'KR'
        # \u6709\u540e\u7f00\u4f46\u4e0d\u662f\u4e2d\u56fd\u5e02\u573a\u540e\u7f00，\u68c0\u67e5\u662f\u5426\u4e3a\u7f8e\u80a1
        # \u7f8e\u80a1\u53ef\u80fd\u6709\u70b9\u53f7\u540e\u7f00（\u5982 BRK.B, GOOG.A, AAPL.U）
        prefix = ts_code.split('.')[0]
        if prefix.isalpha():
            return 'US'
    else:
        # \u65e0\u540e\u7f00\u7684\u60c5\u51b5
        # \u7eaf\u5b57\u6bcd\u4ee3\u7801\u4e3a\u7f8e\u80a1
        if ts_code.isalpha():
            return 'US'

    # \u9ed8\u8ba4\u4e3a A\u80a1
    return 'CN'


def generate_aliases(name: str, market: str) -> List[str]:
    """
    Generate stock aliases

    Args:
        name: Stock name
        market: Market code

    Returns:
        List of aliases
    """
    aliases = []

    # A\u80a1\u5e38\u89c1\u522b\u540d
    cn_alias_map = {
        '\u8d35\u5dde\u8305\u53f0': ['\u8305\u53f0'],
        '\u4e2d\u56fd\u5e73\u5b89': ['\u5e73\u5b89'],
        '\u5e73\u5b89\u94f6\u884c': ['\u5e73\u94f6'],
        '\u62db\u5546\u94f6\u884c': ['\u62db\u884c'],
        '\u4e94\u7cae\u6db2': ['\u4e94\u7cae'],
        '\u5b81\u5fb7\u65f6\u4ee3': ['\u5b81\u5fb7'],
        '\u6bd4\u4e9a\u8fea': ['\u6bd4\u4e9a'],
        '\u5de5\u5546\u94f6\u884c': ['\u5de5\u884c'],
        '\u5efa\u8bbe\u94f6\u884c': ['\u5efa\u884c'],
        '\u519c\u4e1a\u94f6\u884c': ['\u519c\u884c'],
        '\u4e2d\u56fd\u94f6\u884c': ['\u4e2d\u884c'],
        '\u4ea4\u901a\u94f6\u884c': ['\u4ea4\u884c'],
        '\u5174\u4e1a\u94f6\u884c': ['\u5174\u4e1a'],
        '\u6d66\u53d1\u94f6\u884c': ['\u6d66\u53d1'],
        '\u6c11\u751f\u94f6\u884c': ['\u6c11\u751f'],
        '\u4e2d\u4fe1\u8bc1\u5238': ['\u4e2d\u4fe1'],
        '\u4e1c\u65b9\u8d22\u5bcc': ['\u4e1c\u8d22'],
        '\u6d77\u5eb7\u5a01\u89c6': ['\u6d77\u5eb7'],
        '\u9686\u57fa\u7eff\u80fd': ['\u9686\u57fa'],
        '\u4e2d\u56fd\u795e\u534e': ['\u795e\u534e'],
        '\u957f\u6c5f\u7535\u529b': ['\u957f\u7535'],
        '\u4e2d\u56fd\u77f3\u5316': ['\u77f3\u5316'],
        '\u4e2d\u56fd\u77f3\u6cb9': ['\u77f3\u6cb9'],
    }

    # \u6e2f\u80a1\u5e38\u89c1\u522b\u540d
    hk_alias_map = {
        '\u817e\u8baf\u63a7\u80a1': ['\u817e\u8baf', 'Tencent'],
        '\u963f\u91cc\u5df4\u5df4-SW': ['\u963f\u91cc', '\u963f\u91cc\u5df4\u5df4', 'Alibaba'],
        '\u7f8e\u56e2-W': ['\u7f8e\u56e2', 'Meituan'],
        '\u5c0f\u7c73\u96c6\u56e2-W': ['\u5c0f\u7c73', 'Xiaomi'],
        '\u4eac\u4e1c\u96c6\u56e2-SW': ['\u4eac\u4e1c', 'JD'],
        '\u7f51\u6613-S': ['\u7f51\u6613', 'NetEase'],
        '\u767e\u5ea6\u96c6\u56e2-SW': ['\u767e\u5ea6', 'Baidu'],
        '\u4e2d\u82af\u56fd\u9645': ['\u4e2d\u82af', 'SMIC'],
        '\u4e2d\u56fd\u79fb\u52a8': ['\u4e2d\u79fb\u52a8', 'China Mobile'],
        '\u4e2d\u56fd\u6d77\u6d0b\u77f3\u6cb9': ['\u4e2d\u6d77\u6cb9', 'CNOOC'],
    }

    # \u7f8e\u80a1\u5e38\u89c1\u522b\u540d
    us_alias_map = {
        'Apple Inc.': ['Apple', 'AAPL'],
        'Microsoft Corporation': ['Microsoft', 'MSFT'],
        'Amazon.com, Inc.': ['Amazon', 'AMZN'],
        'Tesla Inc.': ['Tesla', 'TSLA'],
        'Meta Platforms, Inc.': ['Meta', 'Facebook', 'META'],
        'Alphabet Inc.': ['Google', 'Alphabet', 'GOOGL'],
        'NVIDIA Corporation': ['NVIDIA', 'NVDA'],
        'Netflix Inc.': ['Netflix', 'NFLX'],
        'Intel Corporation': ['Intel', 'INTC'],
        'Advanced Micro Devices': ['AMD', 'AMD'],
    }

    # \u6839\u636e\u5e02\u573a\u9009\u62e9\u6620\u5c04\u8868
    if market == 'CN':
        alias_map = cn_alias_map
    elif market == 'HK':
        alias_map = hk_alias_map
    elif market == 'US':
        alias_map = us_alias_map
    else:
        alias_map = {}

    if name in alias_map:
        aliases.extend(alias_map[name])

    return aliases


def build_stock_index(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build the stock index.

    Args:
        stocks: Raw stock rows（\u5df2\u5305\u542b market \u5b57\u6bb5）

    Returns:
        Stock index entries
    """
    index = []

    for stock in stocks:
        ts_code = stock['ts_code']
        symbol = stock['symbol']
        name = stock['name']
        market = stock.get('market', 'CN')  # \u4f18\u5148\u4f7f\u7528\u5df2\u89e3\u6790\u7684\u5e02\u573a，\u5426\u5219\u4ece ts_code \u5224\u65ad

        # \u5982\u679c\u6ca1\u6709 market \u5b57\u6bb5，\u4ece ts_code \u5224\u65ad
        if market == 'CN' and '.' not in ts_code:
            market = determine_market(ts_code)

        # Generate pinyin fields.
        pinyin_full, pinyin_abbr = generate_pinyin(name)

        # Generate aliases.
        aliases = generate_aliases(name, market)
        for alias in stock.get('aliases', []):
            if alias != name and alias not in aliases:
                aliases.append(alias)

        index.append({
            "canonicalCode": ts_code,    # Example: 000001.SZ, AAPL
            "displayCode": symbol,       # Example: 000001, AAPL
            "nameZh": name,
            "pinyinFull": pinyin_full,
            "pinyinAbbr": pinyin_abbr,
            "aliases": aliases,
            "market": market,
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        })

    return index


def compress_index(index: List[Dict[str, Any]]) -> List[List]:
    """
    \u538b\u7f29\u7d22\u5f15\u4e3a\u6570\u7ec4\u683c\u5f0f\u4ee5\u51cf\u5c11\u6587\u4ef6\u5927\u5c0f

    Args:
        index: \u539f\u59cb\u7d22\u5f15

    Returns:
        \u538b\u7f29\u540e\u7684\u7d22\u5f15
    """
    compressed = []
    for item in index:
        compressed.append([
            item["canonicalCode"],
            item["displayCode"],
            item["nameZh"],
            item.get("pinyinFull"),
            item.get("pinyinAbbr"),
            item.get("aliases", []),
            item["market"],
            item["assetType"],
            item["active"],
            item.get("popularity", 0),
        ])
    return compressed


def main():
    """\u4e3b\u51fd\u6570"""
    parser = argparse.ArgumentParser(description='\u4ece CSV \u751f\u6210\u80a1\u7968\u81ea\u52a8\u8865\u5168\u7d22\u5f15')
    parser.add_argument(
        '--source',
        choices=['tushare', 'akshare'],
        default='tushare',
        help='\u6570\u636e\u6e90\u9009\u62e9（\u9ed8\u8ba4: tushare）'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='\u6d4b\u8bd5\u6a21\u5f0f：\u53ea\u9a8c\u8bc1\u4e0d\u5199\u5165\u6587\u4ef6'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("\u80a1\u7968\u7d22\u5f15\u751f\u6210\u5de5\u5177（\u4ece CSV）")
    print("=" * 60)
    print(f"\u6570\u636e\u6e90：{args.source}")

    if not require_pypinyin():
        return 1

    # \u52a0\u8f7d\u6570\u636e
    print("\n[1/5] \u8bfb\u53d6 CSV \u6570\u636e...")
    if args.source == 'tushare':
        data_dir = Path(__file__).parent.parent / 'data'
        stocks = load_tushare_data(data_dir)
    elif args.source == 'akshare':
        logs_dir = Path(__file__).parent.parent / 'logs'
        stocks = load_akshare_data(logs_dir)
    else:
        print(f"[Error] \u4e0d\u652f\u6301\u7684\u6570\u636e\u6e90：{args.source}")
        return 1

    if not stocks:
        print("[Error] \u672a\u52a0\u8f7d\u5230\u4efb\u4f55\u80a1\u7968\u6570\u636e")
        return 1

    print(f"      \u5171\u8bfb\u53d6 {len(stocks)} \u53ea\u80a1\u7968")

    print("\n[2/5] \u751f\u6210\u7d22\u5f15\u6570\u636e...")
    index = build_stock_index(stocks)

    # \u8f93\u51fa\u8def\u5f84
    output_path = (
        Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n[3/5] \u538b\u7f29\u7d22\u5f15\u6570\u636e...")
    compressed = compress_index(index)

    if args.test:
        print("\n[4/5] \u6d4b\u8bd5\u6a21\u5f0f：\u8df3\u8fc7\u5199\u5165\u6587\u4ef6")
        print(f"      \u8f93\u51fa\u8def\u5f84：{output_path}")

        # \u9a8c\u8bc1\u6570\u636e
        print("\n[5/5] \u9a8c\u8bc1\u6570\u636e...")
        print(f"      \u538b\u7f29\u524d：{len(index)} \u6761\u8bb0\u5f55")
        print(f"      \u538b\u7f29\u540e：{len(compressed)} \u6761\u8bb0\u5f55")

        # \u663e\u793a\u524d5\u6761\u793a\u4f8b
        if compressed:
            print("\n      \u524d5\u6761\u793a\u4f8b：")
            for i, item in enumerate(compressed[:5]):
                print(f"        {i + 1}. {item}")
    else:
        print(f"\n[4/5] \u5199\u5165\u6587\u4ef6：{output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('[\n')
            for i, item in enumerate(compressed):
                json.dump(item, f, ensure_ascii=False, separators=(',', ':'))
                if i < len(compressed) - 1:
                    f.write(',\n')
                else:
                    f.write('\n')
            f.write(']\n')

        file_size = output_path.stat().st_size
        print(f"      \u6587\u4ef6\u5927\u5c0f：{file_size / 1024:.2f} KB")

        # \u9a8c\u8bc1\u6587\u4ef6
        print("\n[5/5] \u9a8c\u8bc1\u6587\u4ef6...")
        with open(output_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
            print(f"      \u9a8c\u8bc1\u901a\u8fc7：{len(test_data)} \u6761\u8bb0\u5f55")

    # \u7edf\u8ba1\u4fe1\u606f
    market_stats = {}
    for item in index:
        market = item['market']
        market_stats[market] = market_stats.get(market, 0) + 1

    print(f"\n{'=' * 60}")
    print("\u751f\u6210\u5b8c\u6210！\u5e02\u573a\u5206\u5e03：")
    for market, count in sorted(market_stats.items()):
        print(f"  - {market}: {count} \u53ea")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
