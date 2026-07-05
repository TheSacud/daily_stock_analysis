# -*- coding: utf-8 -*-
"""Regression tests for optional pipeline service degradation logs."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.pipeline import StockAnalysisPipeline


def _make_config() -> SimpleNamespace:
    return SimpleNamespace(
        max_workers=2,
        save_context_snapshot=False,
        bocha_api_keys=[],
        tavily_api_keys=[],
        brave_api_keys=[],
        serpapi_keys=[],
        minimax_api_keys=[],
        searxng_base_urls=[],
        searxng_public_instances_enabled=False,
        news_max_age_days=7,
        news_strategy_profile="short",
        enable_realtime_quote=False,
        realtime_source_priority=[],
        enable_chip_distribution=False,
        social_sentiment_api_key="",
        social_sentiment_api_url="https://example.invalid/social",
    )


def _build_pipeline(config: SimpleNamespace) -> StockAnalysisPipeline:
    with patch("src.core.pipeline.get_db", return_value=MagicMock()), \
         patch("src.core.pipeline.DataFetcherManager", return_value=MagicMock()), \
         patch("src.core.pipeline.StockTrendAnalyzer", return_value=MagicMock()), \
         patch("src.core.pipeline.GeminiAnalyzer", return_value=MagicMock()), \
         patch("src.core.pipeline.NotificationService", return_value=MagicMock()):
        return StockAnalysisPipeline(config=config)


def test_search_service_init_failure_logs_traceback_and_failure_state(caplog):
    config = _make_config()
    social_service = MagicMock()
    social_service.is_available = False

    with patch("src.core.pipeline.SearchService", side_effect=RuntimeError("search init boom")), \
         patch("src.core.pipeline.SocialSentimentService", return_value=social_service), \
         caplog.at_level(logging.WARNING, logger="src.core.pipeline"):
        pipeline = _build_pipeline(config)

    assert pipeline.search_service is None

    init_failure_records = [
        record for record in caplog.records if "\u641c\u7d22\u670d\u52a1\u521d\u59cb\u5316\u5931\u8d25，\u5c06\u4ee5\u65e0\u641c\u7d22\u6a21\u5f0f\u8fd0\u884c" in record.message
    ]
    assert len(init_failure_records) == 1
    assert init_failure_records[0].exc_info is not None
    assert "\u641c\u7d22\u670d\u52a1\u672a\u542f\u7528（\u521d\u59cb\u5316\u5931\u8d25\u6216\u4f9d\u8d56\u7f3a\u5931）" in caplog.text
    assert "\u641c\u7d22\u670d\u52a1\u672a\u542f\u7528（\u672a\u914d\u7f6e\u641c\u7d22\u80fd\u529b）" not in caplog.text


def test_social_sentiment_init_failure_logs_traceback(caplog):
    config = _make_config()
    search_service = MagicMock()
    search_service.is_available = False

    with patch("src.core.pipeline.SearchService", return_value=search_service), \
         patch("src.core.pipeline.SocialSentimentService", side_effect=RuntimeError("social init boom")), \
         caplog.at_level(logging.WARNING, logger="src.core.pipeline"):
        pipeline = _build_pipeline(config)

    assert pipeline.social_sentiment_service is None

    init_failure_records = [
        record for record in caplog.records if "\u793e\u4ea4\u8206\u60c5\u670d\u52a1\u521d\u59cb\u5316\u5931\u8d25，\u5c06\u8df3\u8fc7\u8206\u60c5\u5206\u6790" in record.message
    ]
    assert len(init_failure_records) == 1
    assert init_failure_records[0].exc_info is not None


def test_emit_progress_logs_context_when_callback_fails(caplog):
    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.query_id = "query-123"

    def _fail_callback(progress, message):
        raise RuntimeError(f"cannot send {progress}:{message}")

    pipeline.progress_callback = _fail_callback

    with caplog.at_level(logging.WARNING, logger="src.core.pipeline"):
        pipeline._emit_progress(55, "fetching news")

    records = [record for record in caplog.records if "progress callback failed" in record.message]
    assert len(records) == 1
    record = records[0]
    assert "progress=55" in record.message
    assert "message='fetching news'" in record.message
    assert "query_id=query-123" in record.message
    assert record.progress == 55
    assert record.progress_message == "fetching news"
    assert record.query_id == "query-123"
