#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare \u80a1\u7968\u5217\u8868\u83b7\u53d6\u811a\u672c

\u4ece Tushare Pro \u83b7\u53d6 A\u80a1、\u6e2f\u80a1、\u7f8e\u80a1\u5217\u8868\u4fe1\u606f，\u4fdd\u5b58\u4e3a CSV \u6587\u4ef6

\u4f7f\u7528\u65b9\u6cd5：
    python3 scripts/fetch_tushare_stock_list.py
    python3 scripts/fetch_tushare_stock_list.py --a-rk

\u73af\u5883\u8981\u6c42：
    - \u9700\u8981\u5728 .env \u4e2d\u914d\u7f6e TUSHARE_TOKEN
    - \u9700\u8981\u5b89\u88c5 tushare: pip install tushare
    - \u8d26\u53f7\u79ef\u5206\u8981\u6c42：
        * A\u80a1/\u6e2f\u80a1：2000\u79ef\u5206
        * \u7f8e\u80a1：120\u79ef\u5206\u8bd5\u7528，5000\u79ef\u5206\u6b63\u5f0f\u6743\u9650

\u8f93\u51fa\u6587\u4ef6：
    - data/stock_list_a.csv      A\u80a1\u5217\u8868（--a-rk \u65f6\u4f1a\u8986\u76d6\u4e3a\u4fee\u6b63\u540e\u540d\u79f0）
    - data/stock_list_hk.csv     \u6e2f\u80a1\u5217\u8868
    - data/stock_list_us.csv     \u7f8e\u80a1\u5217\u8868
    - data/README_stock_list.md  \u6570\u636e\u8bf4\u660e\u6587\u6863
"""

import argparse
import os
import sys
import time
import random
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

import pandas as pd
from dotenv import load_dotenv

# \u6dfb\u52a0\u9879\u76ee\u6839\u76ee\u5f55\u5230\u8def\u5f84
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tushare as ts
except ImportError:
    print("[\u9519\u8bef] \u672a\u5b89\u88c5 tushare \u5e93")
    print("\u8bf7\u6267\u884c: pip install tushare")
    sys.exit(1)


# \u914d\u7f6e
load_dotenv()

TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN')
OUTPUT_DIR = Path(__file__).parent.parent / "data"
PAGE_SIZE = 5000  # \u7f8e\u80a1\u6bcf\u9875\u8bfb\u53d6\u6570\u91cf（API \u6700\u59276000，\u8bbe\u7f6e5000\u7559\u4f59\u91cf）
SLEEP_MIN = 5     # \u6700\u5c0f\u7761\u7720\u65f6\u95f4（\u79d2）
SLEEP_MAX = 10    # \u6700\u5927\u7761\u7720\u65f6\u95f4（\u79d2）
A_RK_BATCH_SIZE = 200
A_RK_FIELDS = "ts_code,name,close,pre_close,trade_time"
A_RK_NAME_PREFIX_RE = re.compile(r"^(XD|XR|DR|N|C)")


def get_tushare_api() -> Optional[ts.pro_api]:
    """
    \u83b7\u53d6 Tushare API \u5b9e\u4f8b

    Returns:
        Tushare API \u5b9e\u4f8b，\u5931\u8d25\u8fd4\u56de None
    """
    if not TUSHARE_TOKEN:
        print("[\u9519\u8bef] \u672a\u627e\u5230 TUSHARE_TOKEN")
        print("\u8bf7\u5728 .env \u6587\u4ef6\u4e2d\u914d\u7f6e: TUSHARE_TOKEN=\u4f60\u7684token")
        return None

    try:
        api = ts.pro_api(TUSHARE_TOKEN)
        # \u6d4b\u8bd5\u8fde\u63a5
        api.trade_cal(exchange='SSE', start_date='20240101', end_date='20240101')
        print("✓ Tushare API \u8fde\u63a5\u6210\u529f")
        return api
    except Exception as e:
        print(f"[\u9519\u8bef] Tushare API \u8fde\u63a5\u5931\u8d25: {e}")
        print("\u8bf7\u68c0\u67e5：")
        print("  1. TUSHARE_TOKEN \u662f\u5426\u6b63\u786e")
        print("  2. \u8d26\u53f7\u79ef\u5206\u662f\u5426\u8db3\u591f（A\u80a1/\u6e2f\u80a1\u9700\u89812000\u79ef\u5206）")
        return None


def random_sleep(min_seconds: int = SLEEP_MIN, max_seconds: int = SLEEP_MAX):
    """
    \u968f\u673a\u7761\u7720，\u907f\u514d\u9891\u7e41\u8bf7\u6c42

    Args:
        min_seconds: \u6700\u5c0f\u7761\u7720\u65f6\u95f4
        max_seconds: \u6700\u5927\u7761\u7720\u65f6\u95f4
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    print(f"  ⏱  \u4f11\u606f {sleep_time:.1f} \u79d2...")
    time.sleep(sleep_time)


def fetch_a_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """
    \u83b7\u53d6 A\u80a1\u5217\u8868

    \u63a5\u53e3：stock_basic
    \u9650\u91cf：\u5355\u6b21\u6700\u591a6000\u884c（\u8986\u76d6\u5168\u5e02\u573aA\u80a1）

    Args:
        api: Tushare API \u5b9e\u4f8b

    Returns:
        A\u80a1\u6570\u636e DataFrame，\u5931\u8d25\u8fd4\u56de None
    """
    print("\n[1/3] \u6b63\u5728\u83b7\u53d6 A\u80a1\u5217\u8868...")

    try:
        # \u83b7\u53d6\u6240\u6709\u6b63\u5e38\u4e0a\u5e02\u7684\u80a1\u7968
        df = api.stock_basic(
            exchange='',        # \u7a7a：\u5168\u90e8\u4ea4\u6613\u6240
            list_status='L',    # L: \u4e0a\u5e02, D: \u9000\u5e02, P: \u6682\u505c\u4e0a\u5e02
            fields='ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type'
        )

        if df is not None and len(df) > 0:
            print(f"✓ A\u80a1\u5217\u8868\u83b7\u53d6\u6210\u529f，\u5171 {len(df)} \u53ea\u80a1\u7968")
            print("  - \u4ea4\u6613\u6240\u5206\u5e03：")
            for exchange, count in df['exchange'].value_counts().items():
                print(f"    {exchange}: {count} \u53ea")
            return df
        else:
            print("[\u9519\u8bef] A\u80a1\u6570\u636e\u4e3a\u7a7a")
            return None

    except Exception as e:
        print(f"[\u9519\u8bef] \u83b7\u53d6 A\u80a1\u5217\u8868\u5931\u8d25: {e}")
        return None


def should_fix_a_stock_name(name: str) -> bool:
    """
    \u5224\u65ad A \u80a1\u540d\u79f0\u662f\u5426\u5c5e\u4e8e\u9700\u8981\u4fee\u6b63\u7684\u72b6\u6001\u540d。

    \u4e3b\u8981\u8986\u76d6\u65b0\u80a1、\u9664\u6743\u9664\u606f\u7b49\u524d\u7f00：
    XD / XR / DR / N / C
    """
    if name is None:
        return False

    text = str(name).strip()
    if not text or text.lower() in {"nan", "none"}:
        return False

    return bool(A_RK_NAME_PREFIX_RE.match(text))


def chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    """\u5c06\u5217\u8868\u6309\u56fa\u5b9a\u5927\u5c0f\u5207\u7247。"""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def fetch_rt_k_names(api: ts.pro_api, ts_codes: List[str]) -> Dict[str, str]:
    """
    \u6279\u91cf\u83b7\u53d6 rt_k \u8fd4\u56de\u7684\u80a1\u7968\u540d\u79f0。

    \u53c2\u8003\u5b98\u65b9\u6587\u6863：
    https://tushare.pro/wctapi/documents/372.md

    rt_k \u662f A \u80a1\u5b9e\u65f6\u65e5\u7ebf\u63a5\u53e3，\u652f\u6301\u6309\u80a1\u7968\u4ee3\u7801\u548c\u80a1\u7968\u4ee3\u7801\u901a\u914d\u7b26\u63d0\u53d6
    \u5b9e\u65f6\u65e5 K \u7ebf\u884c\u60c5。\u672c\u811a\u672c\u53ea\u628a\u5b83\u7528\u4f5c\u540d\u79f0\u56de\u586b\u7684\u8f85\u52a9\u6765\u6e90，\u4fee\u6b63
    stock_basic \u4e2d\u8fd4\u56de\u7684\u77ed\u671f\u4ea4\u6613\u72b6\u6001\u524d\u7f00\u540d\u79f0。
    """
    if not ts_codes:
        return {}

    name_map: Dict[str, str] = {}
    batches = chunk_list(ts_codes, A_RK_BATCH_SIZE)

    print(f"\n[rt_k] \u5f85\u4fee\u6b63\u80a1\u7968\u6570：{len(ts_codes)}，\u5206 {len(batches)} \u6279\u83b7\u53d6...")

    for index, batch in enumerate(batches, start=1):
        ts_code_param = ",".join(batch)
        print(f"  [rt_k] \u7b2c {index}/{len(batches)} \u6279：{len(batch)} \u53ea\u80a1\u7968")

        try:
            df = api.rt_k(ts_code=ts_code_param, fields=A_RK_FIELDS)
        except Exception as e:
            print(f"  [\u8b66\u544a] rt_k \u6279\u6b21 {index} \u83b7\u53d6\u5931\u8d25: {e}")
            continue

        if df is None or len(df) == 0:
            print(f"  [\u8b66\u544a] rt_k \u6279\u6b21 {index} \u65e0\u8fd4\u56de\u6570\u636e")
            continue

        for _, row in df.iterrows():
            code_value = row.get("ts_code", "")
            name_value = row.get("name", "")

            if pd.isna(code_value) or pd.isna(name_value):
                continue

            code = str(code_value).strip()
            name = str(name_value).strip()
            if code and name and code.lower() not in {"nan", "none"} and name.lower() not in {"nan", "none"}:
                name_map[code] = name

        if index < len(batches):
            random_sleep(1, 2)

    print(f"[rt_k] \u6210\u529f\u83b7\u53d6 {len(name_map)} \u6761\u540d\u79f0\u6620\u5c04")
    return name_map


def fix_a_stock_names_with_rt_k(api: ts.pro_api, df: pd.DataFrame) -> pd.DataFrame:
    """
    \u4f7f\u7528 rt_k \u4fee\u6b63 A \u80a1\u540d\u79f0。

    \u4ec5\u5bf9\u540d\u79f0\u5e26\u6709 XD / XR / DR / N / C \u524d\u7f00\u7684\u80a1\u7968\u8fdb\u884c\u6821\u6b63。
    """
    if df is None or len(df) == 0:
        return df

    if "name" not in df.columns or "ts_code" not in df.columns:
        print("[\u8b66\u544a] A\u80a1\u6570\u636e\u7f3a\u5c11 ts_code/name \u5217，\u8df3\u8fc7 rt_k \u540d\u79f0\u4fee\u6b63")
        return df

    fix_mask = df["name"].astype(str).map(should_fix_a_stock_name)
    fix_df = df.loc[fix_mask, ["ts_code", "name"]].copy()

    if fix_df.empty:
        print("[rt_k] \u672a\u53d1\u73b0\u9700\u8981\u4fee\u6b63\u7684 A \u80a1\u540d\u79f0")
        return df

    ts_codes = fix_df["ts_code"].astype(str).tolist()
    print(f"[rt_k] \u53d1\u73b0 {len(ts_codes)} \u53ea\u5f85\u4fee\u6b63 A \u80a1：")
    print("  " + ", ".join(ts_codes[:20]) + (" ..." if len(ts_codes) > 20 else ""))

    name_map = fetch_rt_k_names(api, ts_codes)
    if not name_map:
        print("[\u8b66\u544a] rt_k \u672a\u8fd4\u56de\u53ef\u7528\u540d\u79f0，\u4fdd\u7559\u539f\u59cb A \u80a1\u540d\u79f0")
        return df

    fixed_df = df.copy()
    fixed_count = 0
    for code, new_name in name_map.items():
        if not new_name:
            continue
        match_index = fixed_df.index[fixed_df["ts_code"].astype(str) == code]
        if len(match_index) == 0:
            continue

        old_name = str(fixed_df.loc[match_index[0], "name"])
        if old_name != new_name:
            fixed_df.loc[match_index[0], "name"] = new_name
            fixed_count += 1
            print(f"  ✓ {code}: {old_name} -> {new_name}")

    print(f"[rt_k] A \u80a1\u540d\u79f0\u4fee\u6b63\u5b8c\u6210，\u5171\u4fee\u6b63 {fixed_count} \u53ea\u80a1\u7968")
    return fixed_df


def fetch_hk_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """
    \u83b7\u53d6\u6e2f\u80a1\u5217\u8868

    \u63a5\u53e3：hk_basic
    \u9650\u91cf：\u5355\u6b21\u53ef\u63d0\u53d6\u5168\u90e8\u5728\u4ea4\u6613\u7684\u6e2f\u80a1

    Args:
        api: Tushare API \u5b9e\u4f8b

    Returns:
        \u6e2f\u80a1\u6570\u636e DataFrame，\u5931\u8d25\u8fd4\u56de None
    """
    print("\n[2/3] \u6b63\u5728\u83b7\u53d6\u6e2f\u80a1\u5217\u8868...")

    try:
        # \u83b7\u53d6\u6240\u6709\u6b63\u5e38\u4e0a\u5e02\u7684\u6e2f\u80a1
        df = api.hk_basic(
            list_status='L'    # L: \u4e0a\u5e02, D: \u9000\u5e02
        )

        if df is not None and len(df) > 0:
            print(f"✓ \u6e2f\u80a1\u5217\u8868\u83b7\u53d6\u6210\u529f，\u5171 {len(df)} \u53ea\u80a1\u7968")
            return df
        else:
            print("[\u9519\u8bef] \u6e2f\u80a1\u6570\u636e\u4e3a\u7a7a")
            return None

    except Exception as e:
        print(f"[\u9519\u8bef] \u83b7\u53d6\u6e2f\u80a1\u5217\u8868\u5931\u8d25: {e}")
        return None


def fetch_us_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """
    \u83b7\u53d6\u7f8e\u80a1\u5217\u8868（\u5206\u9875\u8bfb\u53d6）

    \u63a5\u53e3：us_basic
    \u9650\u91cf：\u5355\u6b21\u6700\u59276000，\u9700\u8981\u5206\u9875\u63d0\u53d6

    Args:
        api: Tushare API \u5b9e\u4f8b

    Returns:
        \u7f8e\u80a1\u6570\u636e DataFrame，\u5931\u8d25\u8fd4\u56de None
    """
    print("\n[3/3] \u6b63\u5728\u83b7\u53d6\u7f8e\u80a1\u5217\u8868（\u5206\u9875\u8bfb\u53d6）...")

    all_data = []
    offset = 0
    page = 1

    try:
        while True:
            print(f"  \u7b2c {page} \u9875（offset={offset}）...")

            df = api.us_basic(
                offset=offset,
                limit=PAGE_SIZE
            )

            if df is None or len(df) == 0:
                print(f"  ✓ \u7b2c {page} \u9875\u65e0\u6570\u636e，\u8bfb\u53d6\u5b8c\u6210")
                break

            all_data.append(df)
            print(f"  ✓ \u7b2c {page} \u9875\u83b7\u53d6 {len(df)} \u53ea\u80a1\u7968")

            # \u5982\u679c\u8fd4\u56de\u6570\u636e\u5c11\u4e8e\u9875\u5927\u5c0f，\u8bf4\u660e\u5df2\u7ecf\u5230\u6700\u540e\u4e00\u9875
            if len(df) < PAGE_SIZE:
                break

            offset += PAGE_SIZE
            page += 1

            # \u968f\u673a\u4f11\u606f（\u6700\u540e\u4e00\u9875\u4e0d\u9700\u8981\u4f11\u606f）
            random_sleep()

        if all_data:
            result_df = pd.concat(all_data, ignore_index=True)
            print(f"✓ \u7f8e\u80a1\u5217\u8868\u83b7\u53d6\u6210\u529f，\u5171 {len(result_df)} \u53ea\u80a1\u7968（{page} \u9875）")

            # \u6309\u5206\u7c7b\u7edf\u8ba1
            if 'classify' in result_df.columns:
                print("  - \u5206\u7c7b\u5206\u5e03：")
                for classify, count in result_df['classify'].value_counts().items():
                    print(f"    {classify}: {count} \u53ea")

            return result_df
        else:
            print("[\u9519\u8bef] \u7f8e\u80a1\u6570\u636e\u4e3a\u7a7a")
            return None

    except Exception as e:
        print(f"[\u9519\u8bef] \u83b7\u53d6\u7f8e\u80a1\u5217\u8868\u5931\u8d25: {e}")
        return None


def save_to_csv(df: pd.DataFrame, filename: str, market_name: str) -> bool:
    """
    \u4fdd\u5b58\u6570\u636e\u5230 CSV \u6587\u4ef6

    Args:
        df: \u6570\u636e DataFrame
        filename: \u6587\u4ef6\u540d
        market_name: \u5e02\u573a\u540d\u79f0（\u7528\u4e8e\u65e5\u5fd7）

    Returns:
        \u662f\u5426\u4fdd\u5b58\u6210\u529f
    """
    if df is None or len(df) == 0:
        print(f"[\u8df3\u8fc7] {market_name} \u6570\u636e\u4e3a\u7a7a，\u4e0d\u4fdd\u5b58\u6587\u4ef6")
        return False

    try:
        output_path = OUTPUT_DIR / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        file_size = output_path.stat().st_size / 1024  # KB
        print(f"✓ {market_name} \u6570\u636e\u5df2\u4fdd\u5b58：{output_path} ({file_size:.2f} KB)")
        return True

    except Exception as e:
        print(f"[\u9519\u8bef] \u4fdd\u5b58 {market_name} \u6570\u636e\u5931\u8d25: {e}")
        return False


def generate_data_documentation(
    a_df: Optional[pd.DataFrame],
    hk_df: Optional[pd.DataFrame],
    us_df: Optional[pd.DataFrame],
    a_filename: str = "stock_list_a.csv",
    a_title: str = "A\u80a1\u5217\u8868"
):
    """
    \u751f\u6210\u6570\u636e\u8bf4\u660e\u6587\u6863

    Args:
        a_df: A\u80a1\u6570\u636e
        hk_df: \u6e2f\u80a1\u6570\u636e
        us_df: \u7f8e\u80a1\u6570\u636e
    """
    doc_path = OUTPUT_DIR / "README_stock_list.md"

    content = f"""# Tushare \u80a1\u7968\u5217\u8868\u6570\u636e\u8bf4\u660e

> \u6570\u636e\u6765\u6e90：[Tushare Pro](https://tushare.pro)
> \u751f\u6210\u65f6\u95f4：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## \u6587\u4ef6\u8bf4\u660e

| \u6587\u4ef6 | \u8bf4\u660e | \u8bb0\u5f55\u6570 |
|------|------|--------|
| `{a_filename}` | {a_title} | {len(a_df) if a_df is not None else 0} |
| `stock_list_hk.csv` | \u6e2f\u80a1\u5217\u8868 | {len(hk_df) if hk_df is not None else 0} |
| `stock_list_us.csv` | \u7f8e\u80a1\u5217\u8868 | {len(us_df) if us_df is not None else 0} |

---

## A\u80a1\u6570\u636e（{a_filename}）

### \u6570\u636e\u63a5\u53e3
- **\u63a5\u53e3\u540d\u79f0**：`stock_basic`
- **\u6570\u636e\u6743\u9650**：2000\u79ef\u5206\u8d77，\u6bcf\u5206\u949f\u8bf7\u6c4250\u6b21
- **\u6570\u636e\u9650\u91cf**：\u5355\u6b21\u6700\u591a6000\u884c（\u8986\u76d6\u5168\u5e02\u573aA\u80a1）

### \u5b57\u6bb5\u8bf4\u660e

| \u5b57\u6bb5\u540d | \u7c7b\u578b | \u8bf4\u660e | \u793a\u4f8b |
|--------|------|------|------|
| ts_code | str | TS\u4ee3\u7801 | 000001.SZ |
| symbol | str | \u80a1\u7968\u4ee3\u7801 | 000001 |
| name | str | \u80a1\u7968\u540d\u79f0 | \u5e73\u5b89\u94f6\u884c |
| area | str | \u5730\u57df | \u6df1\u5733 |
| industry | str | \u6240\u5c5e\u884c\u4e1a | \u94f6\u884c |
| fullname | str | \u80a1\u7968\u5168\u79f0 | \u5e73\u5b89\u94f6\u884c\u80a1\u4efd\u6709\u9650\u516c\u53f8 |
| enname | str | \u82f1\u6587\u5168\u79f0 | Ping An Bank Co., Ltd. |
| cnspell | str | \u62fc\u97f3\u7f29\u5199 | PAYH |
| market | str | \u5e02\u573a\u7c7b\u578b | \u4e3b\u677f/\u521b\u4e1a\u677f/\u79d1\u521b\u677f/CDR |
| exchange | str | \u4ea4\u6613\u6240\u4ee3\u7801 | SSE\u4e0a\u4ea4\u6240/SZSE\u6df1\u4ea4\u6240/BSE\u5317\u4ea4\u6240 |
| curr_type | str | \u4ea4\u6613\u8d27\u5e01 | CNY |
| list_status | str | \u4e0a\u5e02\u72b6\u6001 | L\u4e0a\u5e02/D\u9000\u5e02/P\u6682\u505c\u4e0a\u5e02 |
| list_date | str | \u4e0a\u5e02\u65e5\u671f | 19910403 |
| delist_date | str | \u9000\u5e02\u65e5\u671f | - |
| is_hs | str | \u662f\u5426\u6caa\u6df1\u6e2f\u901a\u6807\u7684 | N\u5426/H\u6caa\u80a1\u901a/S\u6df1\u80a1\u901a |
| act_name | str | \u5b9e\u63a7\u4eba\u540d\u79f0 | - |
| act_ent_type | str | \u5b9e\u63a7\u4eba\u4f01\u4e1a\u6027\u8d28 | - |

### \u6570\u636e\u6837\u4f8b
```csv
ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type
000001.SZ,000001,\u5e73\u5b89\u94f6\u884c,\u6df1\u5733,\u94f6\u884c,\u5e73\u5b89\u94f6\u884c\u80a1\u4efd\u6709\u9650\u516c\u53f8,Ping An Bank Co., Ltd.,PAYH,\u4e3b\u677f,SZSE,CNY,L,19910403,,S,,
000002.SZ,000002,\u4e07\u79d1A,\u6df1\u5733,\u5168\u56fd\u5730\u4ea7,\u4e07\u79d1\u4f01\u4e1a\u80a1\u4efd\u6709\u9650\u516c\u53f8,China Vanke Co., Ltd.,ZKA,\u4e3b\u677f,SZSE,CNY,L,19910129,,S,,
```

---

## \u6e2f\u80a1\u6570\u636e（stock_list_hk.csv）

### \u6570\u636e\u63a5\u53e3
- **\u63a5\u53e3\u540d\u79f0**：`hk_basic`
- **\u6570\u636e\u6743\u9650**：\u7528\u6237\u9700\u8981\u81f3\u5c112000\u79ef\u5206\u624d\u53ef\u4ee5\u8c03\u53d6
- **\u6570\u636e\u9650\u91cf**：\u5355\u6b21\u53ef\u63d0\u53d6\u5168\u90e8\u5728\u4ea4\u6613\u7684\u6e2f\u80a1\u5217\u8868\u6570\u636e

### \u5b57\u6bb5\u8bf4\u660e

| \u5b57\u6bb5\u540d | \u7c7b\u578b | \u8bf4\u660e | \u793a\u4f8b |
|--------|------|------|------|
| ts_code | str | TS\u4ee3\u7801 | 00001.HK |
| name | str | \u80a1\u7968\u7b80\u79f0 | \u957f\u548c |
| fullname | str | \u516c\u53f8\u5168\u79f0 | \u957f\u6c5f\u548c\u8bb0\u5b9e\u4e1a\u6709\u9650\u516c\u53f8 |
| enname | str | \u82f1\u6587\u540d\u79f0 | CK Hutchison Holdings Ltd. |
| cn_spell | str | \u62fc\u97f3 | ZH |
| market | str | \u5e02\u573a\u7c7b\u522b | \u4e3b\u677f/\u521b\u4e1a\u677f |
| list_status | str | \u4e0a\u5e02\u72b6\u6001 | L\u4e0a\u5e02/D\u9000\u5e02/P\u6682\u505c\u4e0a\u5e02 |
| list_date | str | \u4e0a\u5e02\u65e5\u671f | 19720731 |
| delist_date | str | \u9000\u5e02\u65e5\u671f | - |
| trade_unit | float | \u4ea4\u6613\u5355\u4f4d | 1000 |
| isin | str | ISIN\u4ee3\u7801 | KYG217651051 |
| curr_type | str | \u8d27\u5e01\u4ee3\u7801 | HKD |

### \u6570\u636e\u6837\u4f8b
```csv
ts_code,name,fullname,enname,cn_spell,market,list_status,list_date,delist_date,trade_unit,isin,curr_type
00001.HK,\u957f\u548c,\u957f\u6c5f\u548c\u8bb0\u5b9e\u4e1a\u6709\u9650\u516c\u53f8,CK Hutchison Holdings Ltd.,ZH,\u4e3b\u677f,L,19720731,,1000,KYG217651051,HKD
00002.HK,\u4e2d\u7535\u63a7\u80a1,\u4e2d\u534e\u7535\u529b\u6709\u9650\u516c\u53f8,CLP Holdings Ltd.,ZDKG,\u4e3b\u677f,L,19860125,,1000,HK0002007356,HKD
```

---

## \u7f8e\u80a1\u6570\u636e（stock_list_us.csv）

### \u6570\u636e\u63a5\u53e3
- **\u63a5\u53e3\u540d\u79f0**：`us_basic`
- **\u6570\u636e\u6743\u9650**：120\u79ef\u5206\u53ef\u4ee5\u8bd5\u7528，5000\u79ef\u5206\u6709\u6b63\u5f0f\u6743\u9650
- **\u6570\u636e\u9650\u91cf**：\u5355\u6b21\u6700\u59276000，\u53ef\u5206\u9875\u63d0\u53d6

### \u5b57\u6bb5\u8bf4\u660e

| \u5b57\u6bb5\u540d | \u7c7b\u578b | \u8bf4\u660e | \u793a\u4f8b |
|--------|------|------|------|
| ts_code | str | \u7f8e\u80a1\u4ee3\u7801 | AAPL |
| name | str | \u4e2d\u6587\u540d\u79f0 | \u82f9\u679c |
| enname | str | \u82f1\u6587\u540d\u79f0 | Apple Inc. |
| classify | str | \u5206\u7c7b | ADR/GDR/EQT |
| list_date | str | \u4e0a\u5e02\u65e5\u671f | 19801212 |
| delist_date | str | \u9000\u5e02\u65e5\u671f | - |

### \u5206\u7c7b\u8bf4\u660e
- **ADR**：\u7f8e\u56fd\u5b58\u6258\u51ed\u8bc1（American Depositary Receipt）
- **GDR**：\u5168\u7403\u5b58\u6258\u51ed\u8bc1（Global Depositary Receipt）
- **EQT**：\u666e\u901a\u80a1（Equity）

### \u6570\u636e\u6837\u4f8b
```csv
ts_code,name,enname,classify,list_date,delist_date
AAPL,\u82f9\u679c,Apple Inc.,EQT,19801212,
TSLA,\u7279\u65af\u62c9,Tesla Inc.,EQT,20100629,
BABA,\u963f\u91cc\u5df4\u5df4,Alibaba Group Holding Ltd.,ADR,20140919,
```

---

## \u4f7f\u7528\u8bf4\u660e

### \u8bfb\u53d6\u6570\u636e

```python
import pandas as pd

# \u8bfb\u53d6 A\u80a1\u6570\u636e
a_stocks = pd.read_csv('data/{a_filename}')

# \u8bfb\u53d6\u6e2f\u80a1\u6570\u636e
hk_stocks = pd.read_csv('data/stock_list_hk.csv')

# \u8bfb\u53d6\u7f8e\u80a1\u6570\u636e
us_stocks = pd.read_csv('data/stock_list_us.csv')
```

### \u4ee3\u7801\u683c\u5f0f\u8bf4\u660e

**A\u80a1\u4ee3\u7801\u683c\u5f0f**：
- \u6caa\u5e02：`600000.SH`（\u4e3b\u677f）、`688xxx.SH`（\u79d1\u521b\u677f）、`900xxx.SH`（B\u80a1）
- \u6df1\u5e02：`000001.SZ`（\u4e3b\u677f）、`300xxx.SZ`（\u521b\u4e1a\u677f）、`200xxx.SZ`（B\u80a1）
- \u5317\u4ea4\u6240：`8xxxxx.BJ`、`4xxxxx.BJ`、`920xxx.BJ`

**\u6e2f\u80a1\u4ee3\u7801\u683c\u5f0f**：
- \u683c\u5f0f：`xxxxx.HK`（5\u4f4d\u6570\u5b57 + .HK）
- \u793a\u4f8b：`00700.HK`（\u817e\u8baf\u63a7\u80a1）

**\u7f8e\u80a1\u4ee3\u7801\u683c\u5f0f**：
- \u683c\u5f0f：\u4ee3\u7801\u5b57\u6bcd（\u65e0\u540e\u7f00）
- \u793a\u4f8b：`AAPL`（\u82f9\u679c）、`TSLA`（\u7279\u65af\u62c9）

---

## \u6ce8\u610f\u4e8b\u9879

1. **\u6570\u636e\u66f4\u65b0**：\u5efa\u8bae\u5b9a\u671f\u66f4\u65b0\u6570\u636e（\u5982\u6bcf\u6708\u4e00\u6b21）
2. **\u79ef\u5206\u8981\u6c42**：
   - A\u80a1/\u6e2f\u80a1：\u9700\u89812000\u79ef\u5206
   - \u7f8e\u80a1：120\u79ef\u5206\u8bd5\u7528，5000\u79ef\u5206\u6b63\u5f0f\u6743\u9650
3. **\u8bf7\u6c42\u9650\u5236**：\u6ce8\u610f API \u7684\u6bcf\u5206\u949f\u8bf7\u6c42\u6b21\u6570\u9650\u5236
4. **\u6570\u636e\u5b8c\u6574\u6027**：\u672c\u6570\u636e\u4ec5\u5305\u542b\u57fa\u7840\u4fe1\u606f，\u5982\u9700\u66f4\u591a\u6570\u636e\u8bf7\u53c2\u8003 Tushare \u5b98\u65b9\u6587\u6863

---

## \u76f8\u5173\u94fe\u63a5

- [Tushare \u5b98\u7f51](https://tushare.pro)
- [Tushare \u6587\u6863](https://tushare.pro/document/2)
- [\u79ef\u5206\u83b7\u53d6\u529e\u6cd5](https://tushare.pro/document/1)
- [API \u6570\u636e\u8c03\u8bd5](https://tushare.pro/document/2)
"""

    try:
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ \u6570\u636e\u8bf4\u660e\u6587\u6863\u5df2\u751f\u6210：{doc_path}")
    except Exception as e:
        print(f"[\u9519\u8bef] \u751f\u6210\u8bf4\u660e\u6587\u6863\u5931\u8d25: {e}")


def build_arg_parser() -> argparse.ArgumentParser:
    """\u6784\u5efa\u547d\u4ee4\u884c\u53c2\u6570。"""
    parser = argparse.ArgumentParser(description="Tushare \u80a1\u7968\u5217\u8868\u83b7\u53d6\u5de5\u5177")
    parser.add_argument(
        "--a-rk",
        action="store_true",
        help="\u4f7f\u7528 rt_k \u4fee\u6b63 A \u80a1\u4e2d\u5e26 XD/XR/DR/N/C \u524d\u7f00\u7684\u540d\u79f0，\u5e76\u8986\u76d6\u8f93\u51fa\u5230 stock_list_a.csv",
    )
    return parser


def main(argv: Optional[List[str]] = None):
    """\u4e3b\u51fd\u6570"""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    print("=" * 60)
    print("Tushare \u80a1\u7968\u5217\u8868\u83b7\u53d6\u5de5\u5177")
    print("=" * 60)
    print(f"[\u4fe1\u606f] A\u80a1\u540d\u79f0\u4fee\u6b63\u6a21\u5f0f：{'\u5f00\u542f' if args.a_rk else '\u5173\u95ed'}")

    # 1. \u83b7\u53d6 API \u5b9e\u4f8b
    api = get_tushare_api()
    if not api:
        return 1

    # 2. \u83b7\u53d6 A\u80a1\u6570\u636e
    a_df = fetch_a_stock_list(api)
    if a_df is not None:
        a_filename = 'stock_list_a.csv'
        a_title = 'A\u80a1\u5217\u8868'
        a_market_name = 'A\u80a1'

        if args.a_rk:
            a_df = fix_a_stock_names_with_rt_k(api, a_df)
            a_title = 'A\u80a1\u5217\u8868（\u4fee\u6b63\u540e）'

        save_to_csv(a_df, a_filename, a_market_name)

    # 3. \u83b7\u53d6\u6e2f\u80a1\u6570\u636e
    random_sleep()  # \u4f11\u606f\u540e\u518d\u83b7\u53d6\u6e2f\u80a1
    hk_df = fetch_hk_stock_list(api)
    if hk_df is not None:
        save_to_csv(hk_df, 'stock_list_hk.csv', '\u6e2f\u80a1')

    # 4. \u83b7\u53d6\u7f8e\u80a1\u6570\u636e（\u5206\u9875）
    random_sleep()  # \u4f11\u606f\u540e\u518d\u83b7\u53d6\u7f8e\u80a1
    us_df = fetch_us_stock_list(api)
    if us_df is not None:
        save_to_csv(us_df, 'stock_list_us.csv', '\u7f8e\u80a1')

    # 5. \u751f\u6210\u6570\u636e\u8bf4\u660e\u6587\u6863
    print("\n\u6b63\u5728\u751f\u6210\u6570\u636e\u8bf4\u660e\u6587\u6863...")
    a_filename = 'stock_list_a.csv'
    a_title = 'A\u80a1\u5217\u8868（\u4fee\u6b63\u540e）' if args.a_rk else 'A\u80a1\u5217\u8868'
    generate_data_documentation(a_df, hk_df, us_df, a_filename=a_filename, a_title=a_title)

    # 6. \u603b\u7ed3
    print("\n" + "=" * 60)
    print("\u4efb\u52a1\u5b8c\u6210！")
    print("=" * 60)

    total_count = 0
    if a_df is not None:
        total_count += len(a_df)
        print(f"  ✓ A\u80a1：{len(a_df)} \u53ea")
    if hk_df is not None:
        total_count += len(hk_df)
        print(f"  ✓ \u6e2f\u80a1：{len(hk_df)} \u53ea")
    if us_df is not None:
        total_count += len(us_df)
        print(f"  ✓ \u7f8e\u80a1：{len(us_df)} \u53ea")

    print(f"\n\u603b\u8ba1：{total_count} \u53ea\u80a1\u7968")
    print(f"\u8f93\u51fa\u76ee\u5f55：{OUTPUT_DIR}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[\u4e2d\u65ad] \u7528\u6237\u53d6\u6d88\u64cd\u4f5c")
        sys.exit(1)
    except Exception as e:
        print(f"\n[\u9519\u8bef] \u672a\u9884\u671f\u7684\u5f02\u5e38: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
