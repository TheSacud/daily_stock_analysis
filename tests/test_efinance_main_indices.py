import os
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.efinance_fetcher import EfinanceFetcher


class TestEfinanceMainIndices(unittest.TestCase):
    def test_get_main_indices_prefers_jinkai_column_for_open_price(self):
        fetcher = EfinanceFetcher()
        fake_df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["000001"],
                "\u6700\u65b0\u4ef7": [3200.0],
                "\u6da8\u8dcc\u5e45": [0.63],
                "\u6da8\u8dcc\u989d": [20.0],
                "\u4eca\u5f00": [3188.0],
                "\u5f00\u76d8": [0.0],
                "\u6700\u9ad8": [3215.0],
                "\u6700\u4f4e": [3170.0],
                "\u6210\u4ea4\u91cf": [123456789],
                "\u6210\u4ea4\u989d": [9876543210.0],
                "\u632f\u5e45": [1.2],
            }
        )
        fake_efinance = types.SimpleNamespace(
            stock=types.SimpleNamespace(get_realtime_quotes=lambda *args, **kwargs: fake_df)
        )

        with patch.dict(sys.modules, {"efinance": fake_efinance}):
            with patch.object(fetcher, "_set_random_user_agent", return_value=None), patch.object(
                fetcher, "_enforce_rate_limit", return_value=None
            ):
                data = fetcher.get_main_indices(region="cn")

        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["code"], "sh000001")
        self.assertEqual(data[0]["name"], "\u4e0a\u8bc1\u6307\u6570")
        self.assertAlmostEqual(data[0]["open"], 3188.0)
        self.assertAlmostEqual(data[0]["current"], 3200.0)

    def test_get_main_indices_falls_back_to_kaipan_when_jinkai_is_missing(self):
        fetcher = EfinanceFetcher()
        fake_df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["000001"],
                "\u6700\u65b0\u4ef7": [3200.0],
                "\u6da8\u8dcc\u5e45": [0.63],
                "\u6da8\u8dcc\u989d": [20.0],
                "\u4eca\u5f00": [""],
                "\u5f00\u76d8": [3186.0],
                "\u6700\u9ad8": [3215.0],
                "\u6700\u4f4e": [3170.0],
                "\u6210\u4ea4\u91cf": [123456789],
                "\u6210\u4ea4\u989d": [9876543210.0],
                "\u632f\u5e45": [1.2],
            }
        )
        fake_efinance = types.SimpleNamespace(
            stock=types.SimpleNamespace(get_realtime_quotes=lambda *args, **kwargs: fake_df)
        )

        with patch.dict(sys.modules, {"efinance": fake_efinance}):
            with patch.object(fetcher, "_set_random_user_agent", return_value=None), patch.object(
                fetcher, "_enforce_rate_limit", return_value=None
            ):
                data = fetcher.get_main_indices(region="cn")

        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertAlmostEqual(data[0]["open"], 3186.0)


if __name__ == "__main__":
    unittest.main()
