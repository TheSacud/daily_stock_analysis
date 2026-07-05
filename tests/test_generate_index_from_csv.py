#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test generate_index_from_csv.py
"""

import csv
import json
import pytest
from pathlib import Path
from typing import Dict, List

# Add scripts directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from generate_index_from_csv import (
    extract_symbol_from_ts_code,
    get_stock_name,
    get_us_delist_priority,
    parse_stock_row,
    determine_market,
    generate_aliases,
    normalize_name_for_pinyin,
    normalize_stock_name_for_index,
    generate_pinyin,
    main,
    compress_index,
    build_stock_index,
    load_tushare_data,
    load_akshare_data,
)


class TestExtractSymbol:
    """\u6d4b\u8bd5 Symbol \u63d0\u53d6\u51fd\u6570"""

    def test_a_stock_sz(self):
        """\u6d4b\u8bd5 A\u80a1\u6df1\u5733"""
        result = extract_symbol_from_ts_code("000001.SZ", "CN")
        assert result == "000001"

    def test_a_stock_sh(self):
        """\u6d4b\u8bd5 A\u80a1\u4e0a\u6d77"""
        result = extract_symbol_from_ts_code("600519.SH", "CN")
        assert result == "600519"

    def test_hk_stock(self):
        """\u6d4b\u8bd5\u6e2f\u80a1"""
        result = extract_symbol_from_ts_code("00700.HK", "HK")
        assert result == "00700"

    def test_us_stock(self):
        """\u6d4b\u8bd5\u7f8e\u80a1"""
        result = extract_symbol_from_ts_code("AAPL", "US")
        assert result == "AAPL"

    def test_jp_stock_preserves_suffix(self):
        """\u6d4b\u8bd5\u65e5\u80a1\u4fdd\u7559 Yahoo \u540e\u7f00\u4ee5\u907f\u514d\u88f8\u4ee3\u7801\u51b2\u7a81"""
        result = extract_symbol_from_ts_code("7203.T", "JP")
        assert result == "7203.T"

    def test_kr_stock_preserves_suffix(self):
        """\u6d4b\u8bd5\u97e9\u80a1\u4fdd\u7559 Yahoo \u540e\u7f00\u4ee5\u907f\u514d\u88f8\u4ee3\u7801\u51b2\u7a81"""
        result = extract_symbol_from_ts_code("005930.KS", "KR")
        assert result == "005930.KS"

    def test_empty_ts_code(self):
        """\u6d4b\u8bd5\u7a7a ts_code"""
        result = extract_symbol_from_ts_code("", "CN")
        assert result is None

    def test_none_ts_code(self):
        """\u6d4b\u8bd5 None ts_code"""
        result = extract_symbol_from_ts_code(None, "CN")
        assert result is None


class TestDetermineMarket:
    """\u6d4b\u8bd5\u5e02\u573a\u5224\u65ad\u51fd\u6570"""

    def test_a_stock_sz(self):
        """\u6d4b\u8bd5 A\u80a1\u6df1\u5733"""
        result = determine_market("000001.SZ")
        assert result == "CN"

    def test_a_stock_sh(self):
        """\u6d4b\u8bd5 A\u80a1\u4e0a\u6d77"""
        result = determine_market("600519.SH")
        assert result == "CN"

    def test_hk_stock(self):
        """\u6d4b\u8bd5\u6e2f\u80a1"""
        result = determine_market("00700.HK")
        assert result == "HK"

    def test_bse_stock(self):
        """\u6d4b\u8bd5\u5317\u4ea4\u6240"""
        result = determine_market("832566.BJ")
        assert result == "BSE"

    def test_us_stock(self):
        """\u6d4b\u8bd5\u7f8e\u80a1"""
        result = determine_market("AAPL")
        assert result == "US"

    def test_us_stock_tesla(self):
        """\u6d4b\u8bd5\u7f8e\u80a1\u7279\u65af\u62c9"""
        result = determine_market("TSLA")
        assert result == "US"

    def test_us_stock_with_dot_suffix(self):
        """\u6d4b\u8bd5\u7f8e\u80a1\u5e26\u70b9\u53f7\u540e\u7f00（BRK.B）"""
        result = determine_market("BRK.B")
        assert result == "US"

    def test_us_stock_class_a(self):
        """\u6d4b\u8bd5\u7f8e\u80a1 A \u7c7b\u80a1（GOOG.A）"""
        result = determine_market("GOOG.A")
        assert result == "US"

    def test_us_stock_units(self):
        """\u6d4b\u8bd5\u7f8e\u80a1 Unit（AAPL.U）"""
        result = determine_market("AAPL.U")
        assert result == "US"

    def test_jp_stock_with_yahoo_suffix(self):
        """\u6d4b\u8bd5\u65e5\u80a1 Yahoo \u540e\u7f00"""
        result = determine_market("7203.T")
        assert result == "JP"

    def test_kr_kospi_stock_with_yahoo_suffix(self):
        """\u6d4b\u8bd5\u97e9\u80a1 KOSPI Yahoo \u540e\u7f00"""
        result = determine_market("005930.KS")
        assert result == "KR"

    def test_kr_kosdaq_stock_with_yahoo_suffix(self):
        """\u6d4b\u8bd5\u97e9\u80a1 KOSDAQ Yahoo \u540e\u7f00"""
        result = determine_market("035720.KQ")
        assert result == "KR"


class TestGetStockName:
    """\u6d4b\u8bd5\u80a1\u7968\u540d\u79f0\u83b7\u53d6\u51fd\u6570"""

    def test_cn_stock_name(self):
        """\u6d4b\u8bd5 A\u80a1\u4f7f\u7528 name \u5b57\u6bb5"""
        row = {'name': '\u5e73\u5b89\u94f6\u884c', 'enname': 'Ping An Bank'}
        result = get_stock_name(row, 'CN')
        assert result == '\u5e73\u5b89\u94f6\u884c'

    def test_hk_stock_name(self):
        """\u6d4b\u8bd5\u6e2f\u80a1\u4f7f\u7528 name \u5b57\u6bb5"""
        row = {'name': '\u817e\u8baf\u63a7\u80a1', 'enname': 'Tencent'}
        result = get_stock_name(row, 'HK')
        assert result == '\u817e\u8baf\u63a7\u80a1'

    def test_us_stock_name(self):
        """\u6d4b\u8bd5\u7f8e\u80a1\u4f7f\u7528 enname \u5b57\u6bb5"""
        row = {'name': '\u82f9\u679c', 'enname': 'Apple Inc.'}
        result = get_stock_name(row, 'US')
        assert result == 'Apple Inc.'

    def test_empty_name(self):
        """\u6d4b\u8bd5\u7a7a\u540d\u79f0"""
        row = {'name': '', 'enname': ''}
        result = get_stock_name(row, 'CN')
        assert result is None

    def test_cn_stock_name_strips_ex_rights_prefix(self):
        """\u6d4b\u8bd5 A\u80a1\u9664\u6743\u9664\u606f\u77ed\u671f\u524d\u7f00\u4e0d\u4f1a\u5199\u5165\u957f\u671f\u7d22\u5f15\u540d\u79f0"""
        row = {'name': 'XD\u897f\u85cf\u836f', 'enname': ''}
        result = get_stock_name(row, 'CN')
        assert result == '\u897f\u85cf\u836f'

    def test_cn_stock_name_preserves_new_stock_prefix(self):
        """\u6d4b\u8bd5 A\u80a1\u65b0\u80a1\u524d\u7f00\u4fdd\u7559，\u7b49\u5f85\u540e\u7eed\u6570\u636e\u5305\u5237\u65b0\u81ea\u7136\u6d88\u5931"""
        row = {'name': 'N\u60e0\u5eb7', 'enname': ''}
        result = get_stock_name(row, 'CN')
        assert result == 'N\u60e0\u5eb7'


class TestDataCleaning:
    """\u6d4b\u8bd5\u6570\u636e\u6e05\u6d17\u903b\u8f91"""

    def test_valid_cn_stock(self):
        """\u6d4b\u8bd5\u6709\u6548\u7684 A\u80a1\u8bb0\u5f55"""
        row = {
            'ts_code': '000001.SZ',
            'symbol': '000001',
            'name': '\u5e73\u5b89\u94f6\u884c'
        }
        result = parse_stock_row(row, 'CN')
        assert result is not None
        assert result['ts_code'] == '000001.SZ'
        assert result['symbol'] == '000001'
        assert result['name'] == '\u5e73\u5b89\u94f6\u884c'
        assert result['market'] == 'CN'

    def test_valid_hk_stock(self):
        """\u6d4b\u8bd5\u6709\u6548\u7684\u6e2f\u80a1\u8bb0\u5f55"""
        row = {
            'ts_code': '00700.HK',
            'name': '\u817e\u8baf\u63a7\u80a1',
            'enname': 'Tencent'
        }
        result = parse_stock_row(row, 'HK')
        assert result is not None
        assert result['ts_code'] == '00700.HK'
        assert result['symbol'] == '00700'
        assert result['name'] == '\u817e\u8baf\u63a7\u80a1'
        assert result['market'] == 'HK'

    def test_valid_us_stock(self):
        """\u6d4b\u8bd5\u6709\u6548\u7684\u7f8e\u80a1\u8bb0\u5f55"""
        row = {
            'ts_code': 'AAPL',
            'name': '\u82f9\u679c',
            'enname': 'Apple Inc.'
        }
        result = parse_stock_row(row, 'US')
        assert result is not None
        assert result['ts_code'] == 'AAPL'
        assert result['symbol'] == 'AAPL'
        assert result['name'] == 'Apple Inc.'
        assert result['market'] == 'US'

    def test_valid_us_stock_with_dot_suffix(self):
        """\u6d4b\u8bd5\u6709\u6548\u7684\u7f8e\u80a1\u8bb0\u5f55（\u5e26\u70b9\u53f7\u540e\u7f00，\u5982 BRK.B）"""
        row = {
            'ts_code': 'BRK.B',
            'name': '',
            'enname': "BERKSHIRE HATHAWAY 'B'"
        }
        result = parse_stock_row(row, None)
        assert result is not None
        assert result['ts_code'] == 'BRK.B'
        assert result['symbol'] == 'BRK.B'
        assert result['name'] == "BERKSHIRE HATHAWAY 'B'"
        assert result['market'] == 'US'

    def test_valid_jp_stock_with_seed_aliases(self):
        """\u6d4b\u8bd5\u6709\u6548\u7684\u65e5\u80a1\u79cd\u5b50\u8bb0\u5f55"""
        row = {
            'ts_code': '7203.T',
            'name': '\u4e30\u7530\u6c7d\u8f66',
            'enname': 'Toyota Motor Corporation',
            'aliases': 'Toyota|Toyota Motor|\u4e30\u7530'
        }
        result = parse_stock_row(row, 'JP')
        assert result is not None
        assert result['ts_code'] == '7203.T'
        assert result['symbol'] == '7203.T'
        assert result['name'] == '\u4e30\u7530\u6c7d\u8f66'
        assert result['market'] == 'JP'
        assert result['aliases'] == ['Toyota', 'Toyota Motor', '\u4e30\u7530']

    def test_valid_kr_stock_with_seed_aliases(self):
        """\u6d4b\u8bd5\u6709\u6548\u7684\u97e9\u80a1\u79cd\u5b50\u8bb0\u5f55"""
        row = {
            'ts_code': '005930.KS',
            'name': '\u4e09\u661f\u7535\u5b50',
            'enname': 'Samsung Electronics',
            'aliases': 'Samsung|Samsung Electronics|\u4e09\u661f'
        }
        result = parse_stock_row(row, 'KR')
        assert result is not None
        assert result['ts_code'] == '005930.KS'
        assert result['symbol'] == '005930.KS'
        assert result['name'] == '\u4e09\u661f\u7535\u5b50'
        assert result['market'] == 'KR'
        assert result['aliases'] == ['Samsung', 'Samsung Electronics', '\u4e09\u661f']

    def test_us_dummy_filtered(self):
        """\u6d4b\u8bd5\u7f8e\u80a1 DUMMY \u8bb0\u5f55\u88ab\u8fc7\u6ee4"""
        row = {
            'ts_code': 'DUMMY001',
            'name': '\u6d4b\u8bd5',
            'enname': 'DUMMY Test Stock'
        }
        result = parse_stock_row(row, 'US')
        assert result is None

    def test_us_dummy_case_insensitive(self):
        """\u6d4b\u8bd5 DUMMY \u8fc7\u6ee4\u4e0d\u533a\u5206\u5927\u5c0f\u5199"""
        row = {
            'ts_code': 'DUMMY002',
            'name': '\u6d4b\u8bd5',
            'enname': 'dummy test stock'
        }
        result = parse_stock_row(row, 'US')
        assert result is None

    def test_empty_ts_code(self):
        """\u6d4b\u8bd5\u7a7a ts_code \u88ab\u8fc7\u6ee4"""
        row = {
            'ts_code': '',
            'symbol': '000001',
            'name': '\u5e73\u5b89\u94f6\u884c'
        }
        result = parse_stock_row(row, 'CN')
        assert result is None

    def test_empty_name(self):
        """\u6d4b\u8bd5\u7a7a\u540d\u79f0\u88ab\u8fc7\u6ee4"""
        row = {
            'ts_code': '000001.SZ',
            'symbol': '000001',
            'name': ''
        }
        result = parse_stock_row(row, 'CN')
        assert result is None

    def test_us_empty_enname(self):
        """\u6d4b\u8bd5\u7f8e\u80a1\u7a7a enname \u88ab\u8fc7\u6ee4"""
        row = {
            'ts_code': 'AAPL',
            'name': '\u82f9\u679c',
            'enname': ''
        }
        result = parse_stock_row(row, 'US')
        assert result is None

    def test_us_delist_priority_prefers_blank_over_nat(self):
        """\u6d4b\u8bd5\u7f8e\u80a1\u53bb\u91cd\u4f18\u5148\u7ea7：\u7a7a delist_date \u4f18\u5148\u4e8e NaT"""
        assert get_us_delist_priority({'delist_date': ''}) == 2
        assert get_us_delist_priority({'delist_date': 'NaT'}) == 1
        assert get_us_delist_priority({'delist_date': '20250131'}) == 0


class TestNormalizeStockNameForIndex:
    """\u6d4b\u8bd5\u7d22\u5f15\u540d\u79f0\u5f52\u4e00\u5316"""

    def test_strips_a_share_ex_rights_prefixes(self):
        assert normalize_stock_name_for_index('XD\u897f\u85cf\u836f', 'CN') == '\u897f\u85cf\u836f'
        assert normalize_stock_name_for_index('XR\u793a\u4f8b\u80a1', 'CN') == '\u793a\u4f8b\u80a1'
        assert normalize_stock_name_for_index('DR\u7f57\u66fc\u80a1', 'CN') == '\u7f57\u66fc\u80a1'
        assert normalize_stock_name_for_index('XD\u6731\u8001\u516d', 'BSE') == '\u6731\u8001\u516d'

    def test_preserves_a_share_new_stock_and_st_prefixes(self):
        assert normalize_stock_name_for_index('N\u60e0\u5eb7', 'CN') == 'N\u60e0\u5eb7'
        assert normalize_stock_name_for_index('C\u5929\u6d77', 'CN') == 'C\u5929\u6d77'
        assert normalize_stock_name_for_index('ST\u6d77\u738b', 'CN') == 'ST\u6d77\u738b'
        assert normalize_stock_name_for_index('*ST\u7f8e\u4e3d', 'CN') == '*ST\u7f8e\u4e3d'

    def test_does_not_strip_other_markets(self):
        assert normalize_stock_name_for_index('DRAGONFLY ENERGY', 'US') == 'DRAGONFLY ENERGY'
        assert normalize_stock_name_for_index('XD\u6e2f\u80a1\u793a\u4f8b', 'HK') == 'XD\u6e2f\u80a1\u793a\u4f8b'


class TestAliases:
    """\u6d4b\u8bd5\u522b\u540d\u751f\u6210\u51fd\u6570"""

    def test_cn_aliases(self):
        """\u6d4b\u8bd5 A\u80a1\u522b\u540d"""
        result = generate_aliases('\u8d35\u5dde\u8305\u53f0', 'CN')
        assert '\u8305\u53f0' in result

    def test_hk_aliases(self):
        """\u6d4b\u8bd5\u6e2f\u80a1\u522b\u540d"""
        result = generate_aliases('\u817e\u8baf\u63a7\u80a1', 'HK')
        assert '\u817e\u8baf' in result or 'Tencent' in result

    def test_us_aliases(self):
        """\u6d4b\u8bd5\u7f8e\u80a1\u522b\u540d"""
        result = generate_aliases('Apple Inc.', 'US')
        assert 'Apple' in result or 'AAPL' in result

    def test_no_aliases(self):
        """\u6d4b\u8bd5\u65e0\u522b\u540d\u7684\u60c5\u51b5"""
        result = generate_aliases('\u672a\u77e5\u80a1\u7968', 'CN')
        assert result == []


class TestOutputFormat:
    """\u6d4b\u8bd5\u8f93\u51fa\u683c\u5f0f"""

    def test_compress_index_field_order(self):
        """\u6d4b\u8bd5\u538b\u7f29\u683c\u5f0f\u7684\u5b57\u6bb5\u987a\u5e8f"""
        index = [{
            "canonicalCode": "000001.SZ",
            "displayCode": "000001",
            "nameZh": "\u5e73\u5b89\u94f6\u884c",
            "pinyinFull": "pinganyinhang",
            "pinyinAbbr": "pyyh",
            "aliases": ["\u5e73\u94f6"],
            "market": "CN",
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        }]

        compressed = compress_index(index)

        assert len(compressed) == 1
        item = compressed[0]

        # \u9a8c\u8bc1\u5b57\u6bb5\u987a\u5e8f
        assert item[0] == "000001.SZ"      # canonicalCode
        assert item[1] == "000001"         # displayCode
        assert item[2] == "\u5e73\u5b89\u94f6\u884c"       # nameZh
        assert item[3] == "pinganyinhang"  # pinyinFull
        assert item[4] == "pyyh"           # pinyinAbbr
        assert item[5] == ["\u5e73\u94f6"]         # aliases
        assert item[6] == "CN"             # market
        assert item[7] == "stock"          # assetType
        assert item[8] == True             # active
        assert item[9] == 100              # popularity

    def test_compress_index_field_count(self):
        """\u6d4b\u8bd5\u538b\u7f29\u683c\u5f0f\u7684\u5b57\u6bb5\u6570\u91cf"""
        index = [{
            "canonicalCode": "AAPL",
            "displayCode": "AAPL",
            "nameZh": "Apple Inc.",
            "pinyinFull": None,
            "pinyinAbbr": None,
            "aliases": [],
            "market": "US",
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        }]

        compressed = compress_index(index)
        assert len(compressed[0]) == 10  # 10\u4e2a\u5b57\u6bb5

    def test_json_serialization(self):
        """\u6d4b\u8bd5 JSON \u5e8f\u5217\u5316"""
        index = [{
            "canonicalCode": "00700.HK",
            "displayCode": "00700",
            "nameZh": "\u817e\u8baf\u63a7\u80a1",
            "pinyinFull": "xunxiongkonggu",
            "pinyinAbbr": "xxkg",
            "aliases": ["\u817e\u8baf"],
            "market": "HK",
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        }]

        compressed = compress_index(index)

        # \u5e94\u8be5\u80fd\u6210\u529f\u5e8f\u5217\u5316\u4e3a JSON
        json_str = json.dumps(compressed, ensure_ascii=False)
        assert json_str is not None

        # \u5e94\u8be5\u80fd\u6210\u529f\u53cd\u5e8f\u5217\u5316
        loaded = json.loads(json_str)
        assert len(loaded) == 1


class TestIntegration:
    """\u96c6\u6210\u6d4b\u8bd5"""

    def test_full_workflow_tushare(self, tmp_path):
        """\u6d4b\u8bd5\u5b8c\u6574\u7684 Tushare \u5de5\u4f5c\u6d41"""
        # \u521b\u5efa\u6d4b\u8bd5 CSV \u6587\u4ef6
        a_csv = tmp_path / 'stock_list_a.csv'
        with open(a_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'symbol', 'name'])
            writer.writeheader()
            writer.writerow({
                'ts_code': '000001.SZ',
                'symbol': '000001',
                'name': '\u5e73\u5b89\u94f6\u884c'
            })

        hk_csv = tmp_path / 'stock_list_hk.csv'
        with open(hk_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'name', 'enname'])
            writer.writeheader()
            writer.writerow({
                'ts_code': '00700.HK',
                'name': '\u817e\u8baf\u63a7\u80a1',
                'enname': 'Tencent'
            })

        us_csv = tmp_path / 'stock_list_us.csv'
        with open(us_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'name', 'enname'])
            writer.writeheader()
            writer.writerow({
                'ts_code': 'AAPL',
                'name': '\u82f9\u679c',
                'enname': 'Apple Inc.'
            })

        jp_csv = tmp_path / 'stock_list_jp.csv'
        with open(jp_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'name', 'enname', 'aliases'])
            writer.writeheader()
            writer.writerow({
                'ts_code': '7203.T',
                'name': '\u4e30\u7530\u6c7d\u8f66',
                'enname': 'Toyota Motor Corporation',
                'aliases': 'Toyota|\u4e30\u7530'
            })

        kr_csv = tmp_path / 'stock_list_kr.csv'
        with open(kr_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'name', 'enname', 'aliases'])
            writer.writeheader()
            writer.writerow({
                'ts_code': '005930.KS',
                'name': '\u4e09\u661f\u7535\u5b50',
                'enname': 'Samsung Electronics',
                'aliases': 'Samsung|\u4e09\u661f'
            })

        # \u52a0\u8f7d\u6570\u636e
        stocks = load_tushare_data(tmp_path)

        # \u9a8c\u8bc1\u6570\u636e
        assert len(stocks) == 5

        # \u6784\u5efa\u7d22\u5f15
        index = build_stock_index(stocks)

        # \u9a8c\u8bc1\u7d22\u5f15
        assert len(index) == 5
        assert next(item for item in index if item['canonicalCode'] == '7203.T')['aliases'] == ['Toyota', '\u4e30\u7530']
        assert next(item for item in index if item['canonicalCode'] == '005930.KS')['aliases'] == ['Samsung', '\u4e09\u661f']

        # \u538b\u7f29\u7d22\u5f15
        compressed = compress_index(index)

        # \u9a8c\u8bc1\u538b\u7f29
        assert len(compressed) == 5

        # \u9a8c\u8bc1\u5b57\u6bb5\u6570\u91cf
        for item in compressed:
            assert len(item) == 10

    def test_market_distribution(self, tmp_path):
        """\u6d4b\u8bd5\u5e02\u573a\u5206\u5e03\u7edf\u8ba1"""
        # \u521b\u5efa\u6d4b\u8bd5\u6570\u636e
        csv_file = tmp_path / 'stock_list_a.csv'
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'symbol', 'name'])
            writer.writeheader()
            writer.writerow({'ts_code': '000001.SZ', 'symbol': '000001', 'name': '\u5e73\u5b89\u94f6\u884c'})
            writer.writerow({'ts_code': '600519.SH', 'symbol': '600519', 'name': '\u8d35\u5dde\u8305\u53f0'})
            writer.writerow({'ts_code': '832566.BJ', 'symbol': '832566', 'name': '\u6893\u649e\u79d1\u6280'})

        stocks = load_tushare_data(tmp_path)
        index = build_stock_index(stocks)

        # \u7edf\u8ba1\u5e02\u573a\u5206\u5e03
        market_stats = {}
        for item in index:
            market = item['market']
            market_stats[market] = market_stats.get(market, 0) + 1

        # \u9a8c\u8bc1\u7edf\u8ba1
        assert market_stats.get('CN', 0) == 2  # SZ, SH
        assert market_stats.get('BSE', 0) == 1  # BJ

    def test_us_reused_symbols_are_deduplicated(self, tmp_path):
        """\u6d4b\u8bd5\u7f8e\u80a1\u590d\u7528 ticker \u5728\u52a0\u8f7d\u65f6\u4f1a\u5148\u53bb\u91cd"""
        us_csv = tmp_path / 'stock_list_us.csv'
        with open(us_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['ts_code', 'name', 'enname', 'list_date', 'delist_date']
            )
            writer.writeheader()
            writer.writerow({
                'ts_code': 'B',
                'name': '',
                'enname': 'BARNES GROUP',
                'list_date': '19631014',
                'delist_date': 'NaT',
            })
            writer.writerow({
                'ts_code': 'B',
                'name': '',
                'enname': 'BARRICK MINING (NYS)',
                'list_date': '19850213',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'DOC',
                'name': '',
                'enname': 'HEALTHPEAK PROPERTIES',
                'list_date': '19850523',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'DOC',
                'name': '',
                'enname': 'PHYSICIANS REALTY TST.',
                'list_date': '20130719',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'SPWR',
                'name': '',
                'enname': 'COMPLETE SOLARIA',
                'list_date': '20210419',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'SPWR',
                'name': '',
                'enname': 'SUNPOWER',
                'list_date': '20051109',
                'delist_date': 'NaT',
            })

        stocks = load_tushare_data(tmp_path)

        assert len(stocks) == 3
        assert {stock['ts_code'] for stock in stocks} == {'B', 'DOC', 'SPWR'}
        assert next(stock for stock in stocks if stock['ts_code'] == 'B')['name'] == 'BARRICK MINING (NYS)'
        assert next(stock for stock in stocks if stock['ts_code'] == 'DOC')['name'] == 'HEALTHPEAK PROPERTIES'
        assert next(stock for stock in stocks if stock['ts_code'] == 'SPWR')['name'] == 'COMPLETE SOLARIA'


class TestPinyin:
    """\u6d4b\u8bd5\u62fc\u97f3\u751f\u6210"""

    def test_normalize_name(self):
        """\u6d4b\u8bd5\u540d\u79f0\u6807\u51c6\u5316"""
        # \u6d4b\u8bd5 ST \u524d\u7f00\u53bb\u9664
        result = normalize_name_for_pinyin('*ST\u5e73\u5b89')
        assert 'ST' not in result

        # \u6d4b\u8bd5 N \u524d\u7f00\u53bb\u9664
        result = normalize_name_for_pinyin('N\u5e73\u5b89\u94f6\u884c')
        assert 'N' not in result

    def test_generate_pinyin(self):
        """\u6d4b\u8bd5\u62fc\u97f3\u751f\u6210"""
        pinyin_full, pinyin_abbr = generate_pinyin('\u5e73\u5b89\u94f6\u884c')
        assert pinyin_full == 'pinganyinhang'
        assert pinyin_abbr == 'payh'

    def test_generate_pinyin_requires_dependency(self, monkeypatch):
        """\u6d4b\u8bd5\u7f3a\u5c11 pypinyin \u65f6\u4e0d\u4f1a\u751f\u6210\u964d\u7ea7\u62fc\u97f3\u5b57\u6bb5"""
        import generate_index_from_csv

        monkeypatch.setattr(generate_index_from_csv, 'PYPINYIN_AVAILABLE', False)

        with pytest.raises(RuntimeError, match='pypinyin is required'):
            generate_index_from_csv.generate_pinyin('\u5e73\u5b89\u94f6\u884c')

    def test_main_fails_without_pypinyin(self, monkeypatch):
        """\u6d4b\u8bd5\u6b63\u5f0f\u751f\u6210\u7d22\u5f15\u524d\u5fc5\u987b\u5177\u5907 pypinyin"""
        import generate_index_from_csv

        monkeypatch.setattr(generate_index_from_csv, 'PYPINYIN_AVAILABLE', False)
        monkeypatch.setattr(sys, 'argv', ['generate_index_from_csv.py'])

        assert main() == 1
