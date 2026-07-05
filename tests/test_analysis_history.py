# -*- coding: utf-8 -*-
"""
===================================
A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u5206\u6790\u5386\u53f2\u5b58\u50a8\u5355\u5143\u6d4b\u8bd5
===================================

\u804c\u8d23：
1. \u9a8c\u8bc1\u5206\u6790\u5386\u53f2\u4fdd\u5b58\u903b\u8f91
2. \u9a8c\u8bc1\u4e0a\u4e0b\u6587\u5feb\u7167\u4fdd\u5b58\u5f00\u5173
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

try:
    from fastapi.testclient import TestClient
    from api.app import create_app
    from api.v1.endpoints.history import get_history_detail, get_stock_bar
except ModuleNotFoundError:
    TestClient = None
    create_app = None
    get_history_detail = None
    get_stock_bar = None

from src.config import Config
from src.storage import (
    DatabaseManager,
    AnalysisHistory,
    BacktestResult,
    DecisionSignalFeedbackRecord,
    DecisionSignalOutcomeRecord,
    DecisionSignalRecord,
)
from src.analyzer import AnalysisResult
from src.daily_market_context_guardrail import apply_daily_market_context_guardrail
from src.services.history_service import HistoryService
import src.auth as auth


def _analysis_context_pack_overview() -> dict:
    return {
        "pack_version": "1.0",
        "created_at": "2026-04-10T08:30:00+00:00",
        "subject": {
            "code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "market": "cn",
        },
        "blocks": [
            {
                "key": "quote",
                "label": "\u884c\u60c5",
                "status": "available",
                "source": "mock",
                "warnings": [],
                "missing_reasons": [],
            }
        ],
        "counts": {
            "available": 1,
            "missing": 0,
            "not_supported": 0,
            "fallback": 0,
            "stale": 0,
            "estimated": 0,
            "partial": 0,
            "fetch_failed": 0,
        },
        "data_quality": {
            "overall_score": 100,
            "level": "good",
            "block_scores": {
                "quote": 100,
                "daily_bars": 100,
                "technical": 100,
                "news": 100,
                "fundamentals": 100,
                "chip": 100,
            },
            "limitations": [],
        },
        "warnings": [],
        "metadata": {
            "trigger_source": "api",
            "news_result_count": 2,
        },
    }


def _market_phase_summary() -> dict:
    return {
        "market": "cn",
        "phase": "intraday",
        "market_local_time": "2026-03-27T10:00:00+08:00",
        "session_date": "2026-03-27",
        "effective_daily_bar_date": "2026-03-26",
        "is_trading_day": True,
        "is_market_open_now": True,
        "is_partial_bar": True,
        "minutes_to_open": None,
        "minutes_to_close": 300,
        "trigger_source": "api",
        "analysis_intent": "auto",
        "warnings": ["partial_bar"],
    }


class AnalysisHistoryTestCase(unittest.TestCase):
    """\u5206\u6790\u5386\u53f2\u5b58\u50a8\u6d4b\u8bd5"""

    def setUp(self) -> None:
        """\u4e3a\u6bcf\u4e2a\u7528\u4f8b\u521d\u59cb\u5316\u72ec\u7acb\u6570\u636e\u5e93"""
        auth._auth_enabled = False
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_analysis_history.db")
        self._original_env = {
            key: os.environ.get(key)
            for key in (
                "ENV_FILE",
                "DATABASE_PATH",
            )
        }
        self._env_path = os.path.join(self._temp_dir.name, ".env")
        with open(self._env_path, "w", encoding="utf-8") as env_file:
            env_file.write("STOCK_LIST=600519,000001\n")

        os.environ["ENV_FILE"] = self._env_path
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        """\u6e05\u7406\u8d44\u6e90"""
        Config._instance = None
        DatabaseManager.reset_instance()
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._temp_dir.cleanup()

    def _build_result(self) -> AnalysisResult:
        """\u6784\u9020\u5206\u6790\u7ed3\u679c"""
        return AnalysisResult(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            sentiment_score=78,
            trend_prediction="\u770b\u591a",
            operation_advice="\u6301\u6709",
            analysis_summary="\u57fa\u672c\u9762\u7a33\u5065，\u77ed\u671f\u9707\u8361",
        )

    def _save_history(self, query_id: str) -> int:
        """\u4fdd\u5b58\u4e00\u6761\u6d4b\u8bd5\u5386\u53f2\u8bb0\u5f55\u5e76\u8fd4\u56de\u4e3b\u952e ID。"""
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            return row.id

    def test_save_analysis_history_with_snapshot(self) -> None:
        """\u4fdd\u5b58\u5386\u53f2\u8bb0\u5f55\u5e76\u5199\u5165\u4e0a\u4e0b\u6587\u5feb\u7167"""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "\u7406\u60f3\u4e70\u5165\u70b9：125.5\u5143",
                    "secondary_buy": "120",
                    "stop_loss": "\u6b62\u635f\u4f4d：110\u5143",
                    "take_profit": "\u76ee\u6807\u4f4d：150.0\u5143",
                }
            }
        }
        context_snapshot = {"enhanced_context": {"code": "600519"}}

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_001",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=context_snapshot,
            save_snapshot=True
        )

        self.assertGreater(saved, 0)

        history = self.db.get_analysis_history(code="600519", days=7, limit=10)
        self.assertEqual(len(history), 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            self.assertEqual(row.query_id, "query_001")
            self.assertIsNotNone(row.context_snapshot)
            self.assertEqual(row.ideal_buy, 125.5)
            self.assertEqual(row.secondary_buy, 120.0)
            self.assertEqual(row.stop_loss, 110.0)
            self.assertEqual(row.take_profit, 150.0)

    def test_history_display_resolves_bare_jp_kr_code_from_stock_pool(self) -> None:
        result = self._build_result()
        result.code = "005930"
        result.name = "Samsung Electronics"
        persisted_phase_summary = {
            **_market_phase_summary(),
            "phase": "postmarket",
            "market_local_time": "2025-01-02T16:10:00+09:00",
            "session_date": "2025-01-02",
            "effective_daily_bar_date": "2025-01-02",
            "is_market_open_now": False,
            "is_partial_bar": False,
            "minutes_to_open": 900,
            "minutes_to_close": None,
            "trigger_source": "scheduled_job",
            "analysis_intent": "postmarket",
            "warnings": ["legacy_snapshot"],
        }
        expected_phase_summary = {**persisted_phase_summary, "market": "kr"}
        expected_phase_summary["minutes_to_open"] = None

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_kr_bare",
            report_type="simple",
            news_content="news",
            context_snapshot={"market_phase_summary": persisted_phase_summary},
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        service = HistoryService(self.db)
        with patch("src.services.history_service.resolve_index_stock_code", return_value="005930.KS"):
            listing = service.get_history_list(page=1, limit=5)
            detail = service.resolve_and_get_detail("query_kr_bare")

        self.assertEqual(listing["items"][0]["stock_code"], "005930.KS")
        self.assertEqual(listing["items"][0]["market_phase_summary"], expected_phase_summary)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["stock_code"], "005930.KS")
        self.assertEqual(detail["market_phase_summary"], expected_phase_summary)

    def test_history_display_rebuilds_market_phase_summary_for_legacy_cn_snapshot(self) -> None:
        result = self._build_result()
        result.code = "005930"
        result.name = "Samsung Electronics"
        persisted_phase_summary = {
            **_market_phase_summary(),
            "phase": "postmarket",
            "market_local_time": "2026-01-01T10:00:00+08:00",
            "session_date": "2026-01-01",
            "effective_daily_bar_date": "2025-12-31",
            "is_market_open_now": False,
            "is_partial_bar": False,
            "minutes_to_open": 900,
            "minutes_to_close": None,
            "trigger_source": "scheduled_job",
            "analysis_intent": "postmarket",
            "warnings": ["legacy_snapshot"],
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_kr_legacy_snapshot",
            report_type="simple",
            news_content="news",
            context_snapshot={"market_phase_summary": persisted_phase_summary},
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        service = HistoryService(self.db)
        with patch("src.services.history_service.resolve_index_stock_code", return_value="005930.KS"):
            items = service.get_history_list(page=1, limit=5)["items"]

        self.assertEqual(items[0]["stock_code"], "005930.KS")
        rebuilt = items[0]["market_phase_summary"]
        self.assertIsNotNone(rebuilt)
        self.assertEqual(rebuilt["market"], "kr")
        self.assertEqual(rebuilt["market_local_time"], "2026-01-01T11:00:00+09:00")
        self.assertEqual(rebuilt["effective_daily_bar_date"], "2025-12-30")
        self.assertIsNone(rebuilt["minutes_to_open"])

    def test_history_filter_and_stock_bar_merge_bare_and_resolved_jp_kr_codes(self) -> None:
        if get_stock_bar is None:
            self.skipTest("fastapi is not installed in this test environment")

        legacy = self._build_result()
        legacy.code = "005930"
        legacy.name = "Samsung Electronics"
        current = self._build_result()
        current.code = "005930.KS"
        current.name = "Samsung Electronics"

        self.assertGreater(
            self.db.save_analysis_history(
                result=legacy,
                query_id="query_kr_legacy",
                report_type="simple",
                news_content="news",
                context_snapshot={"market_phase_summary": _market_phase_summary()},
                save_snapshot=True,
            ),
            0,
        )
        self.assertGreater(
            self.db.save_analysis_history(
                result=current,
                query_id="query_kr_current",
                report_type="simple",
                news_content="news",
                context_snapshot={"market_phase_summary": _market_phase_summary()},
                save_snapshot=True,
            ),
            0,
        )

        with patch("src.services.history_service.resolve_index_stock_code", side_effect=lambda code: "005930.KS" if str(code).split(".", 1)[0] == "005930" else None):
            listing = HistoryService(self.db).get_history_list(stock_code="005930.KS", page=1, limit=10)
            stock_bar = get_stock_bar(
                start_date=None,
                end_date=None,
                limit=10,
                db_manager=self.db,
            )

        self.assertEqual(listing["total"], 2)
        self.assertEqual({item["query_id"] for item in listing["items"]}, {"query_kr_legacy", "query_kr_current"})
        self.assertEqual(len(stock_bar.items), 1)
        self.assertEqual(stock_bar.items[0].stock_code, "005930.KS")
        self.assertEqual(stock_bar.items[0].analysis_count, 2)

    def test_save_analysis_history_persists_sniper_columns_via_shared_parser(self) -> None:
        """\u8fc1\u51fa sniper parser \u540e\u5386\u53f2\u72d9\u51fb\u70b9\u4f4d\u5217\u4ecd\u6309\u539f\u89c4\u5219\u4fdd\u5b58。"""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "\u7406\u60f3\u4e70\u5165\u70b9：125.5\u5143",
                    "secondary_buy": "1.52-1.53 (\u56de\u8e29MA5/10\u9644\u8fd1)",
                    "stop_loss": "—",
                    "take_profit": "\u76ee\u6807\u4f4d：150.0\u5143",
                }
            }
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_shared_sniper_parser",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False,
        )

        self.assertGreater(saved, 0)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_shared_sniper_parser"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            self.assertEqual(row.ideal_buy, 125.5)
            self.assertEqual(row.secondary_buy, 1.53)
            self.assertIsNone(row.stop_loss)
            self.assertEqual(row.take_profit, 150.0)

    def test_get_latest_analysis_history_id_filters_by_report_type_and_latest_record(self) -> None:
        """\u6309 query/code/report_type \u8fd4\u56de\u6700\u65b0\u771f\u5b9e\u5386\u53f2\u4e3b\u952e。"""
        for report_type in ("simple", "full", "simple"):
            saved = self.db.save_analysis_history(
                result=self._build_result(),
                query_id="query_latest_id",
                report_type=report_type,
                news_content="\u65b0\u95fb\u6458\u8981",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertGreater(saved, 0)

        simple_id = self.db.get_latest_analysis_history_id(
            query_id="query_latest_id",
            code="600519",
            report_type="simple",
        )
        full_id = self.db.get_latest_analysis_history_id(
            query_id="query_latest_id",
            code="600519",
            report_type="full",
        )

        self.assertIsNotNone(simple_id)
        self.assertIsNotNone(full_id)
        self.assertGreater(simple_id, full_id)

    def test_get_latest_analysis_history_id_requires_report_type(self) -> None:
        """report_type \u662f\u5fc5\u4f20\u53c2\u6570，\u907f\u514d\u8bef\u53d6\u540c query/code \u7684\u5176\u4ed6\u62a5\u544a。"""
        with self.assertRaises(TypeError):
            self.db.get_latest_analysis_history_id(query_id="query", code="600519")

    def test_save_analysis_history_without_snapshot(self) -> None:
        """\u5173\u95ed\u5feb\u7167\u4fdd\u5b58\u65f6\u4e0d\u5199\u5165 context_snapshot"""
        result = self._build_result()

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_002",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot={"foo": "bar"},
            save_snapshot=False
        )

        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            self.assertIsNone(row.context_snapshot)

    def test_save_analysis_history_persists_model_used(self) -> None:
        """model_used should be persisted in raw_result for history detail."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_003",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_003").first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            payload = json.loads(row.raw_result or "{}")
            self.assertEqual(payload.get("model_used"), "gemini/gemini-2.0-flash")

    def test_update_analysis_history_diagnostics_preserves_snapshot_fields(self) -> None:
        """\u901a\u77e5\u53d1\u9001\u540e\u8865\u5199 diagnostics \u65f6，\u4e0d\u5e94\u8986\u76d6\u5df2\u6709\u4e0a\u4e0b\u6587\u5b57\u6bb5。"""
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id="query_diag_patch",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot={
                "enhanced_context": {"code": "600519"},
                "diagnostics": {
                    "trace_id": "trace-1",
                    "query_id": "query_diag_patch",
                    "stock_code": "600519",
                    "notification_runs": [],
                },
            },
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        updated = self.db.update_analysis_history_diagnostics(
            query_id="query_diag_patch",
            code="600519",
            notification_runs=[
                {
                    "channel": "report",
                    "status": "success",
                    "success": True,
                }
            ],
        )

        self.assertEqual(updated, 1)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_diag_patch"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            snapshot = json.loads(row.context_snapshot or "{}")
            self.assertEqual(snapshot["enhanced_context"]["code"], "600519")
            notification_run = snapshot["diagnostics"]["notification_runs"][-1]
            self.assertEqual(notification_run["status"], "success")
            self.assertEqual(notification_run["trace_id"], "trace-1")

    def test_history_detail_hides_placeholder_model_used(self) -> None:
        """Placeholder model values should be normalized to None in detail response."""
        result = self._build_result()
        result.model_used = "unknown"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_004",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_004").first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertIsNone(detail.get("model_used"))

    def test_history_list_includes_timeline_summary_fields(self) -> None:
        """History list items expose the fields needed by the same-stock timeline drawer."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.5-pro"
        context_snapshot = {
            "enhanced_context": {
                "realtime": {
                    "price": "51.5",
                    "change_pct": "-4.61%",
                    "volume_ratio": "1.17",
                    "turnover_rate": "11.46",
                },
            },
            "market_phase_summary": _market_phase_summary(),
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_timeline_summary",
            report_type="detailed",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        service = HistoryService(self.db)
        payload = service.get_history_list(stock_code="600519.SH", page=1, limit=5)

        self.assertEqual(payload["total"], 1)
        item = payload["items"][0]
        self.assertEqual(item["stock_code"], "600519")
        self.assertEqual(item["trend_prediction"], "\u770b\u591a")
        self.assertEqual(item["analysis_summary"], "\u57fa\u672c\u9762\u7a33\u5065，\u77ed\u671f\u9707\u8361")
        self.assertEqual(item["operation_advice"], "\u6301\u6709")
        self.assertEqual(item["action"], "buy")
        self.assertEqual(item["action_label"], "\u4e70\u5165")
        self.assertEqual(item["model_used"], "gemini/gemini-2.5-pro")
        self.assertEqual(item["current_price"], 51.5)
        self.assertEqual(item["change_pct"], -4.61)
        self.assertEqual(item["volume_ratio"], 1.17)
        self.assertEqual(item["turnover_rate"], 11.46)
        self.assertEqual(item["market_phase_summary"]["phase"], "intraday")
        self.assertEqual(item["market_phase_summary"]["minutes_to_close"], 300)

    def test_history_persistence_keeps_softened_operation_advice_from_guardrail(self) -> None:
        """Conservative-market guardrail short operation_advice is persisted and exposed to history list."""
        result = self._build_result()
        result.decision_type = "buy"
        result.operation_advice = "\u7acb\u5373\u4e70\u5165\u5e76\u79ef\u6781\u52a0\u4ed3"

        apply_daily_market_context_guardrail(
            result,
            daily_market_context={
                "region": "cn",
                "trade_date": "2026-06-06",
                "summary": "\u5927\u76d8\u9000\u6f6e，\u9ad8\u98ce\u9669，\u5efa\u8bae\u89c2\u671b，\u4ed3\u4f4d\u4e0a\u965030%。",
                "risk_tags": ["high_risk", "low_position_cap"],
            },
            report_language="zh",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_softened_operation_advice",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        service = HistoryService(self.db)
        payload = service.get_history_list(stock_code="600519", page=1, limit=10)

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["operation_advice"], "\u89c2\u671b")
        self.assertLessEqual(len(payload["items"][0]["operation_advice"]), 20)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_softened_operation_advice"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            self.assertEqual(row.operation_advice, "\u89c2\u671b")

    def test_market_review_history_can_be_filtered_without_stock_records(self) -> None:
        """Market review records should be queryable as a dedicated history collection."""
        stock_result = self._build_result()
        market_result = AnalysisResult(
            code="MARKET",
            name="\u5927\u76d8\u590d\u76d8",
            sentiment_score=50,
            trend_prediction="\u5927\u76d8\u590d\u76d8",
            operation_advice="\u67e5\u770b\u590d\u76d8",
            analysis_summary="\u5927\u76d8\u590d\u76d8\u6458\u8981",
        )

        self.assertGreater(
            self.db.save_analysis_history(
                result=stock_result,
                query_id="query_stock_history",
                report_type="detailed",
                news_content="\u4e2a\u80a1\u6b63\u6587",
                context_snapshot=None,
                save_snapshot=False,
            ),
            0,
        )
        self.assertGreater(
            self.db.save_analysis_history(
                result=market_result,
                query_id="query_market_review_history",
                report_type="market_review",
                news_content="\u5927\u76d8\u590d\u76d8\u6b63\u6587",
                context_snapshot={
                    "report_kind": "market_review",
                    "market_review_payload": {
                        "kind": "market_review",
                        "sections": [{"title": "\u590d\u76d8", "markdown": "\u7ed3\u6784\u5316\u6b63\u6587"}],
                    },
                },
                save_snapshot=True,
            ),
            0,
        )

        service = HistoryService(self.db)
        payload = service.get_history_list(
            stock_code="MARKET",
            report_type="market_review",
            page=1,
            limit=10,
        )

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["stock_code"], "MARKET")
        self.assertEqual(payload["items"][0]["report_type"], "market_review")
        self.assertIsNone(payload["items"][0]["action"])
        self.assertIsNone(payload["items"][0]["action_label"])

    def test_distinct_stock_bar_excludes_market_review_records_by_default(self) -> None:
        """The stock bar aggregation should not mix MARKET into ordinary stock entries."""
        stock_result = self._build_result()
        market_result = AnalysisResult(
            code="MARKET",
            name="\u5927\u76d8\u590d\u76d8",
            sentiment_score=50,
            trend_prediction="\u5927\u76d8\u590d\u76d8",
            operation_advice="\u67e5\u770b\u590d\u76d8",
            analysis_summary="\u5927\u76d8\u590d\u76d8\u6458\u8981",
        )

        self.assertGreater(
            self.db.save_analysis_history(
                result=stock_result,
                query_id="query_stock_bar_stock",
                report_type="detailed",
                news_content="\u4e2a\u80a1\u6b63\u6587",
                context_snapshot=None,
                save_snapshot=False,
            ),
            0,
        )
        self.assertGreater(
            self.db.save_analysis_history(
                result=market_result,
                query_id="query_stock_bar_market",
                report_type="market_review",
                news_content="\u5927\u76d8\u590d\u76d8\u6b63\u6587",
                context_snapshot=None,
                save_snapshot=False,
            ),
            0,
        )

        records = self.db.get_distinct_stocks_from_history(limit=10)

        self.assertEqual([record.code for record in records], ["600519"])

    def test_stock_bar_item_derives_action_fields_from_legacy_advice(self) -> None:
        if get_stock_bar is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        result.operation_advice = "\u4e0d\u5efa\u8bae\u4e70\u5165"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_stock_bar_action",
            report_type="detailed",
            news_content="\u4e2a\u80a1\u6b63\u6587",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        response = get_stock_bar(
            start_date=None,
            end_date=None,
            limit=10,
            db_manager=self.db,
        )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].operation_advice, "\u4e0d\u5efa\u8bae\u4e70\u5165")
        self.assertEqual(response.items[0].action, "avoid")
        self.assertEqual(response.items[0].action_label, "\u56de\u907f")

    def test_stock_bar_item_aligns_score_and_legacy_advice(self) -> None:
        if get_stock_bar is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        result.operation_advice = "\u6301\u6709"
        result.sentiment_score = 78

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_stock_bar_score_align",
            report_type="detailed",
            news_content="\u4e2a\u80a1\u6b63\u6587",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        response = get_stock_bar(
            start_date=None,
            end_date=None,
            limit=10,
            db_manager=self.db,
        )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].operation_advice, "\u6301\u6709")
        self.assertEqual(response.items[0].sentiment_score, 78)
        self.assertEqual(response.items[0].action, "buy")
        self.assertEqual(response.items[0].action_label, "\u4e70\u5165")

    def test_stock_bar_item_falls_back_to_raw_result_summary_fields(self) -> None:
        if get_stock_bar is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        result.operation_advice = "Hold"
        result.report_language = "en"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_stock_bar_raw_fallback",
            report_type="detailed",
            news_content="stock report",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.session_scope() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_stock_bar_raw_fallback"
            ).first()
            self.assertIsNotNone(row)
            row.sentiment_score = None
            row.operation_advice = None

        response = get_stock_bar(
            start_date=None,
            end_date=None,
            limit=10,
            db_manager=self.db,
        )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].sentiment_score, 78)
        self.assertEqual(response.items[0].operation_advice, "Hold")
        self.assertEqual(response.items[0].action, "buy")
        self.assertEqual(response.items[0].action_label, "Buy")

    def test_history_detail_uses_service_resolved_action_fields(self) -> None:
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        service = MagicMock()
        service.resolve_and_get_detail.return_value = {
            "id": 1,
            "query_id": "query_action_conflict",
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "report_type": "detailed",
            "report_language": "zh",
            "created_at": "2026-05-21T17:40:00",
            "sentiment_score": 45,
            "operation_advice": "\u6301\u6709\u89c2\u5bdf",
            "action": "watch",
            "action_label": "\u89c2\u671b",
            "trend_prediction": "\u9707\u8361",
            "analysis_summary": "\u7b49\u5f85\u786e\u8ba4",
            "raw_result": {
                "operation_advice": "\u6301\u6709\u89c2\u5bdf",
                "action": "watch",
                "report_language": "zh",
            },
        }

        with patch("api.v1.endpoints.history.HistoryService", return_value=service):
            response = get_history_detail("query_action_conflict", db_manager=self.db)

        self.assertEqual(response.summary.operation_advice, "\u6301\u6709\u89c2\u5bdf")
        self.assertEqual(response.summary.action, "watch")
        self.assertEqual(response.summary.action_label, "\u89c2\u671b")

    def test_history_list_matches_equivalent_suffixed_stock_codes(self) -> None:
        """Same-stock history should include rows saved with supported suffixed codes."""

        def save_record(code: str, query_id: str) -> None:
            result = self._build_result()
            result.code = code
            if "HK" in code:
                result.name = "\u817e\u8baf\u63a7\u80a1"
            saved = self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type="simple",
                news_content="\u65b0\u95fb\u6458\u8981",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertGreater(saved, 0)

        save_record("600519.SH", "query_cn_suffix")
        save_record("600519", "query_cn_plain")
        save_record("00700.HK", "query_hk_suffix")
        save_record("HK00700", "query_hk_prefix")

        service = HistoryService(self.db)

        cn_from_suffix = service.get_history_list(stock_code="600519.SH", page=1, limit=10)
        self.assertEqual(cn_from_suffix["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in cn_from_suffix["items"]},
            {"600519.SH", "600519"},
        )

        cn_from_plain = service.get_history_list(stock_code="600519", page=1, limit=10)
        self.assertEqual(cn_from_plain["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in cn_from_plain["items"]},
            {"600519.SH", "600519"},
        )

        hk_from_suffix = service.get_history_list(stock_code="00700.HK", page=1, limit=10)
        self.assertEqual(hk_from_suffix["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_suffix["items"]},
            {"00700.HK", "HK00700"},
        )

        hk_from_prefix = service.get_history_list(stock_code="HK00700", page=1, limit=10)
        self.assertEqual(hk_from_prefix["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_prefix["items"]},
            {"00700.HK", "HK00700"},
        )

    def test_history_list_matches_unpadded_hk_suffix_variants(self) -> None:
        """HK short suffix forms (e.g. 1810.HK) should match 5-digit canonical suffix/prefix forms."""

        def save_record(code: str, query_id: str) -> None:
            result = self._build_result()
            result.code = code
            if "HK" in code:
                result.name = "\u817e\u8baf\u63a7\u80a1"
            saved = self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type="simple",
                news_content="\u65b0\u95fb\u6458\u8981",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertGreater(saved, 0)

        save_record("1810.HK", "query_hk_unpadded")
        save_record("01810.HK", "query_hk_padded")
        save_record("HK01810", "query_hk_prefix")

        service = HistoryService(self.db)

        hk_from_suffix = service.get_history_list(stock_code="01810.HK", page=1, limit=10)
        self.assertEqual(hk_from_suffix["total"], 3)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_suffix["items"]},
            {"1810.HK", "01810.HK", "HK01810"},
        )

        hk_from_prefix = service.get_history_list(stock_code="HK01810", page=1, limit=10)
        self.assertEqual(hk_from_prefix["total"], 3)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_prefix["items"]},
            {"1810.HK", "01810.HK", "HK01810"},
        )

    def test_history_list_matches_sh_and_ss_suffixed_variants(self) -> None:
        """SH suffix and legacy `.SS` variants should be treated as the same A-share stock."""

        def save_record(code: str, query_id: str) -> None:
            result = self._build_result()
            result.code = code
            saved = self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type="simple",
                news_content="\u65b0\u95fb\u6458\u8981",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertGreater(saved, 0)

        save_record("600519.SH", "query_cn_sh")
        save_record("600519.SS", "query_cn_ss")
        save_record("600519", "query_cn_plain")

        service = HistoryService(self.db)
        expected = {"600519.SH", "600519.SS", "600519"}

        from_sh = service.get_history_list(stock_code="600519.SH", page=1, limit=10)
        self.assertEqual(from_sh["total"], 3)
        self.assertEqual({item["stock_code"] for item in from_sh["items"]}, expected)

        from_ss = service.get_history_list(stock_code="600519.SS", page=1, limit=10)
        self.assertEqual(from_ss["total"], 3)
        self.assertEqual({item["stock_code"] for item in from_ss["items"]}, expected)

        from_plain = service.get_history_list(stock_code="600519", page=1, limit=10)
        self.assertEqual(from_plain["total"], 3)
        self.assertEqual({item["stock_code"] for item in from_plain["items"]}, expected)

    def test_history_detail_preserves_zero_change_pct(self) -> None:
        """change_pct=0.0（\u5e73\u76d8）\u5e94\u539f\u6837\u8fd4\u56de，\u800c\u4e0d\u662f\u88ab\u5f53\u6210\u7f3a\u5931\u503c\u4e22\u5931。

        Regression for issue #1084: history endpoint used `or` chains that
        treated 0.0 as falsy and silently dropped the daily change.
        """
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "enhanced_context": {
                "realtime": {"price": 100.0, "change_pct": 0.0},
            }
        }
        query_id = "query_change_pct_zero"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.current_price, 100.0)
        self.assertEqual(report.meta.change_pct, 0.0)

    def test_history_detail_falls_back_to_realtime_quote_raw_change_pct(self) -> None:
        """\u7f3a\u5c11 enhanced_context.realtime.change_pct \u65f6，\u5e94\u56de\u9000\u5230 realtime_quote_raw。

        Regression for issue #1084: previously the realtime_quote_raw fallback
        was only consulted when current_price was missing, so reports with
        price-only enhanced_context lost their change_pct entirely.
        """
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "enhanced_context": {
                "realtime": {"price": 200.0},
            },
            "realtime_quote_raw": {"change_pct": 1.23},
        }
        query_id = "query_change_pct_fallback"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.current_price, 200.0)
        self.assertEqual(report.meta.change_pct, 1.23)

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_history_detail_ignores_non_dict_realtime_quote_raw(self, mock_auth) -> None:
        """GET /api/v1/history/{id} should tolerate truthy non-dict realtime_quote_raw."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "enhanced_context": {
                "realtime": {"price": 300.0},
            },
            "realtime_quote_raw": "not-a-dict",
        }
        query_id = "query_change_pct_non_dict_raw"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.get(f"/api/v1/history/{record_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["current_price"], 300.0)
        self.assertIsNone(payload["meta"]["change_pct"])

    def test_history_detail_accepts_dict_raw_result(self) -> None:
        """_record_to_detail_dict should handle dict raw_result without json.loads errors."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_005",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_005").first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            row.raw_result = {"model_used": "unknown", "extra": "v"}

            service = HistoryService(self.db)
            detail = service._record_to_detail_dict(row)

        self.assertIsNotNone(detail)
        self.assertIsInstance(detail.get("raw_result"), dict)
        self.assertIsNone(detail.get("model_used"))

    def test_history_detail_prefers_raw_sniper_strings(self) -> None:
        """History detail should display the original sniper point strings from raw_result."""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "\u7406\u60f3\u4e70\u5165\u70b9：125.5\u5143",
                    "secondary_buy": "120-121 \u5143\u5206\u6279",
                    "stop_loss": "\u8dcc\u7834 110 \u5143\u6b62\u635f",
                    "take_profit": "\u76ee\u6807\u4f4d：150.0\u5143",
                }
            }
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_006",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_006").first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("ideal_buy"), "\u7406\u60f3\u4e70\u5165\u70b9：125.5\u5143")
        self.assertEqual(detail.get("secondary_buy"), "120-121 \u5143\u5206\u6279")
        self.assertEqual(detail.get("stop_loss"), "\u8dcc\u7834 110 \u5143\u6b62\u635f")
        self.assertEqual(detail.get("take_profit"), "\u76ee\u6807\u4f4d：150.0\u5143")

    def test_history_detail_falls_back_to_numeric_sniper_columns(self) -> None:
        """History detail should still fall back to stored numeric sniper columns when raw strings are unavailable."""
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_007",
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_007").first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            row.ideal_buy = 125.5
            row.secondary_buy = 120.0
            row.stop_loss = 110.0
            row.take_profit = 150.0
            row.raw_result = json.dumps({"model_used": "gemini/gemini-2.0-flash"})
            session.commit()
            self.assertEqual(row.id, saved)
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("ideal_buy"), "125.5")
        self.assertEqual(detail.get("secondary_buy"), "120.0")
        self.assertEqual(detail.get("stop_loss"), "110.0")
        self.assertEqual(detail.get("take_profit"), "150.0")

    def test_history_detail_uses_fundamental_snapshot_fallback_when_context_missing(self) -> None:
        """When context_snapshot is disabled, detail API should fallback to fundamental_snapshot."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        query_id = "query_fundamental_fallback_001"
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        self.db.save_fundamental_snapshot(
            query_id=query_id,
            code="600519",
            payload={
                "belong_boards": [{"name": "\u767d\u9152", "type": "\u884c\u4e1a"}],
                "boards": {
                    "data": {
                        "top": [{"name": "\u767d\u9152", "change_pct": 2.6}],
                        "bottom": [],
                    }
                },
                "concept_boards": {
                    "data": {
                        "top": [{"name": "\u673a\u5668\u4eba\u6982\u5ff5", "change_pct": 4.2}],
                        "bottom": [],
                    }
                },
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_dividend_yield_pct": 2.6, "ttm_cash_dividend_per_share": 1.3},
                    }
                }
            },
        )

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.financial_report["report_date"], "2025-12-31")
        self.assertEqual(report.details.dividend_metrics["ttm_dividend_yield_pct"], 2.6)
        self.assertEqual(report.details.belong_boards, [{"name": "\u767d\u9152", "type": "\u884c\u4e1a"}])
        self.assertEqual(report.details.sector_rankings["top"][0]["name"], "\u767d\u9152")
        self.assertEqual(report.details.concept_rankings["top"][0]["name"], "\u673a\u5668\u4eba\u6982\u5ff5")

    def test_history_detail_uses_raw_code_for_legacy_jp_kr_fundamental_snapshot(self) -> None:
        """Legacy bare JP/KR history rows should display suffixes but read snapshots by stored code."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        result.code = "005930"
        result.name = "Samsung Electronics"
        query_id = "query_kr_raw_fundamental_fallback"
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        self.db.save_fundamental_snapshot(
            query_id=query_id,
            code="005930",
            payload={
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_dividend_yield_pct": 2.6},
                    }
                }
            },
        )

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        with patch("src.services.history_service.resolve_index_stock_code", return_value="005930.KS"):
            report = get_history_detail(str(record_id), db_manager=self.db)

        self.assertEqual(report.meta.stock_code, "005930.KS")
        self.assertEqual(report.details.financial_report["report_date"], "2025-12-31")
        self.assertEqual(report.details.dividend_metrics["ttm_dividend_yield_pct"], 2.6)

    def test_history_detail_preserves_unavailable_board_rankings_state(self) -> None:
        """Failed board ranking blocks should remain unavailable in detail response."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_fundamental_failed_boards_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        fallback_fundamental = {
            "belong_boards": [{"name": "\u767d\u9152", "type": "\u884c\u4e1a"}],
            "boards": {
                "status": "failed",
                "data": {},
            },
        }
        saved_snapshot = self.db.save_fundamental_snapshot(
            query_id=query_id,
            code="600519",
            payload=fallback_fundamental,
        )
        self.assertGreater(saved_snapshot, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.belong_boards, [{"name": "\u767d\u9152", "type": "\u884c\u4e1a"}])
        self.assertIsNone(report.details.sector_rankings)

    def test_history_detail_returns_null_fundamental_fields_when_snapshot_absent(self) -> None:
        """Detail API should keep new fields nullable when no context/fundamental snapshot exists."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_fundamental_fallback_002"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertIsNone(report.details.financial_report)
        self.assertIsNone(report.details.dividend_metrics)
        self.assertEqual(report.details.belong_boards, [])
        self.assertIsNone(report.details.sector_rankings)

    def test_history_detail_returns_empty_related_boards_for_non_cn(self) -> None:
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=65,
            trend_prediction="Bullish",
            operation_advice="Hold",
            analysis_summary="US stock test",
        )
        query_id = "query_non_cn_board_001"
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.belong_boards, [])
        self.assertIsNone(report.details.sector_rankings)

    def test_history_detail_reads_agent_snapshot_related_boards_shape(self) -> None:
        """Agent-mode snapshots store fundamental_context/realtime_quote at the top level."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "fundamental_context": {
                "belong_boards": [{"name": "\u767d\u9152", "type": "\u884c\u4e1a"}],
                "boards": {
                    "data": {
                        "top": [{"name": "\u767d\u9152", "change_pct": 2.8}],
                        "bottom": [],
                    }
                },
            },
            "realtime_quote": {
                "price": 1888.0,
                "change_pct": 1.56,
            },
        }
        query_id = "query_agent_snapshot_boards_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.current_price, 1888.0)
        self.assertEqual(report.meta.change_pct, 1.56)
        self.assertEqual(report.details.belong_boards, [{"name": "\u767d\u9152", "type": "\u884c\u4e1a"}])
        self.assertEqual(report.details.sector_rankings["top"][0]["name"], "\u767d\u9152")

    def test_history_detail_returns_overview_and_sanitizes_snapshot(self) -> None:
        """History detail exposes the public overview separately from raw snapshot JSON."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        overview = _analysis_context_pack_overview()
        phase_summary = _market_phase_summary()
        query_id = "query_context_pack_overview_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot={
                "enhanced_context": {"code": "600519"},
                "analysis_context_pack_overview": overview,
                "market_phase_summary": {
                    **phase_summary,
                    "market_phase_context": {"raw": True},
                },
            },
            save_snapshot=True,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(
            report.details.analysis_context_pack_overview.metadata.trigger_source,
            "api",
        )
        self.assertEqual(
            report.details.analysis_context_pack_overview.data_quality.overall_score,
            100,
        )
        self.assertIsNotNone(report.meta.market_phase_summary)
        self.assertEqual(report.meta.market_phase_summary.phase, "intraday")
        self.assertEqual(report.meta.market_phase_summary.minutes_to_close, 300)
        self.assertEqual(report.details.analysis_context_pack_overview.metadata.news_result_count, 2)
        self.assertNotIn(
            "analysis_context_pack_overview",
            report.details.context_snapshot,
        )
        self.assertNotIn(
            "market_phase_summary",
            report.details.context_snapshot,
        )

    def test_history_detail_handles_missing_overview_when_snapshot_disabled(self) -> None:
        """SAVE_CONTEXT_SNAPSHOT=false style records should not require an overview."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_context_pack_snapshot_disabled_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="\u65b0\u95fb\u6458\u8981",
            context_snapshot={
                "enhanced_context": {"code": "600519"},
                "analysis_context_pack_overview": _analysis_context_pack_overview(),
            },
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id
            self.assertIsNone(row.context_snapshot)

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertIsNone(report.meta.market_phase_summary)
        self.assertIsNone(report.details.analysis_context_pack_overview)
        self.assertIsNone(report.details.context_snapshot)

    def test_history_markdown_localizes_english_report_and_placeholder_name(self) -> None:
        """History markdown should preserve report_language for English reports."""
        result = AnalysisResult(
            code="AAPL",
            name="\u80a1\u7968AAPL",
            sentiment_score=78,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
            dashboard={
                "core_conclusion": {
                    "one_sentence": "Favor buying on pullbacks.",
                    "position_advice": {
                        "no_position": "Open a starter position.",
                        "has_position": "Hold and trail the stop.",
                    },
                },
                "intelligence": {
                    "risk_alerts": [],
                },
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "180-182",
                        "stop_loss": "172",
                        "take_profit": "195",
                    }
                },
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_markdown_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_markdown_001"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("Stock Analysis Report", markdown)
        self.assertIn("Core Conclusion", markdown)
        self.assertIn("Unnamed Stock (AAPL)", markdown)
        self.assertNotIn("\u6838\u5fc3\u7ed3\u8bba", markdown)

    def test_history_markdown_returns_persisted_market_review_report(self) -> None:
        """Market review history should return the saved Markdown without rebuilding a stock report."""
        result = AnalysisResult(
            code="MARKET",
            name="\u5927\u76d8\u590d\u76d8",
            sentiment_score=50,
            trend_prediction="\u5927\u76d8\u590d\u76d8",
            operation_advice="\u67e5\u770b\u590d\u76d8",
            analysis_summary="\u4eca\u65e5\u5927\u76d8\u590d\u76d8",
            raw_response="# 🎯 \u5927\u76d8\u590d\u76d8\n\n## \u4eca\u65e5\u5927\u76d8\n\n\u590d\u76d8\u6b63\u6587",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="market_review_query_001",
            report_type="market_review",
            news_content="## \u4eca\u65e5\u5927\u76d8\n\n\u590d\u76d8\u6b63\u6587",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "market_review_query_001"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertEqual(markdown, "# 🎯 \u5927\u76d8\u590d\u76d8\n\n## \u4eca\u65e5\u5927\u76d8\n\n\u590d\u76d8\u6b63\u6587")

    def test_history_markdown_collapses_unavailable_chip_structure(self) -> None:
        result = AnalysisResult(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            sentiment_score=72,
            trend_prediction="\u770b\u591a",
            operation_advice="\u6301\u6709",
            analysis_summary="\u7a33\u5065",
            dashboard={
                "data_perspective": {
                    "chip_structure": {
                        "profit_ratio": "\u6570\u636e\u7f3a\u5931，\u65e0\u6cd5\u5224\u65ad",
                        "avg_cost": "\u6570\u636e\u7f3a\u5931，\u65e0\u6cd5\u5224\u65ad",
                        "concentration": "\u6570\u636e\u7f3a\u5931，\u65e0\u6cd5\u5224\u65ad",
                        "chip_health": "\u6570\u636e\u7f3a\u5931，\u65e0\u6cd5\u5224\u65ad",
                    }
                }
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_chip_unavailable_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_chip_unavailable_001"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("**\u7b79\u7801**: \u7b79\u7801\u5206\u5e03\u672a\u542f\u7528\u6216\u6570\u636e\u6e90\u6682\u4e0d\u53ef\u7528，\u672a\u7eb3\u5165\u7b79\u7801\u5224\u65ad。", markdown)
        self.assertEqual(markdown.count("\u6570\u636e\u7f3a\u5931，\u65e0\u6cd5\u5224\u65ad"), 0)

    def test_history_detail_returns_persisted_market_review_report(self) -> None:
        """Market review detail should surface the saved recap content for Web history clicks."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        report_content = "# 🎯 \u5927\u76d8\u590d\u76d8\n\n## \u4eca\u65e5\u5927\u76d8\n\n\u590d\u76d8\u6b63\u6587"
        result = AnalysisResult(
            code="MARKET",
            name="\u5927\u76d8\u590d\u76d8",
            sentiment_score=50,
            trend_prediction="\u5927\u76d8\u590d\u76d8",
            operation_advice="\u67e5\u770b\u590d\u76d8",
            analysis_summary="\u4eca\u65e5\u5927\u76d8\u590d\u76d8",
            raw_response=report_content,
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="market_review_query_detail_001",
            report_type="market_review",
            news_content="## \u4eca\u65e5\u5927\u76d8\n\n\u590d\u76d8\u6b63\u6587",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "market_review_query_detail_001"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)

        self.assertEqual(report.meta.report_type, "market_review")
        self.assertEqual(report.summary.analysis_summary, report_content)
        self.assertIsNone(report.summary.action)
        self.assertIsNone(report.summary.action_label)
        self.assertEqual(report.details.news_content, report_content)

    def test_history_detail_localizes_english_summary_fields(self) -> None:
        """History detail should localize summary enums for English reports."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = AnalysisResult(
            code="AAPL",
            name="\u80a1\u7968AAPL",
            sentiment_score=78,
            trend_prediction="\u770b\u591a",
            operation_advice="\u4e70\u5165",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_detail_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_detail_001"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)

        self.assertEqual(report.meta.report_language, "en")
        self.assertEqual(report.meta.stock_name, "Unnamed Stock")
        self.assertEqual(report.summary.operation_advice, "Buy")
        self.assertEqual(report.summary.action, "buy")
        self.assertEqual(report.summary.action_label, "Buy")
        self.assertEqual(report.summary.trend_prediction, "Bullish")
        self.assertEqual(report.summary.sentiment_label, "Bullish")

    def test_history_markdown_uses_safe_bias_emoji_for_english_status(self) -> None:
        """English bias status should keep the correct non-risk emoji in markdown."""
        result = AnalysisResult(
            code="AAPL",
            name="\u80a1\u7968AAPL",
            sentiment_score=80,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
            dashboard={
                "data_perspective": {
                    "price_position": {
                        "current_price": 190.5,
                        "ma5": 188.0,
                        "ma10": 184.5,
                        "ma20": 179.2,
                        "bias_ma5": 1.33,
                        "bias_status": "Safe",
                        "support_level": 184.5,
                        "resistance_level": 195.0,
                    }
                }
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_markdown_bias_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertGreater(saved, 0)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_markdown_bias_001"
            ).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u5386\u53f2\u8bb0\u5f55")
            self.assertEqual(row.id, saved)
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("✅Safe", markdown)
        self.assertNotIn("🚨Safe", markdown)

    def test_delete_analysis_history_records_also_cleans_backtests_and_decision_signals(self) -> None:
        """\u5220\u9664\u5386\u53f2\u8bb0\u5f55\u65f6\u5e94\u4e00\u5e76\u6e05\u7406\u5173\u8054\u56de\u6d4b\u7ed3\u679c\u548c\u51b3\u7b56\u4fe1\u53f7。"""
        record_id = self._save_history("query_delete_001")
        linked_signal_id = None

        with self.db.session_scope() as session:
            session.add(BacktestResult(
                analysis_history_id=record_id,
                code="600519",
                analysis_date=None,
                eval_window_days=10,
                engine_version="v1",
                eval_status="pending",
            ))
            linked_signal = DecisionSignalRecord(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                market="cn",
                source_type="analysis",
                source_report_id=record_id,
                trace_id="trace-delete-linked",
                market_phase="intraday",
                trigger_source="api",
                action="buy",
                action_label="\u4e70\u5165",
                reason="linked",
                plan_quality="minimal",
                status="active",
            )
            session.add(linked_signal)
            session.flush()
            linked_signal_id = linked_signal.id
            session.add(DecisionSignalOutcomeRecord(
                signal_id=linked_signal_id,
                horizon="3d",
                engine_version="decision-signal-v1",
                eval_status="completed",
                outcome="hit",
                action="buy",
                market="cn",
                source_type="analysis",
                plan_quality="minimal",
                holding_state="holding",
            ))
            session.add(DecisionSignalFeedbackRecord(
                signal_id=linked_signal_id,
                feedback_value="useful",
                source="api",
            ))
            session.add(DecisionSignalRecord(
                stock_code="000001",
                stock_name="\u5e73\u5b89\u94f6\u884c",
                market="cn",
                source_type="analysis",
                source_report_id=record_id + 999,
                trace_id="trace-delete-unrelated",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="\u89c2\u671b",
                reason="unrelated",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([record_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first())
            self.assertEqual(
                session.query(BacktestResult).filter(BacktestResult.analysis_history_id == record_id).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(DecisionSignalRecord.source_report_id == record_id).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalOutcomeRecord).filter(
                    DecisionSignalOutcomeRecord.signal_id == linked_signal_id
                ).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalFeedbackRecord).filter(
                    DecisionSignalFeedbackRecord.signal_id == linked_signal_id
                ).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(DecisionSignalRecord.trace_id == "trace-delete-unrelated").count(),
                1,
            )

    def test_delete_analysis_history_records_keeps_signals_for_nonexistent_history_id(self) -> None:
        """\u4e0d\u5b58\u5728\u7684\u5386\u53f2 ID \u4e0d\u5e94\u89e6\u53d1\u5f31\u5173\u8054 DecisionSignal \u6e05\u7406。"""
        missing_id = 987654321

        with self.db.session_scope() as session:
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                market="cn",
                source_type="manual",
                source_report_id=missing_id,
                trace_id="trace-delete-missing-history",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="\u89c2\u671b",
                reason="manual signal with unverified report id",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([missing_id])
        self.assertEqual(deleted, 0)

        with self.db.get_session() as session:
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-missing-history"
                ).count(),
                1,
            )

    def test_delete_analysis_history_records_keeps_manual_signal_with_same_report_id(self) -> None:
        """source_report_id \u662f\u5f31\u5f15\u7528，\u771f\u5b9e history \u5220\u9664\u4e0d\u5e94\u8bef\u5220 manual/pre-report \u4fe1\u53f7。"""
        record_id = self._save_history("query_delete_manual_collision")

        with self.db.session_scope() as session:
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                market="cn",
                source_type="analysis",
                source_report_id=record_id,
                trace_id="trace-delete-analysis-bound",
                market_phase="intraday",
                trigger_source="api",
                action="buy",
                action_label="\u4e70\u5165",
                reason="history-bound signal",
                plan_quality="minimal",
                status="active",
            ))
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                market="cn",
                source_type="manual",
                source_report_id=record_id,
                trace_id="trace-delete-manual-weak-ref",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="\u89c2\u671b",
                reason="manual signal with caller-supplied report id",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([record_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-analysis-bound"
                ).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-manual-weak-ref"
                ).count(),
                1,
            )

    def test_delete_analysis_history_records_cleans_only_existing_ids_in_mixed_batch(self) -> None:
        """\u6df7\u5408\u5b58\u5728/\u4e0d\u5b58\u5728 ID \u65f6，\u53ea\u6e05\u7406\u5b9e\u9645\u5b58\u5728\u5386\u53f2\u8bb0\u5f55\u7684\u5173\u8054\u6570\u636e。"""
        record_id = self._save_history("query_delete_mixed")
        missing_id = record_id + 987654

        with self.db.session_scope() as session:
            session.add(BacktestResult(
                analysis_history_id=record_id,
                code="600519",
                analysis_date=None,
                eval_window_days=10,
                engine_version="v1",
                eval_status="pending",
            ))
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                market="cn",
                source_type="analysis",
                source_report_id=record_id,
                trace_id="trace-delete-mixed-linked",
                market_phase="intraday",
                trigger_source="api",
                action="buy",
                action_label="\u4e70\u5165",
                reason="linked",
                plan_quality="minimal",
                status="active",
            ))
            session.add(DecisionSignalRecord(
                stock_code="000001",
                stock_name="\u5e73\u5b89\u94f6\u884c",
                market="cn",
                source_type="manual",
                source_report_id=missing_id,
                trace_id="trace-delete-mixed-missing",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="\u89c2\u671b",
                reason="weak report id collision",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([record_id, missing_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first())
            self.assertEqual(
                session.query(BacktestResult).filter(BacktestResult.analysis_history_id == record_id).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-mixed-linked"
                ).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-mixed-missing"
                ).count(),
                1,
            )

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_delete_history_api_deletes_selected_records(self, mock_auth) -> None:
        """DELETE /api/v1/history should remove only the requested records."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        record_id_1 = self._save_history("query_delete_api_001")
        record_id_2 = self._save_history("query_delete_api_002")

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.request(
            "DELETE",
            "/api/v1/history",
            json={"record_ids": [record_id_1]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("deleted"), 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_1).first())
            self.assertIsNotNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_2).first())


class HistoryItemSchemaNegativeSentimentTest(unittest.TestCase):
    """Regression: HistoryItem / ReportSummary must accept out-of-range sentiment_score from DB rows."""

    @classmethod
    def setUpClass(cls) -> None:
        """Import schema classes once for all tests, skipping gracefully when deps are missing."""
        try:
            from api.v1.schemas.history import HistoryItem, ReportSummary  # type: ignore
        except ModuleNotFoundError:
            cls.HistoryItem = None
            cls.ReportSummary = None
        else:
            cls.HistoryItem = HistoryItem
            cls.ReportSummary = ReportSummary

    def test_negative_sentiment_score_does_not_raise(self) -> None:
        """Bug #942: sentiment_score=-22 in DB should not cause Pydantic ValidationError."""
        if self.HistoryItem is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        item = self.HistoryItem(query_id="q1", stock_code="600519", sentiment_score=-22)
        self.assertEqual(item.sentiment_score, -22)

    def test_out_of_range_high_sentiment_score_does_not_raise(self) -> None:
        """HistoryItem should also accept scores above 100 from legacy data."""
        if self.HistoryItem is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        item = self.HistoryItem(query_id="q2", stock_code="600519", sentiment_score=150)
        self.assertEqual(item.sentiment_score, 150)

    def test_none_sentiment_score_is_allowed(self) -> None:
        """HistoryItem.sentiment_score=None should still be valid (optional field)."""
        if self.HistoryItem is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        item = self.HistoryItem(query_id="q3", stock_code="600519", sentiment_score=None)
        self.assertIsNone(item.sentiment_score)

    def test_report_summary_negative_sentiment_score_does_not_raise(self) -> None:
        """ReportSummary.sentiment_score should also accept negative values from legacy DB rows."""
        if self.ReportSummary is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        summary = self.ReportSummary(sentiment_score=-22)
        self.assertEqual(summary.sentiment_score, -22)

    def test_report_summary_out_of_range_high_sentiment_score_does_not_raise(self) -> None:
        """ReportSummary.sentiment_score should also accept scores above 100 from legacy data."""
        if self.ReportSummary is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        summary = self.ReportSummary(sentiment_score=150)
        self.assertEqual(summary.sentiment_score, 150)

    def test_report_summary_none_sentiment_score_is_allowed(self) -> None:
        """ReportSummary.sentiment_score=None should still be valid (optional field)."""
        if self.ReportSummary is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        summary = self.ReportSummary(sentiment_score=None)
        self.assertIsNone(summary.sentiment_score)


if __name__ == "__main__":
    unittest.main()
