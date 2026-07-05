# -*- coding: utf-8 -*-
"""
===================================
A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u65b0\u95fb\u60c5\u62a5\u5b58\u50a8\u5355\u5143\u6d4b\u8bd5
===================================

\u804c\u8d23：
1. \u9a8c\u8bc1\u65b0\u95fb\u60c5\u62a5\u7684\u4fdd\u5b58\u4e0e\u53bb\u91cd\u903b\u8f91
2. \u9a8c\u8bc1\u65e0 URL \u60c5\u51b5\u4e0b\u7684\u515c\u5e95\u53bb\u91cd\u952e
"""

import os
import sqlite3
import tempfile
import unittest

from datetime import datetime
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from src.config import Config
from src.storage import DatabaseManager, NewsIntel
from src.search_service import SearchResponse, SearchResult


class NewsIntelStorageTestCase(unittest.TestCase):
    """\u65b0\u95fb\u60c5\u62a5\u5b58\u50a8\u6d4b\u8bd5"""

    def setUp(self) -> None:
        """\u4e3a\u6bcf\u4e2a\u7528\u4f8b\u521d\u59cb\u5316\u72ec\u7acb\u6570\u636e\u5e93"""
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_news_intel.db")
        os.environ["DATABASE_PATH"] = self._db_path

        # \u91cd\u7f6e\u914d\u7f6e\u4e0e\u6570\u636e\u5e93\u5355\u4f8b，\u786e\u4fdd\u4f7f\u7528\u4e34\u65f6\u5e93
        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        """\u6e05\u7406\u8d44\u6e90"""
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _build_response(self, results) -> SearchResponse:
        """\u6784\u9020 SearchResponse \u5feb\u6377\u51fd\u6570"""
        return SearchResponse(
            query="\u8d35\u5dde\u8305\u53f0 \u6700\u65b0\u6d88\u606f",
            results=results,
            provider="Bocha",
            success=True,
        )

    def test_save_news_intel_with_url_dedup(self) -> None:
        """\u76f8\u540c URL \u53bb\u91cd，\u4ec5\u4fdd\u7559\u4e00\u6761\u8bb0\u5f55"""
        result = SearchResult(
            title="\u8305\u53f0\u53d1\u5e03\u65b0\u4ea7\u54c1",
            snippet="\u516c\u53f8\u53d1\u5e03\u65b0\u54c1...",
            url="https://news.example.com/a",
            source="example.com",
            published_date="2025-01-02"
        )
        response = self._build_response([result])

        query_context = {
            "query_id": "task_001",
            "query_source": "bot",
            "requester_platform": "feishu",
            "requester_user_id": "u_123",
            "requester_user_name": "\u6d4b\u8bd5\u7528\u6237",
            "requester_chat_id": "c_456",
            "requester_message_id": "m_789",
            "requester_query": "/analyze 600519",
        }

        saved_first = self.db.save_news_intel(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            dimension="latest_news",
            query=response.query,
            response=response,
            query_context=query_context
        )
        saved_second = self.db.save_news_intel(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            dimension="latest_news",
            query=response.query,
            response=response,
            query_context=query_context
        )

        self.assertEqual(saved_first, 1)
        self.assertEqual(saved_second, 0)

        with self.db.get_session() as session:
            total = session.query(NewsIntel).count()
            row = session.query(NewsIntel).first()
        self.assertEqual(total, 1)
        if row is None:
            self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u65b0\u95fb\u8bb0\u5f55")
        self.assertEqual(row.query_id, "task_001")
        self.assertEqual(row.requester_user_name, "\u6d4b\u8bd5\u7528\u6237")

    def test_save_news_intel_without_url_fallback_key(self) -> None:
        """\u65e0 URL \u65f6\u4f7f\u7528\u515c\u5e95\u952e\u53bb\u91cd"""
        result = SearchResult(
            title="\u8305\u53f0\u4e1a\u7ee9\u9884\u544a",
            snippet="\u4e1a\u7ee9\u5927\u5e45\u589e\u957f...",
            url="",
            source="example.com",
            published_date="2025-01-03"
        )
        response = self._build_response([result])

        saved_first = self.db.save_news_intel(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            dimension="earnings",
            query=response.query,
            response=response
        )
        saved_second = self.db.save_news_intel(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            dimension="earnings",
            query=response.query,
            response=response
        )

        self.assertEqual(saved_first, 1)
        self.assertEqual(saved_second, 0)

        with self.db.get_session() as session:
            row = session.query(NewsIntel).first()
            if row is None:
                self.fail("\u672a\u627e\u5230\u4fdd\u5b58\u7684\u65b0\u95fb\u8bb0\u5f55")
            self.assertTrue(row.url.startswith("no-url:"))

    def test_get_recent_news(self) -> None:
        """\u53ef\u6309\u65f6\u95f4\u8303\u56f4\u67e5\u8be2\u6700\u65b0\u65b0\u95fb"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = SearchResult(
            title="\u8305\u53f0\u80a1\u4ef7\u9707\u8361",
            snippet="\u76d8\u4e2d\u6ce2\u52a8\u8f83\u5927...",
            url="https://news.example.com/b",
            source="example.com",
            published_date=now
        )
        response = self._build_response([result])

        self.db.save_news_intel(
            code="600519",
            name="\u8d35\u5dde\u8305\u53f0",
            dimension="market_analysis",
            query=response.query,
            response=response
        )

        recent_news = self.db.get_recent_news(code="600519", days=7, limit=10)
        self.assertEqual(len(recent_news), 1)
        self.assertEqual(recent_news[0].title, "\u8305\u53f0\u80a1\u4ef7\u9707\u8361")

    def test_save_news_intel_retries_on_sqlite_locked_execute(self) -> None:
        result = SearchResult(
            title="\u8305\u53f0\u9501\u7ade\u4e89\u91cd\u8bd5",
            snippet="\u6a21\u62df SQLite locked...",
            url="https://news.example.com/retry",
            source="example.com",
            published_date="2025-01-05",
        )
        response = self._build_response([result])

        first_session = self.db.get_session()
        second_session = self.db.get_session()
        stmt_exc = OperationalError(
            "COMMIT",
            None,
            sqlite3.OperationalError("database is locked"),
        )

        with patch.object(self.db, "get_session", side_effect=[first_session, second_session]):
            with patch.object(first_session, "execute", side_effect=stmt_exc):
                with patch("src.storage.time.sleep") as mock_sleep:
                    saved_count = self.db.save_news_intel(
                        code="600519",
                        name="\u8d35\u5dde\u8305\u53f0",
                        dimension="latest_news",
                        query=response.query,
                        response=response,
                    )

        self.assertEqual(saved_count, 1)
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertAlmostEqual(mock_sleep.call_args.args[0], self.db._sqlite_write_retry_base_delay, places=6)

        with self.db.get_session() as session:
            total = session.query(NewsIntel).count()
        self.assertEqual(total, 1)


if __name__ == "__main__":
    unittest.main()
