# -*- coding: utf-8 -*-
"""v2.1 tw report-consumption tests.

Covers the last-mile that makes the merged \u4e09\u5927\u6cd5\u4eba (institutional-flows) data actually
usable in a tw report: currency labelling (TWD, not RMB), rendering the institution
block into the report, injecting it into the LLM prompt, and fetch availability on the
first/only stock. Fully offline (no network / no LLM).
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    from tests.litellm_stub import ensure_litellm_stub

    ensure_litellm_stub()

from src.notification import NotificationService
from src.report_language import get_report_labels
from src.analyzer import GeminiAnalyzer

# real 2330.TW \u4e09\u5927\u6cd5\u4eba net figures (shares)
_INST_REC = {
    "foreign_net": -1912490, "trust_net": -89595, "dealer_net": 652455,
    "total_net": -862914, "unit": "shares", "date": "20260630", "source": "TWSE-T86",
}


class TestTwCurrencyLabel(unittest.TestCase):
    """Point D: TWD amounts must not silently render as the A-share default \u5143 (RMB)."""

    def test_twd_amount_labeled_new_taiwan_dollar_not_rmb(self):
        twd = NotificationService._format_amount_cn(1_134_103_440_000.0, "TWD")
        cny = NotificationService._format_amount_cn(1_134_103_440_000.0, "CNY")
        self.assertIn("\u65b0\u53f0\u5e01", twd)
        self.assertNotIn("\u65b0\u53f0\u5e01", cny)
        self.assertNotEqual(twd, cny)  # a TWD amount must not be byte-identical to CNY

    def test_twd_per_share_labeled(self):
        self.assertIn("\u65b0\u53f0\u5e01", NotificationService._format_per_share(24.0, "TWD"))

    def test_other_currencies_byte_identical(self):
        # strictly additive: cn / us / hk display unchanged
        self.assertEqual(NotificationService._format_amount_cn(1e8, "CNY"), "1.00 \u4ebf\u5143")
        self.assertIn("\u7f8e\u5143", NotificationService._format_amount_cn(1e8, "USD"))
        self.assertIn("\u6e2f\u5143", NotificationService._format_amount_cn(1e8, "HKD"))
        # unknown currency still falls back to \u5143 (unchanged behaviour)
        self.assertIn("\u5143", NotificationService._format_amount_cn(1e8, "ZZZ"))


class TestTwInstitutionRender(unittest.TestCase):
    """Point A: \u4e09\u5927\u6cd5\u4eba renders into the report only for a tw stock with data."""

    def _render(self, status, data):
        svc = NotificationService.__new__(NotificationService)  # methods use no instance state
        lines = []
        blocks = {"institution": data, "institution_status": status}
        svc._append_institutional_flow(lines, blocks, get_report_labels("zh"))
        return "\n".join(lines)

    def test_institution_rendered_when_ok(self):
        out = self._render("ok", dict(_INST_REC))
        self.assertIn("\u4e09\u5927\u6cd5\u4eba\u52a8\u5411", out)
        for token in ("\u5916\u8d44", "\u6295\u4fe1", "\u81ea\u8425\u5546", "\u4e09\u5927\u6cd5\u4eba\u5408\u8ba1", "TWSE-T86", "20260630"):
            self.assertIn(token, out)
        self.assertIn("-191.25 \u4e07\u80a1", out)   # foreign_net -1,912,490
        self.assertIn("+65.25 \u4e07\u80a1", out)    # dealer_net +652,455 (net buy shows +)

    def test_institution_not_rendered_when_not_supported(self):
        self.assertEqual(self._render("not_supported", {}), "")
        self.assertEqual(self._render(None, {}), "")
        self.assertEqual(self._render("ok", {}), "")  # ok but empty data -> skip

    def test_institution_renders_all_languages_without_keyerror(self):
        # every new label key must exist in zh/en/ko so a non-zh tw report never KeyErrors.
        svc = NotificationService.__new__(NotificationService)
        for lang, token in (("zh", "\u4e09\u5927\u6cd5\u4eba"), ("en", "Institutional Flows"), ("ko", "3대 기관")):
            lines = []
            blocks = {"institution": dict(_INST_REC), "institution_status": "ok"}
            svc._append_institutional_flow(lines, blocks, get_report_labels(lang))
            self.assertIn(token, "\n".join(lines), lang)

    def test_get_fundamental_blocks_extracts_institution(self):
        svc = NotificationService.__new__(NotificationService)
        res = SimpleNamespace(fundamental_context={"institution": {"status": "ok", "data": dict(_INST_REC)}})
        blocks = svc._get_fundamental_blocks(res)
        self.assertEqual(blocks["institution_status"], "ok")
        self.assertEqual(blocks["institution"]["total_net"], -862914)
        # non-tw / missing institution -> empty + no status
        res2 = SimpleNamespace(fundamental_context={"earnings": {}})
        blocks2 = svc._get_fundamental_blocks(res2)
        self.assertEqual(blocks2["institution"], {})
        self.assertIsNone(blocks2["institution_status"])

    def test_format_net_shares_signed(self):
        self.assertEqual(NotificationService._format_net_shares(-1912490), "-191.25 \u4e07\u80a1")
        self.assertEqual(NotificationService._format_net_shares(652455), "+65.25 \u4e07\u80a1")
        self.assertEqual(NotificationService._format_net_shares(0), "0 \u80a1")
        self.assertEqual(NotificationService._format_net_shares(250000000), "+2.50 \u4ebf\u80a1")
        self.assertEqual(NotificationService._format_net_shares(None), "N/A")


class TestTwInstitutionPrompt(unittest.TestCase):
    """Point B: \u4e09\u5927\u6cd5\u4eba is injected into the LLM analysis prompt for a tw stock with data."""

    def _prompt(self, fundamental_context):
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()
        context = {
            "code": "2330.TW",
            "stock_name": "\u53f0\u79ef\u7535",
            "date": "2026-06-30",
            "today": {"close": 2410, "ma5": 2380, "ma10": 2409, "ma20": 2369},
            "fundamental_context": fundamental_context,
        }
        return analyzer._format_prompt(context, "\u53f0\u79ef\u7535", news_context=None)

    def test_institution_injected_when_ok(self):
        p = self._prompt({"institution": {"status": "ok", "data": dict(_INST_REC)}})
        self.assertIn("\u4e09\u5927\u6cd5\u4eba\u52a8\u5411", p)
        for token in ("\u5916\u8d44", "\u6295\u4fe1", "\u81ea\u8425\u5546", "\u7b79\u7801\u8fc7\u6ee4\u5668"):
            self.assertIn(token, p)
        self.assertIn("-1912490", p)   # raw foreign_net reaches the prompt
        self.assertIn("-862914", p)    # raw total_net

    def test_institution_absent_when_not_supported(self):
        p = self._prompt({"institution": {"status": "not_supported", "data": {}}})
        self.assertNotIn("\u4e09\u5927\u6cd5\u4eba\u52a8\u5411", p)

    def test_institution_absent_when_any_core_net_missing(self):
        # prompt gate matches the render / base.py gate: ALL four core nets required,
        # so a partial record never reaches the LLM as an unqualified chip signal.
        partials = (
            {"foreign_net": 1, "trust_net": 1, "dealer_net": 1, "total_net": None},
            {"foreign_net": None, "trust_net": 1, "dealer_net": 1, "total_net": 1},
            {"trust_net": 1, "dealer_net": 1, "total_net": 1},  # foreign_net absent
        )
        for data in partials:
            p = self._prompt({"institution": {"status": "ok", "data": data}})
            self.assertNotIn("\u4e09\u5927\u6cd5\u4eba\u52a8\u5411", p, data)


if __name__ == "__main__":
    unittest.main()
