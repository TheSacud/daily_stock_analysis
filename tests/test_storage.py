# -*- coding: utf-8 -*-
import unittest
import sys
import os
import sqlite3
import tempfile
import threading
from datetime import date
from unittest.mock import patch

import pandas as pd
from sqlalchemy import and_, create_engine as sqlalchemy_create_engine, select
from sqlalchemy.sql import func

# Ensure src module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.storage import Base, CURRENT_SCHEMA_VERSION, DatabaseManager, DatabaseSchemaMigration, StockDaily

class TestStorage(unittest.TestCase):

    @staticmethod
    def _list_sqlite_unique_indexes(db_path: str, table_name: str) -> dict[str, list[str]]:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
            unique_indexes = {}
            for row in rows:
                if int(row[2]) != 1:
                    continue
                index_name = row[1]
                index_columns = []
                for index_info in conn.execute(f"PRAGMA index_xinfo({index_name})").fetchall():
                    column_name = index_info[2]
                    if column_name is not None:
                        index_columns.append(column_name)
                unique_indexes[index_name] = index_columns
            return unique_indexes

    def test_legacy_intelligence_items_url_unique_index_rebuilds_without_collision(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "legacy_intel.sqlite")

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """CREATE TABLE intelligence_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    source_type TEXT NOT NULL DEFAULT 'rss',
                    url TEXT NOT NULL,
                    scope_type TEXT NOT NULL DEFAULT 'market',
                    scope_value TEXT,
                    market TEXT NOT NULL DEFAULT 'cn',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_status TEXT,
                    last_error TEXT,
                    last_fetched_at DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME
                )"""
                )
                conn.execute(
                    """CREATE TABLE intelligence_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER,
                    source_name TEXT,
                    source_type TEXT NOT NULL DEFAULT 'rss',
                    title TEXT NOT NULL,
                    summary TEXT,
                    url TEXT NOT NULL,
                    source TEXT,
                    published_at DATETIME,
                    fetched_at DATETIME,
                    scope_type TEXT NOT NULL DEFAULT 'market',
                    scope_value TEXT,
                    market TEXT NOT NULL DEFAULT 'cn',
                    raw_payload TEXT
                )"""
                )
                conn.execute("CREATE UNIQUE INDEX uix_intelligence_item_url_legacy ON intelligence_items(url)")
                conn.execute("CREATE INDEX ix_intel_item_scope_time ON intelligence_items(scope_type, scope_value, market, published_at)")
                conn.execute("CREATE INDEX ix_intel_item_fetch_time ON intelligence_items(fetched_at)")
                conn.execute("INSERT INTO intelligence_sources (name, url) VALUES ('legacy', 'https://legacy.example.com/rss.xml')")
                source_id = conn.execute("SELECT id FROM intelligence_sources WHERE name='legacy'").fetchone()[0]
                conn.executemany(
                    """INSERT INTO intelligence_items (
                    source_id,
                    source_name,
                    source_type,
                    title,
                    summary,
                    url,
                    source,
                    published_at,
                    fetched_at,
                    scope_type,
                    scope_value,
                    market,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (source_id, 'legacy-source', 'rss', 'A', 'legacy-a', 'https://legacy.example.com/a', 'legacy',
                         '2026-01-01 00:00:00', '2026-01-01 00:00:00', 'market', None, 'cn', None),
                        (source_id, 'legacy-source', 'rss', 'B', 'legacy-b', 'https://legacy.example.com/b', 'legacy',
                         '2026-01-02 00:00:00', '2026-01-02 00:00:00', 'market', None, 'cn', None),
                    ],
                )

            unique_indexes_before = self._list_sqlite_unique_indexes(db_path, "intelligence_items")
            self.assertIn("uix_intelligence_item_url_legacy", unique_indexes_before)
            self.assertEqual(unique_indexes_before["uix_intelligence_item_url_legacy"], ["url"])

            DatabaseManager.reset_instance()
            Config.reset_instance()
            DatabaseManager(db_url=f"sqlite:///{db_path}")

            unique_indexes_after = self._list_sqlite_unique_indexes(db_path, "intelligence_items")
            self.assertNotIn("uix_intelligence_item_url_legacy", unique_indexes_after)
            self.assertIn("uix_intel_item_scope", unique_indexes_after)
            self.assertEqual(
                unique_indexes_after["uix_intel_item_scope"],
                ["source_id", "url", "scope_type", "scope_value", "market"],
            )
            with sqlite3.connect(db_path) as conn:
                table_count = conn.execute("SELECT COUNT(*) FROM intelligence_items").fetchone()[0]
                temp_tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'intelligence_items_recreate_tmp_%'"
                ).fetchall()

            self.assertEqual(table_count, 2)
            self.assertEqual(temp_tables, [])
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            temp_dir.cleanup()

    def test_database_initialization_records_schema_version(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        with db.get_session() as session:
            row = session.get(DatabaseSchemaMigration, CURRENT_SCHEMA_VERSION)

        self.assertIsNotNone(row)
        self.assertEqual(row.version, CURRENT_SCHEMA_VERSION)
        self.assertIn("metadata.create_all", row.description)

        DatabaseManager.reset_instance()

    def test_schema_migration_record_is_idempotent(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db._ensure_schema_migration_record()
        db._ensure_schema_migration_record()

        with db.get_session() as session:
            count = session.execute(
                select(func.count()).select_from(DatabaseSchemaMigration)
            ).scalar_one()

        self.assertEqual(count, 1)

        DatabaseManager.reset_instance()

    def test_schema_migration_record_handles_concurrent_initialization(self):
        DatabaseManager.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "schema_migration_race.db")
        db = DatabaseManager(db_url=f"sqlite:///{db_path}")
        worker_count = 8
        barrier = threading.Barrier(worker_count)
        errors = []
        state_lock = threading.Lock()

        with db.get_session() as session:
            session.query(DatabaseSchemaMigration).delete()
            session.commit()

        def ensure_record() -> None:
            try:
                barrier.wait(timeout=5)
                db._ensure_schema_migration_record()
            except Exception as exc:
                with state_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=ensure_record) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        with db.get_session() as session:
            rows = session.execute(select(DatabaseSchemaMigration)).scalars().all()

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].version, CURRENT_SCHEMA_VERSION)

        DatabaseManager.reset_instance()
        temp_dir.cleanup()

    def test_parse_sniper_value(self):
        """\u6d4b\u8bd5\u89e3\u6790\u72d9\u51fb\u70b9\u4f4d\u6570\u503c"""

        # 1. \u6b63\u5e38\u6570\u503c
        self.assertEqual(DatabaseManager._parse_sniper_value(100), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value(100.5), 100.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("100"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("100.5"), 100.5)

        # 2. \u5305\u542b\u4e2d\u6587\u63cf\u8ff0\u548c"\u5143"
        self.assertEqual(DatabaseManager._parse_sniper_value("\u5efa\u8bae\u5728 100 \u5143\u9644\u8fd1\u4e70\u5165"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("\u4ef7\u683c：100.5\u5143"), 100.5)

        # 3. \u5305\u542b\u5e72\u6270\u6570\u5b57（\u4fee\u590d\u7684Bug\u573a\u666f）
        # \u4e4b\u524d "MA5" \u4f1a\u88ab\u9519\u8bef\u63d0\u53d6\u4e3a 5.0，\u73b0\u5728\u5e94\u8be5\u63d0\u53d6 "\u5143" \u524d\u9762\u7684 100
        text_bug = "\u65e0\u6cd5\u7ed9\u51fa。\u9700\u7b49\u5f85MA5\u6570\u636e\u6062\u590d，\u5728\u80a1\u4ef7\u56de\u8e29MA5\u4e14\u4e56\u79bb\u7387<2%\u65f6\u8003\u8651100\u5143"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_bug), 100.0)

        # 4. \u66f4\u591a\u5e72\u6270\u573a\u666f
        text_complex = "MA10\u4e3a20.5，\u5efa\u8bae\u572830\u5143\u4e70\u5165"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_complex), 30.0)

        text_multiple = "\u652f\u6491\u4f4d10\u5143，\u963b\u529b\u4f4d20\u5143" # \u5e94\u8be5\u63d0\u53d6\u6700\u540e\u4e00\u4e2a"\u5143"\u524d\u9762\u7684\u6570\u5b57，\u537320，\u6216\u8005\u66f4\u590d\u6742\u7684\u903b\u8f91？
        # \u5f53\u524d\u903b\u8f91\u662f\u627e\u6700\u540e\u4e00\u4e2a\u5192\u53f7，\u7136\u540e\u627e\u4e4b\u540e\u7684\u7b2c\u4e00\u4e2a"\u5143"，\u63d0\u53d6\u4e2d\u95f4\u7684\u6570\u5b57。
        # \u6d4b\u8bd5\u6ca1\u6709\u5192\u53f7\u7684\u60c5\u51b5
        self.assertEqual(DatabaseManager._parse_sniper_value("30\u5143"), 30.0)

        # \u6d4b\u8bd5\u591a\u4e2a\u6570\u5b57\u5728"\u5143"\u4e4b\u524d
        self.assertEqual(DatabaseManager._parse_sniper_value("MA5 10 20\u5143"), 20.0)

        # 5. Fallback: no "\u5143" character — extracts last non-MA number
        self.assertEqual(DatabaseManager._parse_sniper_value("102.10-103.00（MA5\u9644\u8fd1）"), 103.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("97.62-98.50（MA10\u9644\u8fd1）"), 98.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("93.40\u4e0b\u65b9（MA20\u652f\u6491）"), 93.4)
        self.assertEqual(DatabaseManager._parse_sniper_value("108.00-110.00（\u524d\u671f\u9ad8\u70b9\u963b\u529b）"), 110.0)

        # 6. \u65e0\u6548\u8f93\u5165
        self.assertIsNone(DatabaseManager._parse_sniper_value(None))
        self.assertIsNone(DatabaseManager._parse_sniper_value(""))
        self.assertIsNone(DatabaseManager._parse_sniper_value("\u6ca1\u6709\u6570\u5b57"))
        self.assertIsNone(DatabaseManager._parse_sniper_value("MA5\u4f46\u6ca1\u6709\u5143"))

        # 7. \u56de\u5f52：\u62ec\u53f7\u5185\u6280\u672f\u6307\u6807\u6570\u5b57\u4e0d\u5e94\u88ab\u63d0\u53d6
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.52-1.53 (\u56de\u8e29MA5/10\u9644\u8fd1)"), 10.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20\u652f\u6491)"), 20.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.49-1.50(MA60\u9644\u8fd1\u4f01\u7a33)"), 60.0)
        # \u9a8c\u8bc1\u6b63\u786e\u503c\u5728\u533a\u95f4\u5185
        self.assertIn(DatabaseManager._parse_sniper_value("1.52-1.53 (\u56de\u8e29MA5/10\u9644\u8fd1)"), [1.52, 1.53])
        self.assertIn(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20\u652f\u6491)"), [1.55, 1.56])
        self.assertIn(DatabaseManager._parse_sniper_value("1.49-1.50(MA60\u9644\u8fd1\u4f01\u7a33)"), [1.49, 1.50])

    def test_get_chat_sessions_prefix_is_scoped_by_colon_boundary(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("telegram_12345:chat", "user", "first user")
        db.save_conversation_message("telegram_123456:chat", "user", "second user")

        sessions = db.get_chat_sessions(session_prefix="telegram_12345")

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "telegram_12345:chat")

        DatabaseManager.reset_instance()

    def test_get_chat_sessions_can_include_legacy_exact_session_id(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("feishu_u1", "user", "legacy chat")
        db.save_conversation_message("feishu_u1:ask_600519", "user", "ask session")

        sessions = db.get_chat_sessions(
            session_prefix="feishu_u1:",
            extra_session_ids=["feishu_u1"],
        )

        self.assertEqual({item["session_id"] for item in sessions}, {"feishu_u1", "feishu_u1:ask_600519"})

        DatabaseManager.reset_instance()

    def test_conversation_summary_upsert_and_delete_with_session(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("summary-session", "user", "hello")
        db.upsert_conversation_summary(
            "summary-session",
            "first summary",
            covered_message_id=1,
            source_message_count=1,
            estimated_tokens=10,
        )
        db.upsert_conversation_summary(
            "summary-session",
            "updated summary",
            covered_message_id=2,
            source_message_count=2,
            estimated_tokens=12,
        )

        summary = db.get_conversation_summary("summary-session")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["summary"], "updated summary")
        self.assertEqual(summary["covered_message_id"], 2)
        self.assertEqual(summary["source_message_count"], 2)

        deleted = db.delete_conversation_session("summary-session")

        self.assertEqual(deleted, 1)
        self.assertIsNone(db.get_conversation_summary("summary-session"))

        DatabaseManager.reset_instance()

    def test_conversation_message_save_returns_id(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        message_id = db.save_conversation_message("message-id-session", "user", "hello")

        self.assertIsInstance(message_id, int)
        self.assertGreater(message_id, 0)

        DatabaseManager.reset_instance()

    def test_provider_turn_round_trip_preserves_protocol_fields_and_flags(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        user_id = db.save_conversation_message("trace-session", "user", "question")
        assistant_id = db.save_conversation_message("trace-session", "assistant", "final")
        trace_messages = [
            {
                "role": "assistant",
                "content": "checking",
                "reasoning_content": "reasoning",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "echo",
                        "arguments": {"message": "hello"},
                        "provider_specific_fields": {"thought_signature": "sig"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "{\"ok\": true}"},
        ]

        turn_id = db.save_agent_provider_turn(
            session_id="trace-session",
            run_id="run-1",
            provider="deepseek",
            model="deepseek/deepseek-chat",
            anchor_user_message_id=user_id,
            anchor_assistant_message_id=assistant_id,
            messages=trace_messages,
            contains_reasoning=True,
            contains_tool_calls=True,
            contains_thinking_blocks=False,
            must_roundtrip=True,
            estimated_tokens=42,
        )
        rows = db.get_agent_provider_turns("trace-session")

        self.assertIsInstance(turn_id, int)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["messages"], trace_messages)
        self.assertTrue(rows[0]["contains_reasoning"])
        self.assertTrue(rows[0]["contains_tool_calls"])
        self.assertTrue(rows[0]["must_roundtrip"])
        self.assertEqual(rows[0]["estimated_tokens"], 42)

        DatabaseManager.reset_instance()

    def test_provider_turns_do_not_appear_in_visible_or_web_messages_and_delete_with_session(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        user_id = db.save_conversation_message("trace-hidden", "user", "visible question")
        assistant_id = db.save_conversation_message("trace-hidden", "assistant", "visible answer")
        db.save_agent_provider_turn(
            session_id="trace-hidden",
            run_id="run-hidden",
            provider="deepseek",
            model="deepseek/deepseek-chat",
            anchor_user_message_id=user_id,
            anchor_assistant_message_id=assistant_id,
            messages=[{"role": "assistant", "reasoning_content": "SECRET_REASONING", "tool_calls": []}],
            contains_reasoning=True,
            contains_tool_calls=True,
            contains_thinking_blocks=False,
            must_roundtrip=True,
            estimated_tokens=5,
        )

        self.assertEqual(
            [(m["role"], m["content"]) for m in db.get_visible_conversation_messages("trace-hidden")],
            [("user", "visible question"), ("assistant", "visible answer")],
        )
        self.assertEqual(
            [(m["role"], m["content"]) for m in db.get_conversation_history("trace-hidden")],
            [("user", "visible question"), ("assistant", "visible answer")],
        )
        self.assertEqual(
            [(m["role"], m["content"]) for m in db.get_conversation_messages("trace-hidden")],
            [("user", "visible question"), ("assistant", "visible answer")],
        )

        deleted = db.delete_conversation_session("trace-hidden")

        self.assertEqual(deleted, 2)
        self.assertEqual(db.get_agent_provider_turns("trace-hidden"), [])

        DatabaseManager.reset_instance()

    def test_provider_turn_retention_is_bucketed_by_session_provider_model(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        for idx in range(5):
            user_id = db.save_conversation_message("retention", "user", f"q{idx}")
            assistant_id = db.save_conversation_message("retention", "assistant", f"a{idx}")
            db.save_agent_provider_turn(
                session_id="retention",
                run_id=f"run-{idx}",
                provider="deepseek",
                model="deepseek/deepseek-chat",
                anchor_user_message_id=user_id,
                anchor_assistant_message_id=assistant_id,
                messages=[{"role": "assistant", "reasoning_content": f"r{idx}", "tool_calls": [{"id": f"c{idx}", "name": "echo", "arguments": {}}]}],
                contains_reasoning=True,
                contains_tool_calls=True,
                contains_thinking_blocks=False,
                must_roundtrip=True,
                estimated_tokens=idx + 1,
            )
        user_id = db.save_conversation_message("retention", "user", "other")
        assistant_id = db.save_conversation_message("retention", "assistant", "other")
        db.save_agent_provider_turn(
            session_id="retention",
            run_id="run-other",
            provider="anthropic",
            model="anthropic/claude-test",
            anchor_user_message_id=user_id,
            anchor_assistant_message_id=assistant_id,
            messages=[{"role": "assistant", "provider_blocks": [{"type": "thinking"}], "tool_calls": [{"id": "c-other", "name": "echo", "arguments": {}}]}],
            contains_reasoning=False,
            contains_tool_calls=True,
            contains_thinking_blocks=True,
            must_roundtrip=True,
            estimated_tokens=1,
        )

        deepseek_rows = db.get_agent_provider_turns(
            "retention",
            provider="deepseek",
            model="deepseek/deepseek-chat",
        )
        anthropic_rows = db.get_agent_provider_turns(
            "retention",
            provider="anthropic",
            model="anthropic/claude-test",
        )

        self.assertEqual(len(deepseek_rows), 3)
        self.assertEqual([row["run_id"] for row in deepseek_rows], ["run-2", "run-3", "run-4"])
        self.assertEqual(len(anthropic_rows), 1)

        DatabaseManager.reset_instance()

    def test_get_visible_conversation_messages_returns_ordered_visible_content(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("visible-session", "system", "hidden")
        db.save_conversation_message("visible-session", "user", "question")
        db.save_conversation_message("visible-session", "assistant", "answer")

        messages = db.get_visible_conversation_messages("visible-session")

        self.assertEqual(
            [(item["role"], item["content"]) for item in messages],
            [("user", "question"), ("assistant", "answer")],
        )
        self.assertIsInstance(messages[0]["id"], int)

        DatabaseManager.reset_instance()

    def test_get_visible_conversation_messages_limit_returns_ordered_tail(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        for idx in range(25):
            db.save_conversation_message("visible-limit", "user", f"msg-{idx}")

        messages = db.get_visible_conversation_messages("visible-limit", limit=20)

        self.assertEqual(len(messages), 20)
        self.assertEqual(messages[0]["content"], "msg-5")
        self.assertEqual(messages[-1]["content"], "msg-24")

        DatabaseManager.reset_instance()

    def test_file_sqlite_enables_wal_and_busy_timeout(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_pragmas.db")
        original_env = {
            "DATABASE_PATH": os.environ.get("DATABASE_PATH"),
            "SQLITE_BUSY_TIMEOUT_MS": os.environ.get("SQLITE_BUSY_TIMEOUT_MS"),
            "SQLITE_WAL_ENABLED": os.environ.get("SQLITE_WAL_ENABLED"),
        }

        try:
            os.environ["DATABASE_PATH"] = db_path
            os.environ["SQLITE_BUSY_TIMEOUT_MS"] = "1234"
            os.environ["SQLITE_WAL_ENABLED"] = "true"
            Config.reset_instance()
            DatabaseManager.reset_instance()

            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                journal_mode = session.connection().exec_driver_sql("PRAGMA journal_mode").scalar()
                busy_timeout = session.connection().exec_driver_sql("PRAGMA busy_timeout").scalar()

            self.assertEqual(str(journal_mode).lower(), "wal")
            self.assertEqual(int(busy_timeout), 1234)
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            temp_dir.cleanup()

    def test_get_instance_waits_for_cold_start_initialization(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_cold_start.db")
        original_database_path = os.environ.get("DATABASE_PATH")
        create_all_entered = threading.Event()
        competitor_entered = threading.Event()
        release_create_all = threading.Event()
        competitor_done = threading.Event()
        state_lock = threading.Lock()
        init_errors = []
        competitor_errors = []
        instances = []
        query_values = []
        original_create_all = Base.metadata.create_all

        def delayed_create_all(bind, *args, **kwargs):
            create_all_entered.set()
            if not release_create_all.wait(timeout=5):
                raise TimeoutError("Timed out waiting to release create_all")
            return original_create_all(bind, *args, **kwargs)

        def initialize_manager() -> None:
            try:
                db = DatabaseManager.get_instance()
                with state_lock:
                    instances.append(db)
            except Exception as exc:
                with state_lock:
                    init_errors.append(exc)

        def use_manager() -> None:
            try:
                competitor_entered.set()
                db = DatabaseManager.get_instance()
                session = db.get_session()
                try:
                    value = session.connection().exec_driver_sql("SELECT 1").scalar()
                finally:
                    session.close()
                with state_lock:
                    instances.append(db)
                    query_values.append(value)
            except Exception as exc:
                with state_lock:
                    competitor_errors.append(exc)
            finally:
                competitor_done.set()

        try:
            os.environ["DATABASE_PATH"] = db_path
            Config.reset_instance()
            with patch.object(Base.metadata, "create_all", side_effect=delayed_create_all):
                init_thread = threading.Thread(target=initialize_manager)
                competitor_thread = threading.Thread(target=use_manager)

                init_thread.start()
                self.assertTrue(create_all_entered.wait(timeout=5))

                competitor_thread.start()
                self.assertTrue(competitor_entered.wait(timeout=5))
                self.assertFalse(
                    competitor_done.wait(timeout=0.2),
                    "DatabaseManager.get_instance() returned before initialization completed",
                )

                release_create_all.set()
                init_thread.join(timeout=5)
                competitor_thread.join(timeout=5)

                self.assertFalse(init_thread.is_alive())
                self.assertFalse(competitor_thread.is_alive())

            self.assertEqual(init_errors, [])
            self.assertEqual(competitor_errors, [])
            self.assertEqual(query_values, [1])
            self.assertEqual(len({id(instance) for instance in instances}), 1)
        finally:
            release_create_all.set()
            DatabaseManager.reset_instance()
            Config.reset_instance()
            if original_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = original_database_path
            temp_dir.cleanup()

    def test_direct_construction_serializes_before_get_instance(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        direct_db_path = os.path.join(temp_dir.name, "direct.db")
        env_db_path = os.path.join(temp_dir.name, "env.db")
        direct_db_url = f"sqlite:///{direct_db_path}"
        original_database_path = os.environ.get("DATABASE_PATH")
        direct_init_entered = threading.Event()
        competitor_entered = threading.Event()
        allow_direct_init = threading.Event()
        competitor_done = threading.Event()
        state_lock = threading.Lock()
        errors = []
        instances = []
        query_values = []
        original_init = DatabaseManager.__init__

        def delayed_direct_init(self, db_url=None):
            if db_url == direct_db_url:
                direct_init_entered.set()
                if not competitor_entered.wait(timeout=5):
                    raise TimeoutError("Timed out waiting for competitor")
                if not allow_direct_init.wait(timeout=5):
                    raise TimeoutError("Timed out waiting to initialize direct instance")
            return original_init(self, db_url=db_url)

        def construct_directly() -> None:
            try:
                db = DatabaseManager(db_url=direct_db_url)
                with state_lock:
                    instances.append(db)
            except Exception as exc:
                with state_lock:
                    errors.append(exc)

        def use_get_instance() -> None:
            try:
                competitor_entered.set()
                db = DatabaseManager.get_instance()
                session = db.get_session()
                try:
                    value = session.connection().exec_driver_sql("SELECT 1").scalar()
                finally:
                    session.close()
                with state_lock:
                    instances.append(db)
                    query_values.append(value)
            except Exception as exc:
                with state_lock:
                    errors.append(exc)
            finally:
                competitor_done.set()

        try:
            os.environ["DATABASE_PATH"] = env_db_path
            Config.reset_instance()
            with patch.object(DatabaseManager, "__init__", new=delayed_direct_init):
                direct_thread = threading.Thread(target=construct_directly)
                competitor_thread = threading.Thread(target=use_get_instance)

                direct_thread.start()
                self.assertTrue(direct_init_entered.wait(timeout=5))

                competitor_thread.start()
                self.assertTrue(competitor_entered.wait(timeout=5))
                self.assertFalse(
                    competitor_done.wait(timeout=0.2),
                    "get_instance() should not initialize over an in-flight direct construction",
                )

                allow_direct_init.set()
                direct_thread.join(timeout=5)
                competitor_thread.join(timeout=5)

                self.assertFalse(direct_thread.is_alive())
                self.assertFalse(competitor_thread.is_alive())

            self.assertEqual(errors, [])
            self.assertEqual(query_values, [1])
            self.assertEqual(len({id(instance) for instance in instances}), 1)
            self.assertEqual(DatabaseManager._instance._db_url, direct_db_url)
        finally:
            allow_direct_init.set()
            DatabaseManager.reset_instance()
            Config.reset_instance()
            if original_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = original_database_path
            temp_dir.cleanup()

    def test_init_cleanup_preserves_original_initialization_error(self):
        DatabaseManager.reset_instance()
        original_error = RuntimeError("create all failed")
        cleanup_error = RuntimeError("dispose failed")

        def create_engine_with_failing_dispose(*args, **kwargs):
            engine = sqlalchemy_create_engine(*args, **kwargs)

            def failing_dispose() -> None:
                raise cleanup_error

            engine.dispose = failing_dispose
            return engine

        try:
            with patch("src.storage.create_engine", side_effect=create_engine_with_failing_dispose):
                with patch.object(Base.metadata, "create_all", side_effect=original_error):
                    with self.assertRaisesRegex(RuntimeError, "create all failed") as ctx:
                        DatabaseManager.get_instance()

            self.assertIs(ctx.exception, original_error)
            self.assertIsNone(DatabaseManager._instance)
        finally:
            DatabaseManager.reset_instance()

    def test_sqlite_write_transactions_begin_immediate(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        session = db.get_session()
        connection = session.connection()

        try:
            with patch.object(db, "get_session", return_value=session):
                with patch.object(connection, "exec_driver_sql", wraps=connection.exec_driver_sql) as mock_exec:
                    result = db._run_write_transaction("unit-test", lambda current_session: 7)

            self.assertEqual(result, 7)
            self.assertTrue(
                any(call.args == ("BEGIN IMMEDIATE",) for call in mock_exec.call_args_list)
            )
        finally:
            DatabaseManager.reset_instance()

    def test_save_daily_data_sqlite_concurrent_same_code_date_counts_only_new_rows(self):
        DatabaseManager.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_daily_concurrency.db")
        db = DatabaseManager(db_url=f"sqlite:///{db_path}")

        results = []
        results_lock = threading.Lock()
        start_barrier = threading.Barrier(2)

        def worker() -> None:
            start_barrier.wait()
            count = db.save_daily_data(
                pd.DataFrame(
                    [
                        {
                            'date': date(2026, 4, 1),
                            'open': 10,
                            'high': 11,
                            'low': 9,
                            'close': 10.5,
                            'volume': 100,
                            'amount': 1050,
                            'pct_chg': 1.2,
                            'ma5': 10.1,
                            'ma10': 10.2,
                            'ma20': 10.3,
                            'volume_ratio': 1.0,
                        }
                    ]
                ),
                code='600519',
                data_source='test',
            )
            with results_lock:
                results.append(count)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        try:
            self.assertCountEqual(results, [1, 0])

            with db.get_session() as session:
                total = session.execute(
                    select(func.count()).select_from(StockDaily).where(
                        and_(
                            StockDaily.code == '600519',
                            StockDaily.date == date(2026, 4, 1),
                        )
                    )
                ).scalar()

            self.assertEqual(total, 1)
        finally:
            temp_dir.cleanup()
            DatabaseManager.reset_instance()

if __name__ == '__main__':
    unittest.main()
