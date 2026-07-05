# -*- coding: utf-8 -*-
"""Tests for scripts.fetch_tushare_stock_list A-share rt_k fix flow."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

if "tushare" not in sys.modules:
    tushare_stub = types.ModuleType("tushare")
    tushare_stub.pro_api = lambda *args, **kwargs: MagicMock()
    sys.modules["tushare"] = tushare_stub

fetch_tushare_stock_list = importlib.import_module("fetch_tushare_stock_list")


def test_should_fix_a_stock_name_matches_status_prefixes():
    assert fetch_tushare_stock_list.should_fix_a_stock_name("XD\u897f\u85cf\u836f")
    assert fetch_tushare_stock_list.should_fix_a_stock_name("XR\u6d66\u4e1c\u5efa")
    assert fetch_tushare_stock_list.should_fix_a_stock_name("DR\u7f57\u66fc\u80a1")
    assert fetch_tushare_stock_list.should_fix_a_stock_name("N\u60e0\u5eb7")
    assert fetch_tushare_stock_list.should_fix_a_stock_name("C\u5929\u6d77")
    assert not fetch_tushare_stock_list.should_fix_a_stock_name("\u5e73\u5b89\u94f6\u884c")
    assert not fetch_tushare_stock_list.should_fix_a_stock_name("ST\u7f57\u987f")
    assert not fetch_tushare_stock_list.should_fix_a_stock_name("*ST\u94d6\u660c")


def test_fix_a_stock_names_with_rt_k_replaces_candidate_names():
    api = MagicMock()
    source_df = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "600848.SH", "300001.SZ"],
            "name": ["XD\u897f\u85cf\u836f", "\u5e73\u5b89\u94f6\u884c", "N\u60e0\u5eb7"],
        }
    )

    with patch.object(
        fetch_tushare_stock_list,
        "fetch_rt_k_names",
        return_value={"000001.SZ": "\u897f\u85cf\u836f", "300001.SZ": "\u60e0\u5eb7"},
    ) as fetch_rt_k_names:
        fixed_df = fetch_tushare_stock_list.fix_a_stock_names_with_rt_k(api, source_df)

    assert fixed_df.loc[fixed_df["ts_code"] == "000001.SZ", "name"].iloc[0] == "\u897f\u85cf\u836f"
    assert fixed_df.loc[fixed_df["ts_code"] == "600848.SH", "name"].iloc[0] == "\u5e73\u5b89\u94f6\u884c"
    assert fixed_df.loc[fixed_df["ts_code"] == "300001.SZ", "name"].iloc[0] == "\u60e0\u5eb7"
    fetch_rt_k_names.assert_called_once_with(api, ["000001.SZ", "300001.SZ"])


def test_fetch_rt_k_names_batches_and_collects_results():
    api = MagicMock()
    api.rt_k.return_value = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "300001.SZ"],
            "name": ["\u897f\u85cf\u836f", "\u60e0\u5eb7"],
            "close": [1.0, 2.0],
            "pre_close": [1.0, 2.0],
            "trade_time": ["10:00:00", "10:00:00"],
        }
    )

    with patch.object(fetch_tushare_stock_list, "random_sleep") as random_sleep:
        name_map = fetch_tushare_stock_list.fetch_rt_k_names(api, ["000001.SZ", "300001.SZ"])

    assert name_map == {"000001.SZ": "\u897f\u85cf\u836f", "300001.SZ": "\u60e0\u5eb7"}
    api.rt_k.assert_called_once_with(
        ts_code="000001.SZ,300001.SZ",
        fields="ts_code,name,close,pre_close,trade_time",
    )
    random_sleep.assert_not_called()


def test_main_default_flow_keeps_original_filename():
    api = MagicMock()
    a_df = pd.DataFrame({"ts_code": ["000001.SZ"], "name": ["\u5e73\u5b89\u94f6\u884c"]})
    hk_df = pd.DataFrame({"ts_code": ["00001.HK"], "name": ["\u957f\u548c"]})
    us_df = pd.DataFrame({"ts_code": ["AAPL"], "name": ["\u82f9\u679c"]})

    with (
        patch.object(fetch_tushare_stock_list, "get_tushare_api", return_value=api),
        patch.object(fetch_tushare_stock_list, "fetch_a_stock_list", return_value=a_df) as fetch_a,
        patch.object(fetch_tushare_stock_list, "save_to_csv") as save_to_csv,
        patch.object(fetch_tushare_stock_list, "fetch_hk_stock_list", return_value=hk_df) as fetch_hk,
        patch.object(fetch_tushare_stock_list, "fetch_us_stock_list", return_value=us_df) as fetch_us,
        patch.object(fetch_tushare_stock_list, "generate_data_documentation") as generate_doc,
        patch.object(fetch_tushare_stock_list, "random_sleep") as random_sleep,
        patch.object(fetch_tushare_stock_list, "fix_a_stock_names_with_rt_k") as fix_a_stock_names,
    ):
        exit_code = fetch_tushare_stock_list.main([])

    assert exit_code == 0
    fetch_a.assert_called_once_with(api)
    save_to_csv.assert_any_call(a_df, "stock_list_a.csv", "A\u80a1")
    fetch_hk.assert_called_once_with(api)
    fetch_us.assert_called_once_with(api)
    fix_a_stock_names.assert_not_called()
    generate_doc.assert_called_once_with(a_df, hk_df, us_df, a_filename="stock_list_a.csv", a_title="A\u80a1\u5217\u8868")
    assert random_sleep.call_count == 2


def test_main_a_rk_flow_overwrites_a_filename_and_rt_k():
    api = MagicMock()
    a_df = pd.DataFrame({"ts_code": ["000001.SZ"], "name": ["XD\u897f\u85cf\u836f"]})
    fixed_df = pd.DataFrame({"ts_code": ["000001.SZ"], "name": ["\u897f\u85cf\u836f"]})
    hk_df = pd.DataFrame({"ts_code": ["00001.HK"], "name": ["\u957f\u548c"]})
    us_df = pd.DataFrame({"ts_code": ["AAPL"], "name": ["\u82f9\u679c"]})

    with (
        patch.object(fetch_tushare_stock_list, "get_tushare_api", return_value=api),
        patch.object(fetch_tushare_stock_list, "fetch_a_stock_list", return_value=a_df) as fetch_a,
        patch.object(fetch_tushare_stock_list, "fix_a_stock_names_with_rt_k", return_value=fixed_df) as fix_a_stock_names,
        patch.object(fetch_tushare_stock_list, "save_to_csv") as save_to_csv,
        patch.object(fetch_tushare_stock_list, "fetch_hk_stock_list", return_value=hk_df) as fetch_hk,
        patch.object(fetch_tushare_stock_list, "fetch_us_stock_list", return_value=us_df) as fetch_us,
        patch.object(fetch_tushare_stock_list, "generate_data_documentation") as generate_doc,
        patch.object(fetch_tushare_stock_list, "random_sleep") as random_sleep,
    ):
        exit_code = fetch_tushare_stock_list.main(["--a-rk"])

    assert exit_code == 0
    fetch_a.assert_called_once_with(api)
    fix_a_stock_names.assert_called_once_with(api, a_df)
    fixed_save_call = next(
        call for call in save_to_csv.call_args_list if call.args[1] == "stock_list_a.csv"
    )
    pd.testing.assert_frame_equal(fixed_save_call.args[0], fixed_df)
    assert fixed_save_call.args[2] == "A\u80a1"
    fetch_hk.assert_called_once_with(api)
    fetch_us.assert_called_once_with(api)
    generate_doc.assert_called_once_with(
        fixed_df,
        hk_df,
        us_df,
        a_filename="stock_list_a.csv",
        a_title="A\u80a1\u5217\u8868（\u4fee\u6b63\u540e）",
    )
    assert random_sleep.call_count == 2
