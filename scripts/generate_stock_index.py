#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Index Generation Script

Generate stock index file for frontend autocomplete functionality
Output to apps/dsa-web/public/stocks.index.json

Two-phase strategy:
1. MVP: Use existing STOCK_NAME_MAP
2. Future: Combine with AkShare for complete list

Usage:
    python3 scripts/generate_stock_index.py
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pypinyin import lazy_pinyin
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    print("[Warning] pypinyin not available, pinyin fields will be empty")
    print("[Info] Install with: pip install pypinyin")


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


def generate_stock_index_from_map() -> List[Dict[str, Any]]:
    """
    Generate index from STOCK_NAME_MAP (MVP)

    Returns:
        List of stock index
    """
    from src.data.stock_mapping import STOCK_NAME_MAP

    index = []

    for code, name in STOCK_NAME_MAP.items():
        # Generate pinyin fields.
        pinyin_full = None
        pinyin_abbr = None
        if PYPINYIN_AVAILABLE:
            try:
                normalized_name = normalize_name_for_pinyin(name)
                py = lazy_pinyin(normalized_name)
                pinyin_full = ''.join(py)
                pinyin_abbr = ''.join([p[0] for p in py])
            except Exception:
                pass

        # Determine market and asset type.
        market, asset_type = determine_market_and_type(code)

        # Generate short aliases.
        aliases = generate_aliases(name)

        index.append({
            "canonicalCode": build_canonical_code(code, market),
            "displayCode": code,
            "nameZh": name,
            "pinyinFull": pinyin_full,
            "pinyinAbbr": pinyin_abbr,
            "aliases": aliases,
            "market": market,
            "assetType": asset_type,
            "active": True,
            "popularity": 100,  # Default popularity
        })

    return index


def determine_market_and_type(code: str) -> tuple:
    """
    Determine market and asset type based on stock code

    Args:
        code: Stock code

    Returns:
        Tuple of (market, asset_type)
    """
    if code.isdigit():
        if len(code) == 5:
            # Five digits: likely HK stock or legacy B-share.
            if code.startswith('0') or code.startswith('2'):
                return 'HK', 'stock'
            return 'CN', 'stock'
        elif len(code) == 6:
            # Six digits: A-share universe.
            if code.startswith('6'):
                return 'CN', 'stock'  # Shanghai
            elif code.startswith(('0', '2', '3')):
                return 'CN', 'stock'  # Shenzhen
            elif code.startswith('8'):
                return 'BSE', 'stock'  # Beijing Stock Exchange
            return 'CN', 'stock'
        elif len(code) == 4:
            # Four digits: likely a US symbol or special market code.
            return 'US', 'stock'

    # \u5b57\u6bcd\u4ee3\u7801，\u7f8e\u80a1\u6216\u5176\u4ed6
    return 'US', 'stock'


def market_to_suffix(market: str) -> str:
    """
    Convert market code to suffix

    Args:
        market: Market code

    Returns:
        Market suffix
    """
    suffix_map = {
        'CN': 'SH',  # \u7b80\u5316\u5904\u7406，\u9ed8\u8ba4\u4e0a\u6d77
        'HK': 'HK',
        'US': 'US',
        'INDEX': 'SH',
        'ETF': 'SH',
        'BSE': 'BJ',
    }
    return suffix_map.get(market, 'SH')


def build_canonical_code(code: str, market: str) -> str:
    """
    Generate canonical stock code based on code and market.

    A-shares need to distinguish between SH/SZ/BJ, cannot rely solely on the general CN -> SH mapping.
    """
    if market == 'CN' and code.isdigit() and len(code) == 6:
        # Shanghai Stock Exchange (SH)
        # 60xxxx: Main board, 688xxx: STAR market, 900xxx: B-shares
        if code.startswith(('6', '900')):
            return f"{code}.SH"

        # Shenzhen Stock Exchange (SZ)
        # 00xxxx: Main board, 30xxxx: ChiNext, 20xxxx: B-shares
        if code.startswith(('0', '2', '3')):
            return f"{code}.SZ"

        # Beijing Stock Exchange (BJ)
        # 920xxx: New codes and migrated stock codes after April 2024
        # 43xxxx, 83xxxx, 87xxxx, 88xxxx: Historical/Temporary codes
        # 81xxxx, 82xxxx: Convertible bonds/Preferred stocks
        if code.startswith(('920', '43', '83', '87', '88', '81', '82')):
            return f"{code}.BJ"

    if market == 'BSE' and code.isdigit() and len(code) == 6:
        return f"{code}.BJ"

    return f"{code}.{market_to_suffix(market)}"


def generate_aliases(name: str) -> List[str]:
    """
    Generate stock aliases (abbreviations)

    Args:
        name: Full stock name

    Returns:
        List of aliases
    """
    aliases = []

    # \u5e38\u89c1\u7b80\u79f0\u6620\u5c04
    alias_map = {
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

    if name in alias_map:
        aliases.extend(alias_map[name])

    return aliases


def compress_index(index: List[Dict[str, Any]]) -> List[List]:
    """
    Compress index to array format to reduce file size

    Args:
        index: Original index

    Returns:
        Compressed index
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
    """Main function"""
    # \u89e3\u6790\u547d\u4ee4\u884c\u53c2\u6570
    parser = argparse.ArgumentParser(
        description='\u751f\u6210\u80a1\u7968\u81ea\u52a8\u8865\u5168\u7d22\u5f15\u6587\u4ef6',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
\u793a\u4f8b:
  python3 scripts/generate_stock_index.py              # \u9ed8\u8ba4：\u751f\u6210\u7d22\u5f15\u6587\u4ef6
  python3 scripts/generate_stock_index.py --test       # \u6d4b\u8bd5\u6a21\u5f0f：\u53ea\u8bfb\u53d6\u4e0d\u5199\u5165
  python3 scripts/generate_stock_index.py --test -v    # \u6d4b\u8bd5\u6a21\u5f0f + \u663e\u793a\u8be6\u7ec6\u6570\u636e
        """
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='\u6d4b\u8bd5\u6a21\u5f0f：\u53ea\u8bfb\u53d6\u548c\u9a8c\u8bc1\u6570\u636e，\u4e0d\u5199\u5165\u6587\u4ef6'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='\u8be6\u7ec6\u6a21\u5f0f：\u663e\u793a\u524d10\u6761\u6570\u636e\u9884\u89c8'
    )
    args = parser.parse_args()

    print("\u5f00\u59cb\u751f\u6210\u80a1\u7968\u7d22\u5f15...")

    # \u751f\u6210\u7d22\u5f15（MVP：\u4f7f\u7528\u73b0\u6709\u6620\u5c04）
    index = generate_stock_index_from_map()
    print(f"\u5171\u751f\u6210 {len(index)} \u6761\u7d22\u5f15")

    # \u6309\u5e02\u573a\u7edf\u8ba1
    market_stats = {}
    for item in index:
        market = item['market']
        market_stats[market] = market_stats.get(market, 0) + 1
    print(f"\u5e02\u573a\u5206\u5e03：{market_stats}")

    # \u538b\u7f29\u683c\u5f0f（\u51cf\u5c11\u6587\u4ef6\u5927\u5c0f）
    compressed = compress_index(index)

    # \u6d4b\u8bd5\u6a21\u5f0f：\u4e0d\u5199\u5165\u6587\u4ef6
    if args.test:
        print("\n[\u6d4b\u8bd5\u6a21\u5f0f] \u4e0d\u4f1a\u5199\u5165\u6587\u4ef6")
        print(f"\u9884\u8ba1\u6587\u4ef6\u5927\u5c0f：{len(json.dumps(compressed, ensure_ascii=False, separators=(',', ':'))) / 1024:.2f} KB")

        if args.verbose:
            print("\n\u524d10\u6761\u6570\u636e\u9884\u89c8：")
            for i, item in enumerate(index[:10]):
                print(f"  {i + 1}. {item['canonicalCode']} - {item['nameZh']} ({item['market']})")

        print("\n✓ \u6d4b\u8bd5\u901a\u8fc7，\u6570\u636e\u683c\u5f0f\u6b63\u786e")
        return 0

    # \u8f93\u51fa\u8def\u5f84
    output_path = Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # \u5199\u5165\u6587\u4ef6
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
    print(f"\u7d22\u5f15\u5df2\u751f\u6210：{output_path}")
    print(f"\u6587\u4ef6\u5927\u5c0f：{file_size / 1024:.2f} KB")

    # \u9a8c\u8bc1\u6587\u4ef6\u53ef\u8bfb
    with open(output_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
        print(f"\u9a8c\u8bc1\u901a\u8fc7：{len(test_data)} \u6761\u8bb0\u5f55")

    return 0


if __name__ == "__main__":
    sys.exit(main())
