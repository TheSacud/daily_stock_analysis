# -*- coding: utf-8 -*-
"""
Unit tests for strict news freshness filtering and strategy window logic (Issue #697).
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mock newspaper before search_service import (optional dependency)
if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.search_service import SearchResponse, SearchResult, SearchService
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    current_diagnostic_snapshot,
    reset_run_diagnostic_context,
)


def _result(
    title: str,
    published_date: str | None,
    *,
    snippet: str = "snippet",
    url: str | None = None,
    source: str = "example.com",
) -> SearchResult:
    return SearchResult(
        title=title,
        snippet=snippet,
        url=url or f"https://example.com/{title}",
        source=source,
        published_date=published_date,
    )


def _response(results) -> SearchResponse:
    return SearchResponse(
        query="test",
        results=results,
        provider="Mock",
        success=True,
    )


class SearchNewsFreshnessTestCase(unittest.TestCase):
    """Tests for strategy window and strict published_date filtering."""

    def _create_service_with_mock_provider(
        self,
        *,
        news_max_age_days: int = 3,
        news_strategy_profile: str = "short",
        response: SearchResponse | None = None,
    ):
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=news_max_age_days,
            news_strategy_profile=news_strategy_profile,
        )
        mock_search = MagicMock(
            return_value=response
            or _response([_result("default", datetime.now().date().isoformat())])
        )
        service._providers[0].search = mock_search
        return service, mock_search

    def test_effective_window_uses_profile_and_news_max_age(self) -> None:
        """window = min(profile_days, NEWS_MAX_AGE_DAYS)."""
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="medium",  # 7
        )
        service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=5)
        kwargs = mock_search.call_args[1]
        self.assertEqual(kwargs["days"], 3)

    def test_invalid_profile_falls_back_to_short(self) -> None:
        """Invalid profile should fallback to short (3 days)."""
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=30,
            news_strategy_profile="invalid_profile",
        )
        service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=5)
        kwargs = mock_search.call_args[1]
        self.assertEqual(kwargs["days"], 3)

    def test_search_stock_news_strict_filters(self) -> None:
        """Drop old/unknown/future+2, keep future+1 and within-window dates."""
        today = datetime.now().date()
        fresh = today.isoformat()
        old = (today - timedelta(days=30)).isoformat()
        future_1 = (today + timedelta(days=1)).isoformat()
        future_2 = (today + timedelta(days=2)).isoformat()

        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=7,
            news_strategy_profile="medium",
            response=_response(
                [
                    _result("old", old),
                    _result("unknown", None),
                    _result("future_2", future_2),
                    _result("future_1", future_1),
                    _result("fresh", fresh),
                ]
            ),
        )

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=5)
        titles = [r.title for r in resp.results]
        self.assertEqual(titles, ["future_1", "fresh"])
        for item in resp.results:
            self.assertRegex(item.published_date or "", r"^\d{4}-\d{2}-\d{2}$")

    def test_search_stock_news_overfetch_before_filter(self) -> None:
        """Provider request size should be increased before filtering."""
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=4)
        args, kwargs = mock_search.call_args
        requested = kwargs.get("max_results")
        if requested is None:
            requested = args[1]
        self.assertEqual(requested, 8)

    def test_search_stock_news_try_next_provider_when_filtered_empty(self) -> None:
        """If provider-A passes API call but all results are filtered, continue to provider-B."""
        today = datetime.now().date()
        old = (today - timedelta(days=90)).isoformat()
        fresh = today.isoformat()

        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search=MagicMock(return_value=_response([_result("too_old", old)])),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search=MagicMock(return_value=_response([_result("fresh", fresh)])),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=3)
        self.assertEqual([r.title for r in resp.results], ["fresh"])
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_search_stock_news_records_provider_diagnostics_for_fallback(self) -> None:
        """News search provider attempts should appear in run-flow diagnostics."""
        today = datetime.now().date()
        old = (today - timedelta(days=90)).isoformat()
        fresh = today.isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        tavily = SimpleNamespace(
            is_available=True,
            name="Tavily",
            search=MagicMock(return_value=_response([_result("too_old", old)])),
        )
        searxng = SimpleNamespace(
            is_available=True,
            name="SearXNG",
            search=MagicMock(return_value=_response([_result("\u8d35\u5dde\u8305\u53f0 600519 \u6700\u65b0\u516c\u544a", fresh)])),
        )
        service._providers = [tavily, searxng]

        token = activate_run_diagnostic_context(
            trace_id="trace-news",
            task_id="task-news",
            query_id="query-news",
            stock_code="600519",
            trigger_source="api",
        )
        try:
            response = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=3)
            diagnostics = current_diagnostic_snapshot()
        finally:
            reset_run_diagnostic_context(token)

        self.assertEqual([item.title for item in response.results], ["\u8d35\u5dde\u8305\u53f0 600519 \u6700\u65b0\u516c\u544a"])
        provider_runs = diagnostics["provider_runs"]
        self.assertEqual([run["data_type"] for run in provider_runs], ["news_search", "news_search"])
        self.assertEqual([run["provider"] for run in provider_runs], ["Tavily", "SearXNG"])
        self.assertFalse(provider_runs[0]["success"])
        self.assertTrue(provider_runs[1]["success"])
        self.assertEqual(provider_runs[1]["record_count"], 1)

    def test_search_stock_news_tries_next_provider_when_chinese_context_is_english_only(self) -> None:
        """Chinese-preferred queries should not stop on English-only provider results."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search=MagicMock(
                return_value=_response(
                    [
                        _result("English headline", fresh),
                        _result("Another English story", fresh),
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search=MagicMock(return_value=_response([_result("\u4e2d\u6587\u8d44\u8baf", fresh)])),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=3)
        self.assertEqual([r.title for r in resp.results], ["\u4e2d\u6587\u8d44\u8baf"])
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_search_stock_news_prioritizes_chinese_items_within_mixed_results(self) -> None:
        """Chinese items should be ordered ahead of English items in mixed batches."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        mixed_provider = SimpleNamespace(
            is_available=True,
            name="Mixed",
            search=MagicMock(
                return_value=_response(
                    [
                        _result("English headline", fresh),
                        _result("\u4e2d\u6587\u5feb\u8baf", fresh),
                        _result("Second English headline", fresh),
                    ]
                )
            ),
        )
        service._providers = [mixed_provider]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=3)
        self.assertEqual(
            [r.title for r in resp.results],
            ["\u4e2d\u6587\u5feb\u8baf", "English headline", "Second English headline"],
        )

    def test_search_stock_news_prioritizes_chinese_before_truncating_results(self) -> None:
        """Chinese candidates beyond the first raw slot should still win after reprioritization."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search=MagicMock(
                return_value=_response(
                    [
                        _result("English headline", fresh),
                        _result("\u4e2d\u6587\u5feb\u8baf", fresh),
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search=MagicMock(return_value=_response([_result("\u540e\u7eed\u4e2d\u6587\u8d44\u8baf", fresh)])),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=1)
        self.assertEqual([r.title for r in resp.results], ["\u4e2d\u6587\u5feb\u8baf"])
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_search_stock_news_prefers_chinese_direct_hit_before_score_truncation(self) -> None:
        """Chinese direct hits should outrank higher-scored English direct hits before limiting."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        provider = SimpleNamespace(
            is_available=True,
            name="MixedDirect",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "Kweichow Moutai 600519 announces buyback",
                            fresh,
                            snippet="The company reported an updated share repurchase plan.",
                        ),
                        _result(
                            "\u8d35\u5dde\u8305\u53f0 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                            fresh,
                            snippet="\u516c\u53f8\u62ab\u9732\u56de\u8d2d\u65b9\u6848。",
                        ),
                    ]
                )
            ),
        )
        service._providers = [provider]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=1)

        self.assertEqual([r.title for r in resp.results], ["\u8d35\u5dde\u8305\u53f0 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        provider.search.assert_called_once()

    def test_a_share_chinese_sector_provider_beats_higher_scored_english_sector(self) -> None:
        """When no direct hit exists, Chinese-preferred flows should compare language before score."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="EnglishSector",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "Baijiu industry quarterly results improve",
                            fresh,
                            snippet="Sector peers report better market share.",
                            source="sec.gov",
                        )
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="ChineseSector",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "\u767d\u9152\u677f\u5757\u8d44\u91d1\u56de\u6696",
                            fresh,
                            snippet="\u6d88\u8d39\u884c\u4e1a\u53cd\u5f39。",
                        )
                    ]
                )
            ),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=1)

        self.assertEqual([r.title for r in resp.results], ["\u767d\u9152\u677f\u5757\u8d44\u91d1\u56de\u6696"])
        self.assertEqual(resp.results[0].relevance_category, "sector_related_news")
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_search_stock_news_keeps_english_provider_order_for_us_stock(self) -> None:
        """English stock searches should keep the first successful provider result."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search=MagicMock(return_value=_response([_result("Apple earnings beat", fresh)])),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search=MagicMock(return_value=_response([_result("\u82f9\u679c\u8d44\u8baf", fresh)])),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("AAPL", "Apple", max_results=3)
        self.assertEqual([r.title for r in resp.results], ["Apple earnings beat"])
        p1.search.assert_called_once()
        p2.search.assert_not_called()

    def test_a_share_direct_company_news_beats_sector_provider_fallback(self) -> None:
        """A-share direct company hits should beat generic sector news from earlier providers."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "\u767d\u9152\u884c\u4e1a\u666f\u6c14\u5ea6\u56de\u6696 \u591a\u53ea\u9f99\u5934\u4e0a\u6da8",
                            fresh,
                            snippet="\u6d88\u8d39\u677f\u5757\u83b7\u5f97\u8d44\u91d1\u5173\u6ce8。",
                        )
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search=MagicMock(
                return_value=_response(
                    [
                        _result("\u6caa\u6307\u9707\u8361\u6536\u6da8，\u5e02\u573a\u60c5\u7eea\u56de\u6696", fresh),
                        _result(
                            "\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                            fresh,
                            snippet="\u8d35\u5dde\u8305\u53f0\u62ab\u9732\u516c\u53f8\u516c\u544a，\u8463\u4e8b\u4f1a\u5ba1\u8bae\u901a\u8fc7\u56de\u8d2d\u65b9\u6848。",
                            source="cninfo",
                        ),
                    ]
                )
            ),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=2)

        self.assertEqual(resp.results[0].title, "\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        self.assertIn("\u80a1\u7968\u4ee3\u7801", "；".join(resp.results[0].relevance_reasons or []))
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_search_stock_news_filters_low_quality_and_zero_relevance_fillers(self) -> None:
        """Download/listing pages and zero-relevance fillers should not enter stock news context."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        provider = SimpleNamespace(
            is_available=True,
            name="MixedNoise",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "\u817e\u8baf\u63a7\u80a1 00700 \u6781\u901f\u7248\u5b89\u88c5\u5305\u4e0b\u8f7d",
                            fresh,
                            snippet="\u5f53\u524d\u7248\u672c 686.38MB，84%\u597d\u8bc4，\u9002\u5408\u4e0b\u8f7d\u5b89\u88c5\u5230\u624b\u673a。",
                            url="https://download.example.invalid/apps/douyang",
                            source="download.example.invalid",
                        ),
                        _result(
                            "1000+ \u5b9c\u660c\u5c0f\u59d0\u4e0a\u95e8\u7279\u6b8a\u670d\u52a1",
                            fresh,
                            snippet="\u5c0f\u59d0\u9884\u7ea6 yue2345，\u540c\u57ce\u7ea6\u70ae、\u4fdd\u5065\u6309\u6469、\u63a8\u6cb9\u5957\u9910。",
                            url="https://spam.example.invalid/local/yue2345",
                            source="spam.example.invalid",
                        ),
                        _result(
                            "\u7f8e\u56fd\u8c03\u6574\u5173\u7a0e，\u793e\u7fa4\u8ba8\u8bba\u5347\u6e29",
                            fresh,
                            snippet="\u793e\u7fa4\u7528\u6237\u5206\u4eab\u751f\u6d3b\u8bdd\u9898，\u4e0e\u76ee\u6807\u80a1\u7968\u6ca1\u6709\u76f4\u63a5\u5173\u7cfb。",
                            url="https://news.example.invalid/lifestyle/123",
                            source="news.example.invalid",
                        ),
                        _result(
                            "\u817e\u8baf\u63a7\u80a1 00700 \u65e9\u76d8\u8d70\u5f3a",
                            fresh,
                            snippet="\u817e\u8baf\u63a7\u80a1\u6210\u4ea4\u6d3b\u8dc3，\u6e2f\u80a1\u79d1\u6280\u677f\u5757\u53cd\u5f39。",
                            url="https://finance.example.invalid/00700",
                            source="finance.example.invalid",
                        ),
                    ]
                )
            ),
        )
        service._providers = [provider]

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=3)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u65e9\u76d8\u8d70\u5f3a"])
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_download_like_news_without_size_or_url_hints_is_filtered(self) -> None:
        """Content-only Android/download signals should still trigger low-quality filtering."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u5b98\u65b9\u7248\u5ba2\u6237\u7aef\u5b89\u5353\u7248\u4e0b\u8f7d",
                        fresh,
                        snippet="\u70b9\u6b64\u83b7\u53d6\u6700\u65b0\u7248\u5b89\u5353\u7248\u5ba2\u6237\u7aef，\u652f\u6301\u4e00\u952e\u4e0b\u8f7d\u5b89\u88c5\u5305。",
                        url="https://finance.example.invalid/tencent/stock/00700",
                        source="finance.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        source="hkexnews",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=2)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])

    def test_package_security_news_does_not_trigger_download_filter(self) -> None:
        """Bare package wording in product/security news should not look like a download page."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u91d1\u5c71\u529e\u516c 688111 WPS \u5b89\u88c5\u5305\u88ab\u66dd\u6f0f\u6d1e",
                        fresh,
                        snippet="\u516c\u53f8\u56de\u5e94 WPS \u5b89\u88c5\u5305\u5b89\u5168\u6f0f\u6d1e\u5e76\u53d1\u5e03\u4fee\u590d\u8ba1\u5212。",
                        url="https://finance.example.invalid/news/688111-security",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("688111", "\u91d1\u5c71\u529e\u516c", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u91d1\u5c71\u529e\u516c 688111 WPS \u5b89\u88c5\u5305\u88ab\u66dd\u6f0f\u6d1e"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_rich_media_client_phrase_in_ticker_news_is_not_filtered(self) -> None:
        """Client wording used in normal headline styles should not be treated as download spam."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u8bc1\u5238\u65f6\u62a5\u5ba2\u6237\u7aef\u8baf，\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u8d35\u8305\u62ab\u9732\u80a1\u7968\u56de\u8d2d\u516c\u544a。",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u8bc1\u5238\u65f6\u62a5\u5ba2\u6237\u7aef\u8baf，\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"],
        )

    def test_outer_market_phrase_is_not_filtered_as_adult_spam(self) -> None:
        """`\u5916\u56f4\u5e02\u573a` market-context headlines should not be treated as adult spam."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u5916\u56f4\u5e02\u573a\u8d70\u5f31\u62d6\u7d2f\u79d1\u6280\u80a1",
                        fresh,
                        snippet="\u5916\u56f4\u5e02\u573a\u60c5\u7eea\u8d70\u5f31，\u5e26\u52a8\u79d1\u6280\u80a1\u9636\u6bb5\u6027\u56de\u64a4。",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u5916\u56f4\u5e02\u573a\u8d70\u5f31\u62d6\u7d2f\u79d1\u6280\u80a1"],
        )

    def test_url_only_app_route_does_not_drop_direct_stock_news(self) -> None:
        """App-style news hosts or paths need content evidence before admission drops."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a，\u6210\u4ea4\u7ef4\u6301\u6d3b\u8dc3。",
                        url="https://app.finance.example.invalid/apps/markets/00700",
                        source="app.finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_apple_rating_phrase_does_not_trigger_app_download_filter(self) -> None:
        """Apple should not satisfy the bare app/download term in admission filtering."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "Apple gets 5 stars from analysts after earnings",
                        fresh,
                        snippet="AAPL shares rose after Apple revenue guidance improved.",
                        url="https://finance.example.invalid/aapl-analyst-rating",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("AAPL", "Apple", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["Apple gets 5 stars from analysts after earnings"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_app_ticker_rating_phrase_does_not_trigger_app_download_filter(self) -> None:
        """Ticker APP and analyst ratings should not look like an app listing."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "APP stock jumps after advertising platform guidance",
                        fresh,
                        snippet=(
                            "APP shares rose after analysts gave the company "
                            "5 stars for revenue momentum."
                        ),
                        url="https://finance.example.invalid/app-stock-rating",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("APP", "AppLovin", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["APP stock jumps after advertising platform guidance"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_product_game_rating_does_not_trigger_app_download_filter(self) -> None:
        """Normal game/product ratings need download/install evidence before filtering."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u65b0\u6e38\u4e0a\u7ebf\u83b7\u73a9\u5bb6\u8bc4\u5206 9.0",
                        fresh,
                        snippet="\u817e\u8baf\u6e38\u620f\u65b0\u54c1\u4e0a\u7ebf\u9996\u5468\u8868\u73b0\u5f3a\u52b2，\u73a9\u5bb6\u8bc4\u5206 9.0。",
                        url="https://finance.example.invalid/app/news/00700-game-rating",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u817e\u8baf\u63a7\u80a1 00700 \u65b0\u6e38\u4e0a\u7ebf\u83b7\u73a9\u5bb6\u8bc4\u5206 9.0"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_app_download_growth_metric_does_not_trigger_download_filter(self) -> None:
        """App download/install growth metrics are business news, not app-store pages."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u589e\u957f",
                        fresh,
                        snippet="Temu \u5e94\u7528\u5b89\u88c5\u91cf\u540c\u6bd4\u63d0\u5347，\u5e26\u52a8\u8de8\u5883\u4e1a\u52a1\u6536\u5165\u6539\u5584。",
                        url="https://finance.example.invalid/app/news/pdd-temu-downloads",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("PDD", "PDD Holdings", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u589e\u957f"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_neutral_app_download_scale_metric_does_not_trigger_download_filter(self) -> None:
        """Neutral app download scale metrics are operating news, not download pages."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u8fbe1\u4ebf",
                        fresh,
                        snippet="Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u8fbe1\u4ebf，\u5e02\u573a\u5173\u6ce8\u8de8\u5883\u4e1a\u52a1\u83b7\u5ba2\u6548\u7387。",
                        url="https://finance.example.invalid/app/news/pdd-temu-downloads",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("PDD", "PDD Holdings", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u8fbe1\u4ebf"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_app_download_and_install_metric_phrases_do_not_trigger_download_filter(self) -> None:
        """Application download/install metric phrases should remain business news."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u540c\u6bd4\u589e\u957f",
                        fresh,
                        snippet="Temu \u5e94\u7528\u5b89\u88c5\u540c\u6bd4\u63d0\u5347，\u63a8\u52a8\u8de8\u5883\u4e1a\u52a1\u589e\u957f。",
                        url="https://finance.example.invalid/app/news/pdd-temu-install-growth",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("PDD", "PDD Holdings", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u540c\u6bd4\u589e\u957f"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_neutral_english_app_install_metric_does_not_trigger_download_filter(self) -> None:
        """Neutral English app-install scale metrics should remain business news."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "PDD Temu mobile app install base reaches 100M",
                        fresh,
                        snippet="PDD shares rose as Temu mobile app install base reaches 100M.",
                        url="https://finance.example.invalid/app/news/pdd-temu-installs",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("PDD", "PDD Holdings", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["PDD Temu mobile app install base reaches 100M"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_app_download_decline_metrics_do_not_trigger_download_filter(self) -> None:
        """Negative app download/install metrics are also business news."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u4e0b\u964d",
                        fresh,
                        snippet="Temu \u5e94\u7528\u5b89\u88c5\u91cf\u4e0b\u6ed1，\u5e02\u573a\u5173\u6ce8\u83b7\u5ba2\u6548\u7387。",
                        url="https://finance.example.invalid/app/news/pdd-downloads-fall",
                        source="finance.example.invalid",
                    ),
                    _result(
                        "PDD app installs fell after campaign pullback",
                        fresh,
                        snippet="PDD shares moved as app installs fell in May.",
                        url="https://finance.example.invalid/apps/pdd-installs",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("PDD", "PDD Holdings", max_results=2)

        self.assertEqual(
            [item.title for item in resp.results],
            [
                "\u62fc\u591a\u591a PDD Temu \u5e94\u7528\u4e0b\u8f7d\u91cf\u4e0b\u964d",
                "PDD app installs fell after campaign pullback",
            ],
        )
        self.assertTrue(all(item.relevance_category == "direct_company_news" for item in resp.results))

    def test_url_backed_app_rating_listing_is_filtered(self) -> None:
        """App-store URL plus version/rating metrics should be treated as listing noise."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 app store rating",
                        fresh,
                        snippet="4.8 stars, 10M downloads, version 12.8 for mobile app users.",
                        url="https://apps.example.invalid/tencent/00700",
                        source="apps.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/00700-buyback",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])

    def test_app_listing_metric_with_version_rating_still_filtered(self) -> None:
        """Business metric wording should not rescue obvious app listing pages."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u4e0b\u8f7d\u91cf\u7a81\u78341000\u4e07",
                        fresh,
                        snippet="\u5e94\u7528\u7248\u672c 12.8，\u8bc4\u5206 4.9，\u5b89\u88c5\u5305 256MB，\u4e0b\u8f7d\u91cf\u7a81\u78341000\u4e07。",
                        url="https://apps.example.invalid/tencent/00700/download",
                        source="apps.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u4e1a\u7ee9\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u5b63\u5ea6\u4e1a\u7ee9，\u6536\u5165\u4e0e\u5229\u6da6\u4fdd\u6301\u589e\u957f。",
                        url="https://finance.example.invalid/news/00700-earnings",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u4e1a\u7ee9\u516c\u544a"])

    def test_finance_client_boilerplate_does_not_trigger_download_filter(self) -> None:
        """Finance media boilerplate such as \u5ba2\u6237\u7aef\u8baf should not look like an app page."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u8bc1\u5238\u65f6\u62a5\u5ba2\u6237\u7aef\u8baf，\u8d35\u5dde\u8305\u53f0\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/600519-buyback",
                        source="\u8bc1\u5238\u65f6\u62a5",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_market_peripheral_phrase_does_not_trigger_adult_spam_filter(self) -> None:
        """Finance usage of \u5916\u56f4\u5e02\u573a should not be treated as adult-service spam."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d7\u5916\u56f4\u5e02\u573a\u8d70\u5f31\u62d6\u7d2f",
                        fresh,
                        snippet="\u5916\u56f4\u5e02\u573a\u8d70\u5f31\u62d6\u7d2f\u6e2f\u80a1\u79d1\u6280\u80a1，\u817e\u8baf\u63a7\u80a1\u6210\u4ea4\u6d3b\u8dc3。",
                        url="https://finance.example.invalid/markets/00700",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u817e\u8baf\u63a7\u80a1 00700 \u53d7\u5916\u56f4\u5e02\u573a\u8d70\u5f31\u62d6\u7d2f"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_business_full_service_phrase_does_not_trigger_adult_spam_filter(self) -> None:
        """Business-safe \u5168\u5957\u670d\u52a1 wording should require adult-service context."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u534e\u80fd\u56fd\u9645 600011 \u63a8\u51fa\u5168\u5957\u670d\u52a1\u89e3\u51b3\u65b9\u6848",
                        fresh,
                        snippet="\u516c\u53f8\u9762\u5411\u80fd\u6e90\u5ba2\u6237\u63d0\u4f9b\u5168\u5957\u670d\u52a1\u89e3\u51b3\u65b9\u6848，\u63d0\u5347\u8fd0\u7ef4\u6548\u7387。",
                        url="https://finance.example.invalid/news/600011-service-solution",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("600011", "\u534e\u80fd\u56fd\u9645", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u534e\u80fd\u56fd\u9645 600011 \u63a8\u51fa\u5168\u5957\u670d\u52a1\u89e3\u51b3\u65b9\u6848"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_mobile_app_wording_does_not_count_as_adult_contact_signal(self) -> None:
        """Mobile-app wording should not look like a phone/contact handle."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u7f8e\u7684\u96c6\u56e2 000333 mobile-app \u6309\u6469\u6905\u4e1a\u52a1\u589e\u957f",
                        fresh,
                        snippet="\u516c\u53f8 mobile app \u6e20\u9053\u5e26\u52a8\u6309\u6469\u6905\u548c\u4fdd\u5065\u4e1a\u52a1\u9500\u552e\u589e\u957f。",
                        url="https://finance.example.invalid/mobile-app/000333-health",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("000333", "\u7f8e\u7684\u96c6\u56e2", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u7f8e\u7684\u96c6\u56e2 000333 mobile-app \u6309\u6469\u6905\u4e1a\u52a1\u589e\u957f"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_local_service_category_cluster_does_not_trigger_adult_spam_filter(self) -> None:
        """Benign local-service categories need adult-specific anchors before filtering."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u7f8e\u56e2 03690 \u63a8\u51fa\u6309\u6469\u8db3\u6d74\u4f1a\u6240\u9884\u7ea6\u5957\u9910\u670d\u52a1",
                        fresh,
                        snippet="\u7f8e\u56e2\u62d3\u5c55\u672c\u5730\u751f\u6d3b\u670d\u52a1，\u65b0\u589e\u6309\u6469\u8db3\u6d74\u4f1a\u6240\u9884\u7ea6\u5957\u9910。",
                        url="https://finance.example.invalid/news/03690-local-service",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("03690.HK", "\u7f8e\u56e2", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u7f8e\u56e2 03690 \u63a8\u51fa\u6309\u6469\u8db3\u6d74\u4f1a\u6240\u9884\u7ea6\u5957\u9910\u670d\u52a1"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_adult_term_platform_remediation_news_is_not_filtered(self) -> None:
        """Platform enforcement/remediation articles are risk news, not service ads."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u7f8e\u56e2 03690 \u4e0b\u67b6\u6d89\u8272\u60c5\u6309\u6469\u4f1a\u6240\u5546\u5bb6",
                        fresh,
                        snippet="\u7f8e\u56e2\u5f00\u5c55\u5e73\u53f0\u6cbb\u7406，\u6e05\u7406\u6d89\u8272\u60c5\u4f4e\u4fd7\u5185\u5bb9\u5546\u5bb6。",
                        url="https://finance.example.invalid/news/03690-risk-remediation",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("03690.HK", "\u7f8e\u56e2", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u7f8e\u56e2 03690 \u4e0b\u67b6\u6d89\u8272\u60c5\u6309\u6469\u4f1a\u6240\u5546\u5bb6"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_contact_like_product_token_does_not_trigger_adult_spam_filter(self) -> None:
        """Product/version identifiers such as QQ2024 need adult context before filtering."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 QQ2024 \u5f00\u653e\u9884\u7ea6",
                        fresh,
                        snippet="QQ2024 \u4ea7\u54c1\u5347\u7ea7\u5f00\u653e\u9884\u7ea6，\u4f01\u4e1a\u901a\u4fe1\u529f\u80fd\u589e\u5f3a。",
                        url="https://finance.example.invalid/products/QQ2024",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u817e\u8baf\u63a7\u80a1 00700 QQ2024 \u5f00\u653e\u9884\u7ea6"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_adult_contact_id_with_full_width_separator_is_filtered(self) -> None:
        """Contact IDs such as QQ：123456 should count as adult-service spam signals."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u5c0f\u59d0\u4e0a\u95e8 QQ：123456",
                        fresh,
                        snippet="\u8054\u7cfb\u83b7\u53d6\u8be6\u60c5。",
                        url="https://spam.example.invalid/local/qq123456",
                        source="spam.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/00700-buyback",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])

    def test_adult_alphanumeric_contact_handle_is_filtered(self) -> None:
        """Contact handles such as \u5fae\u4fe1：abc123 should count as adult-service spam signals."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u5c0f\u59d0\u4e0a\u95e8 \u5fae\u4fe1：abc123",
                        fresh,
                        snippet="\u8054\u7cfb\u83b7\u53d6\u8be6\u60c5。",
                        url="https://spam.example.invalid/local/wechat-abc123",
                        source="spam.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/00700-buyback",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])

    def test_adult_phone_contact_is_filtered(self) -> None:
        """Phone contact labels should count as contact signals with adult-service context."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u5c0f\u59d0\u4e0a\u95e8 \u7535\u8bdd13800138000",
                        fresh,
                        snippet="\u8054\u7cfb\u83b7\u53d6\u8be6\u60c5。",
                        url="https://spam.example.invalid/local/phone-13800138000",
                        source="spam.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/00700-buyback",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])

    def test_healthcare_phone_contact_news_does_not_trigger_adult_spam_filter(self) -> None:
        """Normal phone contacts plus healthcare category wording are not adult-service spam."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u6c64\u81e3\u500d\u5065 300146 \u4fdd\u5065\u54c1\u4e1a\u52a1\u589e\u957f \u8054\u7cfb\u7535\u8bdd02012345678",
                        fresh,
                        snippet="\u516c\u53f8\u4fdd\u5065\u54c1\u4e1a\u52a1\u589e\u957f，\u6295\u8d44\u8005\u8054\u7cfb\u7535\u8bdd02012345678。",
                        url="https://finance.example.invalid/news/300146-healthcare",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("300146", "\u6c64\u81e3\u500d\u5065", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u6c64\u81e3\u500d\u5065 300146 \u4fdd\u5065\u54c1\u4e1a\u52a1\u589e\u957f \u8054\u7cfb\u7535\u8bdd02012345678"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_content_moderation_pornography_phrase_does_not_trigger_adult_spam_filter(self) -> None:
        """Content-safety/regulatory news can mention \u8272\u60c5 without being adult-service spam."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u52a0\u5f3a\u8272\u60c5\u4f4e\u4fd7\u5185\u5bb9\u6cbb\u7406",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u5347\u7ea7\u5185\u5bb9\u5b89\u5168\u4f53\u7cfb，\u6301\u7eed\u6cbb\u7406\u8272\u60c5\u4f4e\u4fd7\u5185\u5bb9\u98ce\u9669。",
                        url="https://finance.example.invalid/news/00700-content-safety",
                        source="finance.example.invalid",
                    )
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=1)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u817e\u8baf\u63a7\u80a1 00700 \u52a0\u5f3a\u8272\u60c5\u4f4e\u4fd7\u5185\u5bb9\u6cbb\u7406"],
        )
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")

    def test_label_only_official_source_is_honored_without_url(self) -> None:
        """Exact official labels without URL should still receive official-source treatment."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    SearchResult(
                        title="\u8463\u4e8b\u4f1a\u516c\u544a",
                        snippet="\u80a1\u4efd\u56de\u8d2d\u4e8b\u9879。",
                        url="",
                        source="hkexnews",
                        published_date=fresh,
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/00700-buyback",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=2)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a", "\u8463\u4e8b\u4f1a\u516c\u544a"],
        )
        official_result = resp.results[1]
        self.assertGreater(official_result.relevance_score or 0, 0)
        self.assertIn("\u6765\u6e90\u63a5\u8fd1\u516c\u544a\u6216\u4ea4\u6613\u6240\u6e20\u9053", official_result.relevance_reasons)

    def test_full_chinese_official_source_label_is_honored_without_url(self) -> None:
        """Full Chinese exchange labels without URL should retain official-source treatment."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    SearchResult(
                        title="\u4e0a\u5e02\u516c\u53f8\u516c\u544a",
                        snippet="\u80a1\u4efd\u56de\u8d2d\u4e8b\u9879。",
                        url="",
                        source="\u4e0a\u6d77\u8bc1\u5238\u4ea4\u6613\u6240",
                        published_date=fresh,
                    ),
                    _result(
                        "\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u8d35\u5dde\u8305\u53f0\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://finance.example.invalid/news/600519-buyback",
                        source="finance.example.invalid",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=2)

        self.assertEqual(
            [item.title for item in resp.results],
            ["\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a", "\u4e0a\u5e02\u516c\u53f8\u516c\u544a"],
        )
        official_result = resp.results[1]
        self.assertGreater(official_result.relevance_score or 0, 0)
        self.assertIn("\u6765\u6e90\u63a5\u8fd1\u516c\u544a\u6216\u4ea4\u6613\u6240\u6e20\u9053", official_result.relevance_reasons)

    def test_spoofed_official_tokens_do_not_bypass_news_admission(self) -> None:
        """Official exemptions should require trusted parsed hosts or exact source labels."""
        fresh = datetime.now().date().isoformat()
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u6781\u901f\u7248\u5b89\u88c5\u5305\u4e0b\u8f7d",
                        fresh,
                        snippet="\u5f53\u524d\u7248\u672c 686.38MB，84%\u597d\u8bc4，\u9002\u5408\u4e0b\u8f7d\u5b89\u88c5\u5230\u624b\u673a。",
                        url="https://spam.example.invalid/sec.gov/apps/douyang",
                        source="spam.example.invalid",
                    ),
                    _result(
                        "1000+ \u5b9c\u660c\u5c0f\u59d0\u4e0a\u95e8\u7279\u6b8a\u670d\u52a1",
                        fresh,
                        snippet="\u5c0f\u59d0\u9884\u7ea6 yue2345，\u540c\u57ce\u7ea6\u70ae、\u4fdd\u5065\u6309\u6469、\u63a8\u6cb9\u5957\u9910。",
                        url="https://hkexnews.evil.invalid/local/yue2345",
                        source="hkexnews.evil.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u5b98\u65b9app\u4e0b\u8f7d\u94fe\u63a5",
                        fresh,
                        snippet="\u5b89\u5353\u5ba2\u6237\u7aef\u4e0b\u8f7d，\u652f\u6301\u6781\u901f\u7248\u4e0b\u8f7d。",
                        url="https://hkexnews.evil.invalid/guide/officialdownload",
                        source="hkexnews",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 SEC \u5b98\u65b9app\u4e0b\u8f7d\u94fe\u63a5",
                        fresh,
                        snippet="\u5b89\u5353\u5ba2\u6237\u7aef\u4e0b\u8f7d，\u652f\u6301\u6781\u901f\u7248\u4e0b\u8f7d。",
                        url="https://spam.example.invalid/apps/sec-download",
                        source="sec.gov",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        url="https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0613/example.pdf",
                        source="hkexnews",
                    ),
                ]
            ),
        )

        resp = service.search_stock_news("00700.HK", "\u817e\u8baf\u63a7\u80a1", max_results=3)

        self.assertEqual([item.title for item in resp.results], ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"])

    def test_comprehensive_intel_filters_fillers_before_prompt_context(self) -> None:
        """Admission filtering should run before per-dimension result limiting."""
        fresh = datetime.now().date().isoformat()
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
            response=_response(
                [
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u6781\u901f\u7248\u5b89\u88c5\u5305\u4e0b\u8f7d",
                        fresh,
                        snippet="\u5f53\u524d\u7248\u672c 686.38MB，84%\u597d\u8bc4，\u9002\u5408\u4e0b\u8f7d\u5b89\u88c5\u5230\u624b\u673a。",
                        url="https://cdn.example.invalid/apps/00700/download",
                        source="cdn.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 Android \u5b89\u88c5\u5305\u8bc4\u5206",
                        fresh,
                        snippet="\u5e94\u7528\u7248\u672c 12.8，\u8bc4\u5206 4.9，\u5b89\u88c5\u540e\u53ef\u67e5\u770b\u884c\u60c5。",
                        url="https://finance.example.invalid/tencent/00700-rating",
                        source="finance.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 iOS \u65e7\u7248\u4e0b\u8f7d",
                        fresh,
                        snippet="\u5386\u53f2\u7248\u672c\u5b89\u88c5\u5305 256MB，\u7528\u6237\u597d\u8bc4\u7387 96%。",
                        url="https://download.example.invalid/ios/00700",
                        source="download.example.invalid",
                    ),
                    _result(
                        "\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                        fresh,
                        snippet="\u817e\u8baf\u63a7\u80a1\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                        source="hkexnews",
                    ),
                ]
            ),
        )

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="00700.HK",
                stock_name="\u817e\u8baf\u63a7\u80a1",
                max_searches=1,
            )

        self.assertEqual(
            [item.title for item in intel["latest_news"].results],
            ["\u817e\u8baf\u63a7\u80a1 00700 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"],
        )
        mock_search.assert_called_once()

    def test_a_share_chinese_direct_news_beats_english_direct_provider_fallback(self) -> None:
        """Chinese-preferred queries should keep looking past English-only direct hits."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        p1 = SimpleNamespace(
            is_available=True,
            name="EnglishDirect",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "Kweichow Moutai 600519 announces buyback",
                            fresh,
                            snippet="The company reported an updated share repurchase plan.",
                        )
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="ChineseDirect",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a",
                            fresh,
                            snippet="\u8d35\u5dde\u8305\u53f0\u62ab\u9732\u516c\u53f8\u56de\u8d2d\u516c\u544a。",
                        )
                    ]
                )
            ),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=1)

        self.assertEqual(resp.results[0].title, "\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_hk_stock_relevance_drops_similar_name_noise(self) -> None:
        """HK stock matching should drop similar-name noise when exact hits exist."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        provider = SimpleNamespace(
            is_available=True,
            name="HKProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "\u817e\u8baf\u97f3\u4e50\u53d1\u5e03\u65b0\u4e13\u8f91\u5408\u4f5c\u8ba1\u5212",
                            fresh,
                            snippet="\u817e\u8baf\u97f3\u4e50\u5a31\u4e50\u96c6\u56e2\u5ba3\u5e03\u5185\u5bb9\u5408\u4f5c。",
                        ),
                        _result(
                            "\u817e\u8baf\u63a7\u80a1 00700 \u516c\u544a：\u56de\u8d2d\u80a1\u4efd",
                            fresh,
                            snippet="\u817e\u8baf\u63a7\u80a1\u5728\u6e2f\u4ea4\u6240\u62ab\u9732\u80a1\u4efd\u56de\u8d2d\u516c\u544a。",
                            source="hkexnews",
                        ),
                    ]
                )
            ),
        )
        service._providers = [provider]

        resp = service.search_stock_news("hk00700", "\u817e\u8baf\u63a7\u80a1", max_results=2)

        self.assertEqual(resp.results[0].title, "\u817e\u8baf\u63a7\u80a1 00700 \u516c\u544a：\u56de\u8d2d\u80a1\u4efd")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        self.assertEqual(len(resp.results), 1)

    def test_hk_stock_bare_short_code_does_not_match_index_points(self) -> None:
        """Bare HK short codes should not make index-point headlines direct hits."""
        result = SearchService._score_news_relevance(
            _result(
                "\u6052\u751f\u6307\u6570\u5927\u6da8700\u70b9 \u79d1\u6280\u80a1\u666e\u904d\u53cd\u5f39",
                datetime.now().date().isoformat(),
                snippet="\u6e2f\u80a1\u5e02\u573a\u60c5\u7eea\u56de\u6696，\u6307\u6570\u8d70\u5f3a。",
            ),
            stock_code="hk00700",
            stock_name="\u817e\u8baf\u63a7\u80a1",
        )

        self.assertNotEqual(result.relevance_category, "direct_company_news")
        self.assertNotIn("\u80a1\u7968\u4ee3\u7801 700", "；".join(result.relevance_reasons or []))

    def test_us_stock_ticker_relevance_beats_ambiguous_company_word(self) -> None:
        """US ticker hits should outrank ambiguous common-word company-name noise."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        provider = SimpleNamespace(
            is_available=True,
            name="USProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "Apple growers face lower fruit prices",
                            fresh,
                            snippet="Agriculture market report on orchards.",
                        ),
                        _result(
                            "AAPL Apple earnings beat analyst expectations",
                            fresh,
                            snippet="Apple shares rose after quarterly revenue guidance improved.",
                        ),
                    ]
                )
            ),
        )
        service._providers = [provider]

        resp = service.search_stock_news("AAPL", "Apple", max_results=2)

        self.assertEqual(resp.results[0].title, "AAPL Apple earnings beat analyst expectations")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        self.assertEqual(resp.results[1].relevance_category, "sector_related_news")

    def test_ambiguous_company_name_with_generic_event_terms_stays_background(self) -> None:
        """Generic event words should not make ambiguous company names direct without ticker."""
        scored = SearchService._score_news_relevance(
            _result(
                "Apple stock results harvest",
                datetime.now().date().isoformat(),
                snippet="Agriculture market report on orchards.",
            ),
            stock_code="AAPL",
            stock_name="Apple",
        )

        self.assertNotEqual(scored.relevance_category, "direct_company_news")
        self.assertFalse(
            any(
                reason.startswith(("\u6807\u9898\u547d\u4e2d\u80a1\u7968\u4ee3\u7801", "\u6458\u8981\u547d\u4e2d\u80a1\u7968\u4ee3\u7801", "\u94fe\u63a5\u547d\u4e2d\u80a1\u7968\u4ee3\u7801"))
                for reason in (scored.relevance_reasons or [])
            )
        )

    def test_suffixed_stock_codes_keep_canonical_identity_terms(self) -> None:
        """Suffixed market codes should still emit canonical direct-match variants."""
        cases = (
            ("00700.HK", {"00700", "HK00700"}),
            ("600519.SH", {"600519", "600519.SH"}),
            ("AAPL.US", {"AAPL", "NASDAQ:AAPL", "NYSE:AAPL"}),
        )
        for stock_code, expected_terms in cases:
            with self.subTest(stock_code=stock_code):
                terms = set(SearchService._stock_code_identity_terms(stock_code))
                self.assertTrue(expected_terms.issubset(terms))

    def test_suffixed_market_codes_score_canonical_code_hits_as_direct(self) -> None:
        """Canonical code hits from suffixed inputs should be direct company news."""
        fresh = datetime.now().date().isoformat()
        cases = (
            ("00700.HK", "HK00700 announces buyback"),
            ("600519.SH", "600519 \u53d1\u5e03\u56de\u8d2d\u516c\u544a"),
            ("AAPL.US", "AAPL announces quarterly results"),
        )
        for stock_code, title in cases:
            with self.subTest(stock_code=stock_code):
                scored = SearchService._score_news_relevance(
                    _result(
                        title,
                        fresh,
                        snippet="The company reported a share buyback and quarterly results.",
                    ),
                    stock_code=stock_code,
                    stock_name="Unmatched Name",
                )
                self.assertEqual(scored.relevance_category, "direct_company_news")
                self.assertIn("\u80a1\u7968\u4ee3\u7801", "；".join(scored.relevance_reasons or []))

    def test_us_ticker_matches_before_known_dotted_market_suffix(self) -> None:
        """Ticker boundaries should allow explicit market suffixes from news feeds."""
        self.assertTrue(
            SearchService._contains_stock_code_identity_term("AAPL.US shares rally", "AAPL")
        )
        self.assertTrue(
            SearchService._contains_stock_code_identity_term("aapl.us shares rally", "AAPL")
        )
        self.assertTrue(
            SearchService._contains_stock_code_identity_term("aapl shares rally", "AAPL")
        )
        self.assertTrue(
            SearchService._contains_stock_code_identity_term("TSLA.O gains after results", "TSLA")
        )
        self.assertTrue(
            SearchService._contains_stock_code_identity_term("tsla.o gains after results", "TSLA")
        )
        self.assertFalse(
            SearchService._contains_stock_code_identity_term("AAPL.COM launches update", "AAPL")
        )

        scored = SearchService._score_news_relevance(
            _result(
                "msft.us earnings beat expectations",
                datetime.now().date().isoformat(),
                snippet="Quarterly revenue guidance improved.",
            ),
            stock_code="MSFT",
            stock_name="Microsoft",
        )
        self.assertEqual(scored.relevance_category, "direct_company_news")
        self.assertIn("\u80a1\u7968\u4ee3\u7801", "；".join(scored.relevance_reasons or []))

    def test_one_letter_us_ticker_does_not_match_common_article_words(self) -> None:
        """Bare one-letter US tickers should not make ordinary words direct hits."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        p1 = SimpleNamespace(
            is_available=True,
            name="GenericProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "A new investing playbook emerges",
                            fresh,
                            snippet="Markets weigh a broad macro update.",
                        )
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="CompanyProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "Agilent Technologies announces quarterly earnings",
                            fresh,
                            snippet="Agilent Technologies revenue guidance improved.",
                        )
                    ]
                )
            ),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("A", "Agilent Technologies", max_results=1)

        self.assertEqual(resp.results[0].title, "Agilent Technologies announces quarterly earnings")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_common_word_us_ticker_does_not_match_title_case_words(self) -> None:
        """Bare alphabetic tickers should not turn ordinary words into direct hits."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        p1 = SimpleNamespace(
            is_available=True,
            name="GenericProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "All investors brace for inflation data",
                            fresh,
                            snippet="Market participants watch a broad macro update.",
                        )
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="CompanyProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "ALL Allstate quarterly earnings beat expectations",
                            fresh,
                            snippet="Allstate revenue guidance improved after quarterly results.",
                        )
                    ]
                )
            ),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("ALL", "Allstate", max_results=1)

        self.assertEqual(resp.results[0].title, "ALL Allstate quarterly earnings beat expectations")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_ambiguous_english_name_generic_event_does_not_stop_provider_fallback(self) -> None:
        """Ambiguous title-only names plus broad event words should not count as direct hits."""
        fresh = datetime.now().date().isoformat()
        service = SearchService(
            bocha_keys=["dummy_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        p1 = SimpleNamespace(
            is_available=True,
            name="AmbiguousProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "Apple stock results improve after harvest update",
                            fresh,
                            snippet="Fruit market coverage tracks inventory and crop supply.",
                        )
                    ]
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="TickerProvider",
            search=MagicMock(
                return_value=_response(
                    [
                        _result(
                            "AAPL Apple earnings beat analyst expectations",
                            fresh,
                            snippet="Apple revenue guidance improved after quarterly earnings.",
                        )
                    ]
                )
            ),
        )
        service._providers = [p1, p2]

        resp = service.search_stock_news("AAPL", "Apple", max_results=1)

        self.assertEqual(resp.results[0].title, "AAPL Apple earnings beat analyst expectations")
        self.assertEqual(resp.results[0].relevance_category, "direct_company_news")
        p1.search.assert_called_once()
        p2.search.assert_called_once()

    def test_relevance_metadata_is_visible_in_news_context(self) -> None:
        result = SearchResult(
            title="\u8d35\u5dde\u8305\u53f0 600519 \u53d1\u5e03\u516c\u544a",
            snippet="\u516c\u53f8\u62ab\u9732\u8463\u4e8b\u4f1a\u51b3\u8bae。",
            url="https://example.com/news",
            source="cninfo",
            published_date=datetime.now().date().isoformat(),
            relevance_score=100,
            relevance_category="direct_company_news",
            relevance_reasons=["\u6807\u9898\u547d\u4e2d\u80a1\u7968\u4ee3\u7801 600519", "\u6807\u9898\u547d\u4e2d\u516c\u53f8\u540d \u8d35\u5dde\u8305\u53f0"],
        )
        context = SearchResponse(query="\u8d35\u5dde\u8305\u53f0", results=[result], provider="Unit").to_context()

        self.assertIn("\u5173\u8054\u5ea6", context)
        self.assertIn("direct_company_news", context)
        self.assertIn("\u6807\u9898\u547d\u4e2d\u80a1\u7968\u4ee3\u7801 600519", context)

    def test_search_stock_news_brave_locale_matches_market_context(self) -> None:
        """Brave locale should follow Chinese-preferred vs US-stock contexts."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_iso = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        for stock_code, stock_name, expected_lang, expected_country, title, description in (
            ("600519", "\u8d35\u5dde\u8305\u53f0", "zh-hans", "CN", "\u4e2d\u6587\u8d44\u8baf", "\u4e2d\u6587\u6458\u8981"),
            ("AAPL", "Apple", "en", "US", "Apple earnings beat", "English summary"),
        ):
            with self.subTest(stock_code=stock_code):
                fake_response = MagicMock()
                fake_response.status_code = 200
                fake_response.json.return_value = {
                    "web": {
                        "results": [
                            {
                                "title": title,
                                "description": description,
                                "url": "https://example.com/news",
                                "age": fresh_iso,
                            }
                        ]
                    }
                }

                with patch("src.search_service.requests.get", return_value=fake_response) as mock_get:
                    service = SearchService(
                        brave_keys=["dummy_key"],
                        searxng_public_instances_enabled=False,
                        news_max_age_days=3,
                        news_strategy_profile="short",
                    )
                    resp = service.search_stock_news(stock_code, stock_name, max_results=1)

                self.assertEqual(len(resp.results), 1)
                params = mock_get.call_args.kwargs["params"]
                self.assertEqual(params["search_lang"], expected_lang)
                self.assertEqual(params["country"], expected_country)

    def test_search_comprehensive_intel_splits_strict_and_non_strict_filters(self) -> None:
        """Latest news stays strict while market analysis keeps undated results."""
        today = datetime.now().date()
        old = (today - timedelta(days=20)).isoformat()
        fresh = (today - timedelta(days=1)).isoformat()
        analysis_dt = datetime.now(timezone.utc).replace(microsecond=0)
        analysis_text = analysis_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        expected_analysis_date = analysis_dt.astimezone().date().isoformat()

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="medium",  # min(7,3)=3
        )
        mock_search.side_effect = [
            _response([_result("old", old), _result("fresh", fresh)]),
            _response([_result("analysis_unknown", None), _result("analysis_dated", analysis_text)]),
        ]
        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                max_searches=2,
            )

        self.assertEqual(
            [call[1]["days"] for call in mock_search.call_args_list],
            [3, service.ANALYTICAL_INTEL_LOOKBACK_DAYS],
        )
        for call in mock_search.call_args_list:
            self.assertEqual(call[1]["max_results"], 6)  # target 3 -> overfetch 6

        self.assertEqual([item.title for item in intel["latest_news"].results], ["fresh"])
        self.assertEqual(
            [item.title for item in intel["market_analysis"].results],
            ["analysis_unknown", "analysis_dated"],
        )
        self.assertIsNone(intel["market_analysis"].results[0].published_date)
        self.assertEqual(intel["market_analysis"].results[1].published_date, expected_analysis_date)

    def test_search_comprehensive_intel_widens_analytical_provider_windows(self) -> None:
        """Market analysis and earnings should request a longer provider lookback."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([_result("market_analysis", None)]),
            _response([_result("risk_check", fresh_text)]),
            _response([_result("announcement_item", fresh_text)]),
            _response([_result("earnings", None)]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                max_searches=5,
            )

        self.assertIn("earnings", intel)
        self.assertEqual(
            [call[1]["days"] for call in mock_search.call_args_list],
            [
                3,
                service.ANALYTICAL_INTEL_LOOKBACK_DAYS,
                3,
                3,
                service.ANALYTICAL_INTEL_LOOKBACK_DAYS,
            ],
        )

    def test_search_comprehensive_intel_analytical_keeps_unknown_dates_and_crops_by_window(self) -> None:
        """Analytical dimensions keep unknown-date results while clipping known results to 180 days."""
        today = datetime.now().date()
        very_old = (today - timedelta(days=220)).isoformat()
        in_window = (today - timedelta(days=170)).isoformat()
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([
                _result("market_analysis_too_old", very_old),
                _result("market_analysis_unknown", None),
                _result("market_analysis_in_window", in_window),
            ]),
            _response([_result("risk_check", fresh_text)]),
            _response([_result("announcement_item", fresh_text)]),
            _response([
                _result("earnings_too_old", very_old),
                _result("earnings_unknown", None),
                _result("earnings_in_window", in_window),
            ]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                max_searches=5,
            )

        self.assertEqual(
            [item.title for item in intel["market_analysis"].results],
            ["market_analysis_unknown", "market_analysis_in_window"],
        )
        self.assertIsNone(intel["market_analysis"].results[0].published_date)
        self.assertEqual(intel["market_analysis"].results[1].published_date, in_window)
        self.assertEqual(
            [item.title for item in intel["earnings"].results],
            ["earnings_unknown", "earnings_in_window"],
        )
        self.assertIsNone(intel["earnings"].results[0].published_date)
        self.assertEqual(intel["earnings"].results[1].published_date, in_window)

    def test_search_comprehensive_intel_etf_risk_check_keeps_unknown_dates(self) -> None:
        """ETF risk_check should avoid strict freshness filtering."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        expected_fresh_date = fresh_dt.astimezone().date().isoformat()

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([_result("market_analysis_unknown", None)]),
            _response([_result("risk_unknown", None)]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="510300",
                stock_name="\u6caa\u6df1300ETF",
                max_searches=3,
            )

        self.assertEqual(intel["latest_news"].results[0].published_date, expected_fresh_date)
        self.assertEqual([item.title for item in intel["market_analysis"].results], ["market_analysis_unknown"])
        self.assertIsNone(intel["market_analysis"].results[0].published_date)
        self.assertEqual([item.title for item in intel["risk_check"].results], ["risk_unknown"])
        self.assertIsNone(intel["risk_check"].results[0].published_date)

    def test_search_comprehensive_intel_non_etf_risk_check_stays_strict(self) -> None:
        """Non-ETF risk_check should keep strict freshness filtering."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        expected_fresh_date = fresh_dt.astimezone().date().isoformat()

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([_result("market_analysis_unknown", None)]),
            _response([_result("risk_unknown", None)]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                max_searches=3,
            )

        self.assertEqual(intel["latest_news"].results[0].published_date, expected_fresh_date)
        self.assertEqual([item.title for item in intel["market_analysis"].results], ["market_analysis_unknown"])
        self.assertIsNone(intel["market_analysis"].results[0].published_date)
        self.assertEqual(intel["risk_check"].results, [])

    def test_announcements_dimension_included_within_max_searches_5(self) -> None:
        """announcements is now at index 3 so it is processed when max_searches>=4."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([_result("market_analysis", None)]),
            _response([_result("risk_check", fresh_text)]),
            _response([_result("announcement_item", fresh_text)]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                max_searches=4,
            )

        self.assertIn("announcements", intel)
        self.assertEqual(
            [item.title for item in intel["announcements"].results],
            ["announcement_item"],
        )

    def test_announcements_dimension_uses_news_topic_and_strict_filter(self) -> None:
        """announcements uses tavily_topic='news' and strict_freshness=True."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        old = (datetime.now().date() - timedelta(days=30)).isoformat()

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([_result("market_analysis", None)]),
            _response([_result("risk_check", fresh_text)]),
            _response([_result("old_announcement", old), _result("fresh_announcement", fresh_text)]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="\u8d35\u5dde\u8305\u53f0",
                max_searches=4,
            )

        self.assertIn("announcements", intel)
        # strict_freshness=True: stale result is filtered out
        titles = [item.title for item in intel["announcements"].results]
        self.assertNotIn("old_announcement", titles)
        self.assertIn("fresh_announcement", titles)

    def test_announcements_etf_is_not_strict(self) -> None:
        """For ETF, announcements dimension also uses tavily_topic='news' and strict_freshness=True."""
        fresh_dt = datetime.now(timezone.utc).replace(microsecond=0)
        fresh_text = fresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        mock_search.side_effect = [
            _response([_result("latest_news", fresh_text)]),
            _response([_result("market_analysis", None)]),
            _response([_result("risk_check", None)]),
            _response([_result("announcement_item", fresh_text)]),
        ]

        with patch("src.search_service.time.sleep"):
            intel = service.search_comprehensive_intel(
                stock_code="510300",
                stock_name="\u6caa\u6df1300ETF",
                max_searches=4,
            )

        self.assertIn("announcements", intel)

    def test_effective_window_helper_has_no_side_effect(self) -> None:
        """_effective_news_window_days should not mutate stored news_window_days."""
        service, _ = self._create_service_with_mock_provider(
            news_max_age_days=3,
            news_strategy_profile="short",
        )
        service.news_window_days = 99
        resolved = service._effective_news_window_days()
        self.assertEqual(resolved, 3)
        self.assertEqual(service.news_window_days, 99)

    def test_unix_timestamp_normalizes_to_local_date(self) -> None:
        """Unix timestamp should be converted to local date before window filtering."""
        dt_utc = datetime(2026, 3, 15, 23, 30, tzinfo=timezone.utc)
        timestamp = str(int(dt_utc.timestamp()))
        expected_local_date = dt_utc.astimezone().date()
        parsed = SearchService._normalize_news_publish_date(timestamp)
        self.assertEqual(parsed, expected_local_date)

    def test_iso_utc_string_normalizes_to_local_date(self) -> None:
        """ISO datetime with timezone should be converted to local date."""
        dt_utc = datetime(2026, 3, 15, 23, 30, tzinfo=timezone.utc)
        iso_text = "2026-03-15T23:30:00Z"
        expected_local_date = dt_utc.astimezone().date()
        parsed = SearchService._normalize_news_publish_date(iso_text)
        self.assertEqual(parsed, expected_local_date)

    def test_rfc_utc_string_normalizes_to_local_date(self) -> None:
        """RFC datetime with timezone should be converted to local date."""
        dt_utc = datetime(2026, 3, 15, 23, 30, tzinfo=timezone.utc)
        rfc_text = "Sun, 15 Mar 2026 23:30:00 +0000"
        expected_local_date = dt_utc.astimezone().date()
        parsed = SearchService._normalize_news_publish_date(rfc_text)
        self.assertEqual(parsed, expected_local_date)


if __name__ == "__main__":
    unittest.main()
