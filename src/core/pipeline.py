# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis system - \u6838\u5fc3analyze\u6d41\u6c34\u7ebf
===================================

\u804c\u8d23:
1. \u7ba1\u7406\u6574\u4e2aanalysis flow
2. \u534f\u8c03\u6570\u636e\u83b7\u53d6、\u5b58\u50a8、search、analyze、\u901a\u77e5\u7b49\u6a21chunks
3. \u5b9e\u73b0\u5e76\u53d1\u63a7\u5236\u548c\u5f02\u5e38\u5904\u7406
4. \u63d0\u4f9b\u80a1\u7968analyze\u7684\u6838\u5fc3\u529f\u80fd
"""

import logging
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Tuple, Callable

import pandas as pd

from src.config import FUNDAMENTAL_STAGE_TIMEOUT_SECONDS_DEFAULT, get_config, Config
from src.storage import get_db
from data_provider import DataFetcherManager
from data_provider.base import is_bse_code, normalize_stock_code
from data_provider.realtime_types import ChipDistribution
from src.analyzer import (
    GeminiAnalyzer,
    AnalysisResult,
    fill_price_position_if_needed,
    normalize_chip_structure_availability,
    populate_decision_action_fields,
    stabilize_decision_with_structure,
)
from src.notification import NotificationService, NotificationChannel
from src.report_language import (
    get_placeholder_text,
    get_unknown_text,
    infer_decision_type_from_advice,
    localize_confidence_level,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.search_service import SearchService
from src.analysis_context_pack_prompt import format_analysis_context_pack_prompt_section
from src.analysis_context_pack_overview import render_analysis_context_pack_overview
from src.market_phase_summary import MARKET_PHASE_SUMMARY_KEY, render_market_phase_summary
from src.daily_market_context_guardrail import apply_daily_market_context_guardrail
from src.phase_decision_guardrail import apply_phase_decision_guardrails
from src.services.daily_market_context import (
    DailyMarketContext,
    DailyMarketContextService,
    format_daily_market_context_prompt_section,
)
from src.services.social_sentiment_service import SocialSentimentService
from src.services.intelligence_service import IntelligenceService
from src.services.analysis_context_builder import (
    AnalysisContextBuilder,
    PipelineAnalysisArtifacts,
)
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    current_diagnostic_snapshot,
    get_current_diagnostic_context,
    record_history_run,
    record_llm_run,
    record_llm_run_started,
    record_notification_run,
    reset_run_diagnostic_context,
    sanitize_diagnostic_text,
)
from src.services.decision_signal_extractor import extract_and_persist_from_analysis_result
from src.services.decision_signal_summary import summarize_decision_signal
from src.enums import ReportType
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult
from src.core.trading_calendar import (
    build_market_phase_context,
    get_effective_trading_date,
    get_market_for_stock,
    get_market_now,
    is_market_open,
)
from data_provider.us_index_mapping import is_us_stock_code
from bot.models import BotMessage


logger = logging.getLogger(__name__)

# \u9632\u5fa1 guard: \u5f53\u5b9e\u4f8b\u7ed5\u8fc7 __init__ (\u5982\u6d4b\u8bd5Medium __new__)\u6784\u9020\u65f6;
# double-check \u521d\u59cb\u5316 _single_stock_notify_lock \u4ecd\u7136\u7ebf\u7a0b\u5b89\u5168.
_SINGLE_STOCK_NOTIFY_LOCK_INIT_GUARD = threading.Lock()
_DAILY_MARKET_CONTEXT_SERVICE_LOCK_INIT_GUARD = threading.Lock()


def _symbol_scope_lookup_values(code: str, market: str) -> List[str]:
    """Return accepted persisted-intelligence symbol spellings for lookup."""
    raw = str(code or "").strip()
    normalized = normalize_stock_code(raw) if raw else ""
    values: List[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)

    def add_case_variants(value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        add(text)
        add(text.upper())
        add(text.lower())

    add_case_variants(normalized)
    add_case_variants(raw)

    normalized_upper = normalized.upper()
    if normalized_upper.startswith("HK") and normalized_upper[2:].isdigit():
        digits = normalized_upper[2:]
        trimmed_digits = digits.lstrip("0") or digits
        add_case_variants(normalized_upper)
        add_case_variants(digits)
        add_case_variants(trimmed_digits)
        add_case_variants(f"HK{trimmed_digits}")
        add_case_variants(f"{trimmed_digits}.HK")
        add_case_variants(f"{digits}.HK")
        return values

    if (market or "").strip().lower() != "cn":
        return values
    if not (normalized.isdigit() and len(normalized) == 6):
        return values

    raw_upper = raw.upper()
    exchange = ""
    if raw_upper.startswith(("SH", "SS")) or raw_upper.endswith((".SH", ".SS")):
        exchange = "SH"
    elif raw_upper.startswith("SZ") or raw_upper.endswith(".SZ"):
        exchange = "SZ"
    elif raw_upper.startswith("BJ") or raw_upper.endswith(".BJ"):
        exchange = "BJ"
    elif is_bse_code(normalized):
        exchange = "BJ"
    elif normalized.startswith(("5", "6", "9")):
        exchange = "SH"
    else:
        exchange = "SZ"

    add_case_variants(f"{exchange}{normalized}")
    add_case_variants(f"{exchange}.{normalized}")
    add_case_variants(f"{normalized}.{exchange}")
    if exchange == "SH":
        add_case_variants(f"SS.{normalized}")
        add_case_variants(f"{normalized}.SS")
    return values


class StockAnalysisPipeline:
    """
    \u80a1\u7968analyze\u4e3b\u6d41\u7a0b\u8c03\u5ea6\u5668

    \u804c\u8d23:
    1. \u7ba1\u7406\u6574\u4e2aanalysis flow
    2. \u534f\u8c03\u6570\u636e\u83b7\u53d6、\u5b58\u50a8、search、analyze、\u901a\u77e5\u7b49\u6a21chunks
    3. \u5b9e\u73b0\u5e76\u53d1\u63a7\u5236\u548c\u5f02\u5e38\u5904\u7406
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        max_workers: Optional[int] = None,
        source_message: Optional[BotMessage] = None,
        query_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        query_source: Optional[str] = None,
        save_context_snapshot: Optional[bool] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        analysis_skills: Optional[List[str]] = None,
        analysis_phase: str = "auto",
        portfolio_context: Optional[Dict[str, Any]] = None,
        daily_market_context_enabled: Optional[bool] = None,
        daily_market_context_allow_generate: bool = True,
    ):
        """
        \u521d\u59cb\u5316\u8c03\u5ea6\u5668

        Args:
            config: config\u5bf9\u8c61 (optional; default\u4f7f\u7528\u5168\u5c40config)
            max_workers: \u6700\u5927\u5e76\u53d1\u7ebf\u7a0b\u6570 (optional; default\u4ececonfig\u8bfb\u53d6)
        """
        self.config = config or get_config()
        self.max_workers = max_workers or self.config.max_workers
        self.source_message = source_message
        self.query_id = query_id
        self.trace_id = trace_id or query_id
        self.query_source = self._resolve_query_source(query_source)
        self.save_context_snapshot = (
            self.config.save_context_snapshot if save_context_snapshot is None else save_context_snapshot
        )
        self.progress_callback = progress_callback
        self.analysis_skills = list(analysis_skills) if analysis_skills is not None else None
        self.analysis_phase = analysis_phase or "auto"
        self.portfolio_context = dict(portfolio_context) if isinstance(portfolio_context, dict) else None
        self.daily_market_context_enabled = (
            bool(getattr(self.config, "daily_market_context_enabled", True))
            if daily_market_context_enabled is None
            else bool(daily_market_context_enabled)
        )
        self.daily_market_context_allow_generate = daily_market_context_allow_generate

        # \u521d\u59cb\u5316\u5404\u6a21chunks
        self.db = get_db()
        self.fetcher_manager = DataFetcherManager()
        # \u4e0d\u518d\u5355\u72ec\u521b\u5efa akshare_fetcher; \u7edf\u4e00\u4f7f\u7528 fetcher_manager \u83b7\u53d6\u589e\u5f3a\u6570\u636e
        self.trend_analyzer = StockTrendAnalyzer()  # \u6280\u672fanalyze\u5668
        self.analyzer = GeminiAnalyzer(config=self.config, skills=self.analysis_skills)
        self.notifier = NotificationService(source_message=source_message)
        self._single_stock_notify_lock = threading.Lock()
        self._daily_market_context_service_lock = threading.Lock()
        self._concept_rankings_cache_lock = threading.Lock()
        self._concept_rankings_cache: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = {}

        # \u521d\u59cb\u5316search\u670d\u52a1 (optional; initialization failed\u4e0d\u5e94\u963b\u65ad\u4e3banalysis flow)
        try:
            self.search_service = SearchService(
                bocha_keys=self.config.bocha_api_keys,
                tavily_keys=self.config.tavily_api_keys,
                anspire_keys=self.config.anspire_api_keys,
                brave_keys=self.config.brave_api_keys,
                serpapi_keys=self.config.serpapi_keys,
                minimax_keys=self.config.minimax_api_keys,
                searxng_base_urls=self.config.searxng_base_urls,
                searxng_public_instances_enabled=self.config.searxng_public_instances_enabled,
                news_max_age_days=self.config.news_max_age_days,
                news_strategy_profile=getattr(self.config, "news_strategy_profile", "short"),
            )
        except Exception as exc:
            logger.warning("search\u670d\u52a1initialization failed; \u5c06\u4ee5\u65e0searchmode\u8fd0\u884c: %s", exc, exc_info=True)
            self.search_service = None

        logger.info(f"\u8c03\u5ea6\u5668initialization complete; \u6700\u5927\u5e76\u53d1\u6570: {self.max_workers}")
        logger.info("enabled\u6280\u672fanalyze\u5f15\u64ce (\u5747\u7ebf/\u8d8b\u52bf/\u91cf\u4ef7\u6307\u6807)")
        # \u6253\u5370realtime quote/\u7b79\u7801configstatus
        if self.config.enable_realtime_quote:
            logger.info(f"realtime quoteenabled (\u4f18\u5148\u7ea7: {self.config.realtime_source_priority})")
        else:
            logger.info("realtime quotedisabled; \u5c06\u4f7f\u7528history\u6536\u76d8\u4ef7")
        if self.config.enable_chip_distribution:
            logger.info("chip distributionanalyzeenabled")
        else:
            logger.info("chip distributionanalyzedisabled")
        if self.search_service is None:
            logger.warning("search\u670d\u52a1\u672a\u542f\u7528 (initialization failedor\u4f9d\u8d56\u7f3a\u5931)")
        elif self.search_service.is_available:
            logger.info("search\u670d\u52a1enabled")
        else:
            logger.warning("search\u670d\u52a1\u672a\u542f\u7528 (not configuredsearch\u80fd\u529b)")

        # \u521d\u59cb\u5316\u793e\u4ea4\u8206\u60c5\u670d\u52a1 (\u4ec5US stock; optional)
        try:
            self.social_sentiment_service = SocialSentimentService(
                api_key=self.config.social_sentiment_api_key,
                api_url=self.config.social_sentiment_api_url,
            )
            if self.social_sentiment_service.is_available:
                logger.info("Social sentiment service enabled (Reddit/X/Polymarket, US stocks only)")
        except Exception as exc:
            logger.warning(
                "\u793e\u4ea4\u8206\u60c5\u670d\u52a1initialization failed; \u5c06skipping\u8206\u60c5analyze: %s",
                exc,
                exc_info=True,
            )
            self.social_sentiment_service = None

    def _emit_progress(self, progress: int, message: str) -> None:
        """Best-effort bridge from pipeline stages to task SSE progress."""
        callback = getattr(self, "progress_callback", None)
        if callback is None:
            return
        try:
            callback(progress, message)
        except Exception as exc:
            query_id = getattr(self, "query_id", None)
            logger.warning(
                "[pipeline] progress callback failed: %s (progress=%s, message=%r, query_id=%s)",
                exc,
                progress,
                message,
                query_id,
                extra={
                    "progress": progress,
                    "progress_message": message,
                    "query_id": query_id,
                },
            )

    def fetch_and_save_stock_data(
        self,
        code: str,
        force_refresh: bool = False,
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        \u83b7\u53d6\u5e76\u4fdd\u5b58\u5355stocks\u6570\u636e

        \u65ad\u70b9\u7eed\u4f20\u903b\u8f91:
        1. \u68c0check\u6570\u636elibrary\u662f\u5426\u5df2\u6709\u6700\u65b0\u53ef\u590d\u7528\u4ea4\u6613\u65e5\u6570\u636e
        2. \u5982\u679c\u6709\u4e14\u4e0d\u5f3a\u5236\u5237\u65b0; \u5219skipping\u7f51\u7edcrequest
        3. \u5426\u5219\u4ecedata source\u83b7\u53d6\u5e76\u4fdd\u5b58

        Args:
            code: stock code
            force_refresh: \u662f\u5426\u5f3a\u5236\u5237\u65b0 (\u5ffd\u7565\u672c\u5730cache)
            current_time: \u672c\u8f6e\u8fd0\u884c\u51bb\u7ed3\u7684\u53c2\u8003\u65f6\u95f4; \u7528\u4e8e\u7edf\u4e00\u65ad\u70b9\u7eed\u4f20\u76ee\u6807\u4ea4\u6613\u65e5\u5224\u65ad

        Returns:
            Tuple[\u662f\u5426success, errorinfo]
        """
        stock_name = code
        try:
            # \u9996\u5148\u83b7\u53d6stock name
            stock_name = self.fetcher_manager.get_stock_name(code, allow_realtime=False)

            target_date = self._resolve_resume_target_date(
                code, current_time=current_time
            )

            # \u65ad\u70b9\u7eed\u4f20\u68c0check: \u5982\u679c\u6700\u65b0\u53ef\u590d\u7528\u4ea4\u6613\u65e5dataalready exists; \u5219skipping
            if not force_refresh and self.db.has_today_data(code, target_date):
                logger.info(
                    f"{stock_name}({code}) {target_date} \u6570\u636ealready exists; skipping\u83b7\u53d6 (\u65ad\u70b9\u7eed\u4f20)"
                )
                return True, None

            # \u4ecedata source\u83b7\u53d6\u6570\u636e
            logger.info(f"{stock_name}({code}) \u5f00\u59cb\u4ecedata source\u83b7\u53d6\u6570\u636e...")
            df, source_name = self.fetcher_manager.get_daily_data(code, days=30)

            if df is None or df.empty:
                return False, "\u83b7\u53d6\u6570\u636e\u4e3a\u7a7a"

            # \u4fdd\u5b58\u5230\u6570\u636elibrary
            saved_count = self.db.save_daily_data(df, code, source_name)
            logger.info(f"{stock_name}({code}) \u6570\u636esave succeeded (source: {source_name}; \u65b0\u589e {saved_count} \u6761)")

            return True, None

        except Exception as e:
            error_msg = f"\u83b7\u53d6/\u4fdd\u5b58\u6570\u636efailed: {str(e)}"
            logger.error(f"{stock_name}({code}) {error_msg}")
            return False, error_msg

    def analyze_stock(
        self,
        code: str,
        report_type: ReportType,
        query_id: str,
        current_time: Optional[datetime] = None,
    ) -> Optional[AnalysisResult]:
        """
        analyze\u5355stocks (\u589e\u5f3a\u7248: \u542b\u91cf\u6bd4、turnover、\u7b79\u7801analyze、\u591a\u7ef4\u5ea6\u60c5\u62a5)

        \u6d41\u7a0b:
        1. \u83b7\u53d6realtime quote (\u91cf\u6bd4、turnover)- \u901a\u8fc7 DataFetcherManager \u81ea\u52a8\u6545\u969c\u5207\u6362
        2. \u83b7\u53d6chip distribution - \u901a\u8fc7 DataFetcherManager \u5e26\u7194\u65ad\u4fdd\u62a4
        3. \u8fdb\u884c\u8d8b\u52bfanalyze (\u57fa\u4e8e\u4ea4\u6613\u7406\u5ff5)
        4. \u591a\u7ef4\u5ea6\u60c5\u62a5search (\u6700\u65b0\u6d88\u606f+\u98ce\u9669\u6392check+\u4e1a\u7ee9\u9884\u671f)
        5. \u4ece\u6570\u636elibrary\u83b7\u53d6analyze\u4e0a\u4e0b\u6587
        6. \u8c03\u7528 AI \u8fdb\u884c\u7efc\u5408analyze

        Args:
            query_id: query\u94fe\u8def\u5173\u8054 id
            code: stock code
            report_type: report type
            current_time: \u672c\u8f6e\u8fd0\u884c\u51bb\u7ed3\u7684\u53c2\u8003\u65f6\u95f4; \u7528\u4e8e\u7edf\u4e00market\u9636\u6bb5\u4e0a\u4e0b\u6587

        Returns:
            AnalysisResult or None (\u5982\u679canalyzefailed)
        """
        stock_name = code
        try:
            portfolio_context = getattr(self, "portfolio_context", None)
            if not isinstance(portfolio_context, dict):
                portfolio_context = None
            market = get_market_for_stock(normalize_stock_code(code))
            market_phase_context = build_market_phase_context(
                market=market,
                current_time=current_time,
                trigger_source=self.query_source,
                analysis_phase=getattr(self, "analysis_phase", "auto"),
            )
            market_phase_context_dict = market_phase_context.to_dict()
            market_phase_summary = render_market_phase_summary(market_phase_context_dict)
            report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))
            daily_market_target_date = self._coerce_daily_market_context_date(
                getattr(market_phase_context, "effective_daily_bar_date", None)
                or market_phase_context_dict.get("effective_daily_bar_date")
            )
            if daily_market_target_date is None:
                daily_market_target_date = get_effective_trading_date(
                    market,
                    current_time=current_time,
                )
            daily_market_context = self._load_daily_market_context(
                market,
                target_date=daily_market_target_date,
            )

            self._emit_progress(18, f"{code}: \u6b63\u5728\u83b7\u53d6\u884c\u60c5\u4e0e\u7b79\u7801\u6570\u636e")
            # \u83b7\u53d6stock name (\u5148\u8d70\u8f7b\u91cfname\u8def\u5f84; \u540e\u7eed\u82e5 realtime_quote \u6709 name \u518d\u8986\u76d6)
            stock_name = self.fetcher_manager.get_stock_name(code, allow_realtime=False)

            # Step 1: \u83b7\u53d6realtime quote (\u91cf\u6bd4、turnover\u7b49)- \u4f7f\u7528\u7edf\u4e00\u5165\u53e3; \u81ea\u52a8\u6545\u969c\u5207\u6362
            realtime_quote = None
            try:
                if self.config.enable_realtime_quote:
                    realtime_quote = self.fetcher_manager.get_realtime_quote(code, log_final_failure=False)
                    if realtime_quote:
                        # \u4f7f\u7528realtime quote\u8fd4\u56de\u7684\u771f\u5b9estock name
                        if realtime_quote.name:
                            stock_name = realtime_quote.name
                        # \u517c\u5bb9\u4e0d\u540cdata source\u7684\u5b57\u6bb5 (\u6709\u4e9bdata source\u53ef\u80fd\u6ca1\u6709 volume_ratio)
                        volume_ratio = getattr(realtime_quote, 'volume_ratio', None)
                        turnover_rate = getattr(realtime_quote, 'turnover_rate', None)
                        logger.info(f"{stock_name}({code}) realtime quote: price={realtime_quote.price}, "
                                  f"\u91cf\u6bd4={volume_ratio}, turnover={turnover_rate}% "
                                  f"(source: {realtime_quote.source.value if hasattr(realtime_quote, 'source') else 'unknown'})")
                    else:
                        logger.warning(f"{stock_name}({code}) \u6240\u6709realtime quotedata source\u5747unavailable; \u5df2\u964d\u7ea7\u4e3ahistory\u6536\u76d8\u4ef7\u7ee7\u7eedanalyze")
                else:
                    logger.info(f"{stock_name}({code}) realtime quotedisabled; \u4f7f\u7528history\u6536\u76d8\u4ef7\u7ee7\u7eedanalyze")
            except Exception as e:
                logger.warning(f"{stock_name}({code}) realtime quote\u94fe\u8def\u5f02\u5e38; \u5df2\u964d\u7ea7\u4e3ahistory\u6536\u76d8\u4ef7\u7ee7\u7eedanalyze: {e}")

            # \u5982\u679c\u8fd8\u662f\u6ca1\u6709name; \u4f7f\u7528code\u4f5c\u4e3aname
            if not stock_name:
                stock_name = f'\u80a1\u7968{code}'

            # Step 2: \u83b7\u53d6chip distribution - \u4f7f\u7528\u7edf\u4e00\u5165\u53e3; \u5e26\u7194\u65ad\u4fdd\u62a4
            chip_data = None
            try:
                chip_data = self.fetcher_manager.get_chip_distribution(code)
                if chip_data:
                    logger.info(f"{stock_name}({code}) chip distribution: \u83b7\u5229\u6bd4\u4f8b={chip_data.profit_ratio:.1%}, "
                              f"90%\u96c6Medium\u5ea6={chip_data.concentration_90:.2%}")
                else:
                    logger.debug(f"{stock_name}({code}) chip distributionfetch failedordisabled")
            except Exception as e:
                logger.warning(f"{stock_name}({code}) \u83b7\u53d6chip distributionfailed: {e}")

            # If agent mode is explicitly enabled, or specific agent skills are configured, use the Agent analysis pipeline.
            # NOTE: use config.agent_mode (explicit opt-in) instead of
            # config.is_agent_available() so that users who only configured an
            # API Key for the traditional analysis path are not silently
            # switched to Agent mode (which is slower and more expensive).
            use_agent = getattr(self.config, 'agent_mode', False)
            if not use_agent:
                if self.analysis_skills:
                    use_agent = True
                    logger.info(f"{stock_name}({code}) Auto-enabled agent mode due to request skills: {self.analysis_skills}")
            if not use_agent:
                # Auto-enable agent mode when specific skills are configured (e.g., scheduled task with strategy)
                configured_skills = getattr(self.config, 'agent_skills', [])
                if configured_skills and configured_skills != ['all']:
                    use_agent = True
                    logger.info(f"{stock_name}({code}) Auto-enabled agent mode due to configured skills: {configured_skills}")

            self._emit_progress(32, f"{stock_name}: \u6b63\u5728\u805a\u5408fundamentals\u4e0e\u8d8b\u52bf\u6570\u636e")

            # Step 2.5: fundamentals\u80fd\u529b\u805a\u5408 (\u7edf\u4e00\u5165\u53e3; \u5f02\u5e38\u964d\u7ea7)
            # - failed\u65f6\u8fd4\u56de partial/failed; \u4e0d\u5f71\u54cd\u65e2\u6709\u6280\u672f\u9762/news\u94fe\u8def
            # - \u5173\u95ed\u5f00\u5173\u65f6\u4ecd\u8fd4\u56de not_supported \u7ed3\u6784
            fundamental_context = None
            try:
                fundamental_context = self.fetcher_manager.get_fundamental_context(
                    code,
                    budget_seconds=getattr(
                        self.config,
                        'fundamental_stage_timeout_seconds',
                        FUNDAMENTAL_STAGE_TIMEOUT_SECONDS_DEFAULT,
                    ),
                )
            except Exception as e:
                logger.warning(f"{stock_name}({code}) fundamentals\u805a\u5408failed: {e}")
                fundamental_context = self.fetcher_manager.build_failed_fundamental_context(code, str(e))

            fundamental_context = self._attach_belong_boards_to_fundamental_context(
                code,
                fundamental_context,
            )

            # P0: write-only snapshot, fail-open, no read dependency on this table.
            try:
                self.db.save_fundamental_snapshot(
                    query_id=query_id,
                    code=code,
                    payload=fundamental_context,
                    source_chain=fundamental_context.get("source_chain", []),
                    coverage=fundamental_context.get("coverage", {}),
                )
            except Exception as e:
                logger.debug(f"{stock_name}({code}) fundamentals\u5feb\u7167\u5199\u5165failed: {e}")

            # Step 3: \u8d8b\u52bfanalyze (\u57fa\u4e8e\u4ea4\u6613\u7406\u5ff5)— \u5728 Agent \u5206\u652f\u4e4b\u524d\u6267\u884c; \u4f9b\u4e24\u6761\u8def\u5f84\u5171\u7528
            trend_result: Optional[TrendAnalysisResult] = None
            try:
                from src.services.history_loader import get_frozen_target_date
                _mkt = get_market_for_stock(normalize_stock_code(code))
                frozen = get_frozen_target_date()
                end_date = frozen if frozen else get_market_now(_mkt).date()
                start_date = end_date - timedelta(days=89)  # ~60 trading days for MA60
                historical_bars = self.db.get_data_range(code, start_date, end_date)
                if historical_bars:
                    df = pd.DataFrame([bar.to_dict() for bar in historical_bars])
                    # Issue #234: Augment with realtime for intraday MA calculation
                    if self.config.enable_realtime_quote and realtime_quote:
                        df = self._augment_historical_with_realtime(df, realtime_quote, code)
                    trend_result = self.trend_analyzer.analyze(df, code)
                    logger.info(f"{stock_name}({code}) \u8d8b\u52bfanalyze: {trend_result.trend_status.value}, "
                              f"\u4e70\u5165\u4fe1\u53f7={trend_result.buy_signal.value}, \u8bc4\u5206={trend_result.signal_score}")
            except Exception as e:
                logger.warning(f"{stock_name}({code}) \u8d8b\u52bfanalyzefailed: {e}", exc_info=True)

            if use_agent:
                logger.info(f"{stock_name}({code}) \u542f\u7528 Agent mode\u8fdb\u884canalyze")
                self._emit_progress(58, f"{stock_name}: \u6b63\u5728\u5207\u6362 Agent analyze\u94fe\u8def")
                return self._analyze_with_agent(
                    code,
                    report_type,
                    query_id,
                    stock_name,
                    realtime_quote,
                    chip_data,
                    fundamental_context,
                    trend_result,
                    market_phase_context=market_phase_context_dict,
                    market_phase_summary=market_phase_summary,
                    daily_market_context=daily_market_context,
                    portfolio_context=portfolio_context,
                )

            # Step 4: \u591a\u7ef4\u5ea6\u60c5\u62a5search (\u6700\u65b0\u6d88\u606f+\u98ce\u9669\u6392check+\u4e1a\u7ee9\u9884\u671f)
            news_context = None
            persisted_intelligence_context = self._load_persisted_intelligence_context(
                code=code,
                stock_name=stock_name,
                market=market or "cn",
            )
            news_result_count: Optional[int] = None
            self._emit_progress(46, f"{stock_name}: \u6b63\u5728\u68c0\u7d22news\u4e0e\u8206\u60c5")
            if self.search_service is not None and self.search_service.is_available:
                logger.info(f"{stock_name}({code}) \u5f00\u59cb\u591a\u7ef4\u5ea6\u60c5\u62a5search...")

                # \u4f7f\u7528\u591a\u7ef4\u5ea6search (\u6700\u591a5\u6b21search)
                intel_results = self.search_service.search_comprehensive_intel(
                    stock_code=code,
                    stock_name=stock_name,
                    max_searches=5
                )

                # \u683c\u5f0f\u5316\u60c5\u62a5report
                if intel_results:
                    news_context = self.search_service.format_intel_report(intel_results, stock_name)
                    total_results = sum(
                        len(r.results) for r in intel_results.values() if r.success
                    )
                    news_result_count = total_results
                    logger.info(f"{stock_name}({code}) \u60c5\u62a5search\u5b8c\u6210: \u5171 {total_results} \u6761result")
                    logger.debug(f"{stock_name}({code}) \u60c5\u62a5searchresult:\n{news_context}")

                    # \u4fdd\u5b58news\u60c5\u62a5\u5230\u6570\u636elibrary (\u7528\u4e8e\u540e\u7eed\u590d\u76d8\u4e0equery)
                    try:
                        query_context = self._build_query_context(query_id=query_id)
                        for dim_name, response in intel_results.items():
                            if response and response.success and response.results:
                                self.db.save_news_intel(
                                    code=code,
                                    name=stock_name,
                                    dimension=dim_name,
                                    query=response.query,
                                    response=response,
                                    query_context=query_context
                                )
                    except Exception as e:
                        logger.warning(f"{stock_name}({code}) \u4fdd\u5b58news\u60c5\u62a5failed: {e}")
            else:
                logger.info(f"{stock_name}({code}) search\u670d\u52a1unavailable; skipping\u60c5\u62a5search")

            # Step 4.5: Social sentiment intelligence (US stocks only)
            if self.social_sentiment_service is not None and self.social_sentiment_service.is_available and is_us_stock_code(code):
                try:
                    social_context = self.social_sentiment_service.get_social_context(code)
                    if social_context:
                        logger.info(f"{stock_name}({code}) Social sentiment data retrieved")
                        if news_context:
                            news_context = news_context + "\n\n" + social_context
                        else:
                            news_context = social_context
                except Exception as e:
                    logger.warning(f"{stock_name}({code}) Social sentiment fetch failed: {e}")

            if persisted_intelligence_context:
                news_context = (
                    f"{news_context}\n\n{persisted_intelligence_context}"
                    if news_context
                    else persisted_intelligence_context
                )

            # Step 5: \u83b7\u53d6analyze\u4e0a\u4e0b\u6587 (\u6280\u672f\u9762\u6570\u636e)
            self._emit_progress(58, f"{stock_name}: \u6b63\u5728\u6574\u7406analyze\u4e0a\u4e0b\u6587")
            context = self._get_analysis_context_with_market_fallback(code)

            if context is None:
                logger.warning(f"{stock_name}({code}) \u65e0\u6cd5\u83b7\u53d6history\u884c\u60c5\u6570\u636e; \u5c06\u4ec5\u57fa\u4e8enews\u548crealtime quoteanalyze")
                _mkt_date = get_market_now(
                    get_market_for_stock(normalize_stock_code(code))
                ).date()
                context = {
                    'code': code,
                    'stock_name': stock_name,
                    'date': _mkt_date.isoformat(),
                    'data_missing': True,
                    'today': {},
                    'yesterday': {}
                }

            # Step 6: \u589e\u5f3a\u4e0a\u4e0b\u6587\u6570\u636e (\u6dfb\u52a0realtime quote、\u7b79\u7801、\u8d8b\u52bfanalysis result、stock name)
            enhanced_context = self._enhance_context(
                context,
                realtime_quote,
                chip_data,
                trend_result,
                stock_name,  # \u4f20\u5165stock name
                fundamental_context,
                market_phase_context=market_phase_context_dict,
                portfolio_context=portfolio_context,
            )
            enhanced_context["market_phase_context"] = market_phase_context_dict
            self._attach_daily_market_context(
                enhanced_context,
                daily_market_context,
                report_language=report_language,
            )
            if portfolio_context is not None:
                enhanced_context["portfolio_context"] = dict(portfolio_context)

            # Step 7: \u8c03\u7528 AI analyze (\u4f20\u5165\u589e\u5f3a\u7684\u4e0a\u4e0b\u6587\u548cnews)
            (
                analysis_context_pack_summary,
                analysis_context_pack_overview,
            ) = self._build_analysis_context_pack_outputs(
                self._build_legacy_analysis_artifacts(
                    code=code,
                    stock_name=stock_name,
                    market=market,
                    phase=market_phase_context_dict,
                    context=context,
                    enhanced_context=enhanced_context,
                    realtime_quote=realtime_quote,
                    trend_result=trend_result,
                    chip_data=chip_data,
                    fundamental_context=fundamental_context,
                    news_context=news_context,
                    news_result_count=news_result_count,
                    query_id=query_id,
                    portfolio_context=portfolio_context,
                ),
                report_language=report_language,
                code=code,
                query_id=query_id,
            )
            llm_progress_state = {"last_progress": 64}

            def _on_llm_stream(chars_received: int) -> None:
                dynamic_progress = min(92, 64 + min(chars_received // 80, 28))
                if dynamic_progress <= llm_progress_state["last_progress"]:
                    return
                llm_progress_state["last_progress"] = dynamic_progress
                self._emit_progress(
                    dynamic_progress,
                    f"{stock_name}: LLM \u6b63\u5728\u751f\u6210analysis result (\u5df2\u63a5\u6536 {chars_received} \u5b57\u7b26)",
                )

            self._emit_progress(64, f"{stock_name}: \u6b63\u5728request LLM \u751f\u6210report")
            llm_started_at = time.monotonic()
            try:
                record_llm_run_started(
                    model=getattr(self.config, "litellm_model", None),
                    call_type="analysis",
                )
                result = self.analyzer.analyze(
                    enhanced_context,
                    news_context=news_context,
                    progress_callback=self._emit_progress,
                    stream_progress_callback=_on_llm_stream,
                    analysis_context_pack_summary=analysis_context_pack_summary,
                )
                llm_duration_ms = int((time.monotonic() - llm_started_at) * 1000)
                record_llm_run(
                    success=bool(result and getattr(result, "success", True)),
                    model=getattr(result, "model_used", None) if result else None,
                    call_type="analysis",
                    duration_ms=llm_duration_ms,
                    error_type=(
                        None
                        if result and getattr(result, "success", True)
                        else "AnalysisResultError"
                    ),
                    error_message=(
                        getattr(result, "error_message", None)
                        if result and not getattr(result, "success", True)
                        else ("LLM returned empty result" if result is None else None)
                    ),
                )
            except Exception as exc:
                record_llm_run(
                    success=False,
                    model=getattr(self.config, "litellm_model", None),
                    call_type="analysis",
                    duration_ms=int((time.monotonic() - llm_started_at) * 1000),
                    error_type=type(exc).__name__,
                    error_message=exc,
                )
                raise

            # Step 7.5: \u586b\u5145analyze\u65f6\u7684priceinfo\u5230 result
            if result:
                self._emit_progress(94, f"{stock_name}: \u6b63\u5728\u6821\u9a8c\u5e76\u6574\u7406analysis result")
                result.query_id = query_id
                realtime_data = enhanced_context.get('realtime', {})
                result.current_price = realtime_data.get('price')
                result.change_pct = realtime_data.get('change_pct')

            # Step 7.6: chip_structure fallback (Issue #589) and unavailable collapse
            if result:
                normalize_chip_structure_availability(result, chip_data)

            # Step 7.7: price_position fallback
            if result:
                fill_price_position_if_needed(result, trend_result, realtime_quote)
                action_source_advice = getattr(result, "operation_advice", None)
                stabilize_decision_with_structure(result, trend_result, fundamental_context)
                adjustments = apply_phase_decision_guardrails(
                    result,
                    market_phase_summary=market_phase_summary,
                    analysis_context_pack_overview=analysis_context_pack_overview,
                    report_language=getattr(result, "report_language", None)
                    or getattr(self.config, "report_language", "zh"),
                )
                if adjustments:
                    logger.info("[phase_decision_guardrail] Applied adjustments for %s: %s", code, adjustments)
                market_context_adjustments = apply_daily_market_context_guardrail(
                    result,
                    daily_market_context=enhanced_context.get("daily_market_context"),
                    report_language=getattr(result, "report_language", None)
                    or getattr(self.config, "report_language", "zh"),
                )
                if market_context_adjustments:
                    logger.info(
                        "[daily_market_context_guardrail] Applied adjustments for %s: %s",
                        code,
                        market_context_adjustments,
                    )
                if isinstance(fundamental_context, dict):
                    result.fundamental_context = fundamental_context
                result.market_phase_summary = market_phase_summary
                result.analysis_context_pack_overview = analysis_context_pack_overview
                self._refresh_decision_action_for_final_result(
                    result,
                    report_type=report_type.value,
                    previous_operation_advice=action_source_advice,
                )

            # Step 8: \u4fdd\u5b58analyzehistory records
            if result and result.success:
                try:
                    self._emit_progress(97, f"{stock_name}: \u6b63\u5728\u4fdd\u5b58analyzereport")
                    context_snapshot = self._build_context_snapshot(
                        enhanced_context=enhanced_context,
                        news_content=news_context,
                        news_result_count=news_result_count,
                        realtime_quote=realtime_quote,
                        chip_data=chip_data,
                        analysis_context_pack_overview=analysis_context_pack_overview,
                        market_phase_summary=market_phase_summary,
                    )
                    result.diagnostic_context_snapshot = context_snapshot
                    saved_history_id = self.db.save_analysis_history(
                        result=result,
                        query_id=query_id,
                        report_type=report_type.value,
                        news_content=news_context,
                        context_snapshot=context_snapshot,
                        save_snapshot=self.save_context_snapshot
                    )
                    valid_saved_history_id = (
                        isinstance(saved_history_id, int)
                        and not isinstance(saved_history_id, bool)
                        and saved_history_id > 0
                    )
                    record_history_run(
                        report_saved=bool(saved_history_id),
                        metadata_saved=bool(saved_history_id),
                        analysis_history_id=(
                            saved_history_id if valid_saved_history_id else None
                        ),
                    )
                    if valid_saved_history_id:
                        self._extract_decision_signal_after_history_save(
                            result=result,
                            query_id=query_id,
                            source_report_id=saved_history_id,
                            report_type=report_type.value,
                            context_snapshot=context_snapshot,
                            portfolio_context=portfolio_context,
                        )
                except Exception as e:
                    record_history_run(
                        report_saved=False,
                        metadata_saved=False,
                        error_message=e,
                    )
                    logger.warning(f"{stock_name}({code}) \u4fdd\u5b58analyzehistoryfailed: {e}")

            return result

        except Exception as e:
            logger.error(f"{stock_name}({code}) analyzefailed: {e}")
            logger.exception(f"{stock_name}({code}) \u8be6\u7ec6errorinfo:")
            return None

    def _enhance_context(
        self,
        context: Dict[str, Any],
        realtime_quote,
        chip_data: Optional[ChipDistribution],
        trend_result: Optional[TrendAnalysisResult],
        stock_name: str = "",
        fundamental_context: Optional[Dict[str, Any]] = None,
        market_phase_context: Optional[Dict[str, Any]] = None,
        portfolio_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        \u589e\u5f3aanalyze\u4e0a\u4e0b\u6587

        \u5c06realtime quote、chip distribution、\u8d8b\u52bfanalysis result、stock name\u6dfb\u52a0\u5230\u4e0a\u4e0b\u6587Medium

        Args:
            context: \u539f\u59cb\u4e0a\u4e0b\u6587
            realtime_quote: realtime quote\u6570\u636e (UnifiedRealtimeQuote or None)
            chip_data: chip distribution\u6570\u636e
            trend_result: \u8d8b\u52bfanalysis result
            stock_name: stock name
            market_phase_context: \u5df2\u6784\u5efa\u7684market\u9636\u6bb5\u4e0a\u4e0b\u6587; \u7528\u4e8e\u6807\u8bb0\u76d8Medium partial bar

        Returns:
            \u589e\u5f3a\u540e\u7684\u4e0a\u4e0b\u6587
        """
        enhanced = context.copy()
        enhanced["report_language"] = normalize_report_language(getattr(self.config, "report_language", "zh"))

        # \u6dfb\u52a0stock name
        if stock_name:
            enhanced['stock_name'] = stock_name
        elif realtime_quote and getattr(realtime_quote, 'name', None):
            enhanced['stock_name'] = realtime_quote.name
        if isinstance(portfolio_context, dict):
            enhanced["portfolio_context"] = dict(portfolio_context)

        # \u5c06\u8fd0\u884c\u65f6search\u7a97\u53e3\u900f\u4f20\u7ed9 analyzer; \u907f\u514d\u4e0e\u5168\u5c40config\u91cd\u65b0\u8bfb\u53d6\u4ea7\u751f\u7a97\u53e3\u4e0d\u4e00\u81f4
        enhanced['news_window_days'] = getattr(self.search_service, "news_window_days", 3)

        # \u6dfb\u52a0realtime quote (\u517c\u5bb9\u4e0d\u540cdata source\u7684\u5b57\u6bb5\u5dee\u5f02)
        if realtime_quote:
            # \u4f7f\u7528 getattr \u5b89\u5168\u83b7\u53d6\u5b57\u6bb5; \u7f3a\u5931\u5b57\u6bb5\u8fd4\u56de None ordefault\u503c
            volume_ratio = getattr(realtime_quote, 'volume_ratio', None)
            quote_source = getattr(realtime_quote, 'source', None)
            quote_source_name = getattr(quote_source, 'value', quote_source)
            quote_source_name = str(quote_source_name) if quote_source_name is not None else None
            enhanced['realtime'] = {
                'name': getattr(realtime_quote, 'name', ''),
                'price': getattr(realtime_quote, 'price', None),
                'change_pct': getattr(realtime_quote, 'change_pct', None),
                'volume_ratio': volume_ratio,
                'volume_ratio_desc': self._describe_volume_ratio(volume_ratio) if volume_ratio else 'no data',
                'turnover_rate': getattr(realtime_quote, 'turnover_rate', None),
                'pe_ratio': getattr(realtime_quote, 'pe_ratio', None),
                'pb_ratio': getattr(realtime_quote, 'pb_ratio', None),
                'total_mv': getattr(realtime_quote, 'total_mv', None),
                'circ_mv': getattr(realtime_quote, 'circ_mv', None),
                'change_60d': getattr(realtime_quote, 'change_60d', None),
                'source': quote_source_name,
                'fetched_at': getattr(realtime_quote, 'fetched_at', None),
                'provider_timestamp': getattr(realtime_quote, 'provider_timestamp', None),
                'is_stale': getattr(realtime_quote, 'is_stale', None),
                'stale_seconds': getattr(realtime_quote, 'stale_seconds', None),
                'fallback_from': getattr(realtime_quote, 'fallback_from', None),
            }
            # \u79fb\u9664 None \u503c\u4ee5\u51cf\u5c11\u4e0a\u4e0b\u6587\u5927\u5c0f
            enhanced['realtime'] = {k: v for k, v in enhanced['realtime'].items() if v is not None}

        # \u6dfb\u52a0chip distribution
        if chip_data:
            current_price = getattr(realtime_quote, 'price', 0) if realtime_quote else 0
            enhanced['chip'] = {
                'profit_ratio': chip_data.profit_ratio,
                'avg_cost': chip_data.avg_cost,
                'concentration_90': chip_data.concentration_90,
                'concentration_70': chip_data.concentration_70,
                'chip_status': chip_data.get_chip_status(current_price or 0),
            }

        # \u6dfb\u52a0\u8d8b\u52bfanalysis result
        if trend_result:
            enhanced['trend_analysis'] = {
                'trend_status': trend_result.trend_status.value,
                'ma_alignment': trend_result.ma_alignment,
                'trend_strength': trend_result.trend_strength,
                'bias_ma5': trend_result.bias_ma5,
                'bias_ma10': trend_result.bias_ma10,
                'volume_status': trend_result.volume_status.value,
                'volume_trend': trend_result.volume_trend,
                'buy_signal': trend_result.buy_signal.value,
                'signal_score': trend_result.signal_score,
                'signal_reasons': trend_result.signal_reasons,
                'risk_factors': trend_result.risk_factors,
            }

        # Issue #234: \u76d8Mediumanalyze\u4f7f\u7528\u5b9e\u65f6 OHLC \u4e0e\u8d8b\u52bf MA \u8986\u76d6 today.
        # \u9632\u62a4\u6761\u4ef6: trend_result.ma5 > 0 \u8868\u793a MA \u8ba1\u7b97\u5df2success\u4e14\u6570\u636e\u91cf\u5145\u8db3.
        if realtime_quote and trend_result and trend_result.ma5 > 0:
            price = getattr(realtime_quote, 'price', None)
            if price is not None and price > 0:
                yesterday_close = None
                if enhanced.get('yesterday') and isinstance(enhanced['yesterday'], dict):
                    yesterday_close = enhanced['yesterday'].get('close')
                orig_today = enhanced.get('today') or {}
                market_today = get_market_now(
                    get_market_for_stock(normalize_stock_code(enhanced.get('code', '')))
                ).date().isoformat()
                source = getattr(realtime_quote, 'source', None)
                source_name = getattr(source, 'value', source)
                source_name = str(source_name) if source_name is not None else 'unknown'
                open_p = getattr(realtime_quote, 'open_price', None) or getattr(
                    realtime_quote, 'pre_close', None
                ) or yesterday_close or orig_today.get('open') or price
                high_p = getattr(realtime_quote, 'high', None) or price
                low_p = getattr(realtime_quote, 'low', None) or price
                vol = getattr(realtime_quote, 'volume', None)
                amt = getattr(realtime_quote, 'amount', None)
                pct = getattr(realtime_quote, 'change_pct', None)
                fetched_at = getattr(realtime_quote, 'fetched_at', None)
                provider_timestamp = getattr(realtime_quote, 'provider_timestamp', None)
                fallback_from = getattr(realtime_quote, 'fallback_from', None)
                realtime_today = {
                    'close': price,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'ma5': trend_result.ma5,
                    'ma10': trend_result.ma10,
                    'ma20': trend_result.ma20,
                    'date': market_today,
                    'data_source': f"realtime:{source_name}",
                    'realtime_source': source_name,
                    'is_estimated': True,
                }
                estimated_fields = [
                    'close', 'open', 'high', 'low', 'ma5', 'ma10', 'ma20',
                ]
                if vol is not None:
                    realtime_today['volume'] = vol
                    estimated_fields.append('volume')
                if amt is not None:
                    realtime_today['amount'] = amt
                    estimated_fields.append('amount')
                if pct is not None:
                    realtime_today['pct_chg'] = pct
                    estimated_fields.append('pct_chg')
                realtime_today['estimated_fields'] = estimated_fields
                if isinstance(market_phase_context, dict) and "is_partial_bar" in market_phase_context:
                    realtime_today['is_partial_bar'] = market_phase_context.get("is_partial_bar")
                if fetched_at is not None:
                    realtime_today['fetched_at'] = fetched_at
                if provider_timestamp is not None:
                    realtime_today['provider_timestamp'] = provider_timestamp
                if fallback_from is not None:
                    realtime_today['fallback_from'] = fallback_from
                realtime_owned_fields = {
                    'open', 'high', 'low', 'close',
                    'volume', 'amount', 'pct_chg', 'pctChg',
                    'date', 'data_source', 'dataSource', 'source',
                    'realtime_source', 'realtimeSource',
                    'is_partial_bar', 'isPartialBar', 'is_estimated',
                    'isEstimated', 'estimated_fields', 'estimatedFields',
                    'fetched_at', 'fetchedAt', 'provider_timestamp',
                    'providerTimestamp', 'fallback_from', 'fallbackFrom',
                }
                for k, v in orig_today.items():
                    if k not in realtime_today and k not in realtime_owned_fields and v is not None:
                        realtime_today[k] = v
                enhanced['today'] = realtime_today
                enhanced['ma_status'] = self._compute_ma_status(
                    price, trend_result.ma5, trend_result.ma10, trend_result.ma20
                )
                enhanced['date'] = market_today
                if yesterday_close is not None:
                    try:
                        yc = float(yesterday_close)
                        if yc > 0:
                            enhanced['price_change_ratio'] = round(
                                (price - yc) / yc * 100, 2
                            )
                    except (TypeError, ValueError):
                        pass
                if vol is not None and enhanced.get('yesterday'):
                    yest_vol = enhanced['yesterday'].get('volume') if isinstance(
                        enhanced['yesterday'], dict
                    ) else None
                    if yest_vol is not None:
                        try:
                            yv = float(yest_vol)
                            if yv > 0:
                                enhanced['volume_change_ratio'] = round(
                                    float(vol) / yv, 2
                                )
                        except (TypeError, ValueError):
                            pass

        # ETF/index flag for analyzer prompt (Fixes #274)
        enhanced['is_index_etf'] = SearchService.is_index_or_etf(
            context.get('code', ''), enhanced.get('stock_name', stock_name)
        )

        # P0: append unified fundamental block; keep as additional context only
        enhanced["fundamental_context"] = (
            fundamental_context
            if isinstance(fundamental_context, dict)
            else self.fetcher_manager.build_failed_fundamental_context(
                context.get("code", ""),
                "invalid fundamental context",
            )
        )

        return enhanced

    def _attach_belong_boards_to_fundamental_context(
        self,
        code: str,
        fundamental_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Attach A-share board membership as a top-level supplemental field.

        Keep this as a shallow copy so cached fundamental contexts are not
        mutated in place after retrieval.
        """
        if isinstance(fundamental_context, dict):
            enriched_context = dict(fundamental_context)
        else:
            enriched_context = self.fetcher_manager.build_failed_fundamental_context(
                code,
                "invalid fundamental context",
            )

        market = enriched_context.get("market")
        if not isinstance(market, str) or not market.strip():
            market = get_market_for_stock(normalize_stock_code(code))

        existing_boards = enriched_context.get("belong_boards")
        existing_board_list = list(existing_boards) if isinstance(existing_boards, list) else None
        if existing_board_list:
            enriched_context["belong_boards"] = existing_board_list
            self._attach_concept_rankings_to_fundamental_context(code, enriched_context, market)
            return enriched_context

        boards_block = enriched_context.get("boards")
        boards_status = boards_block.get("status") if isinstance(boards_block, dict) else None
        coverage = enriched_context.get("coverage")
        boards_coverage = coverage.get("boards") if isinstance(coverage, dict) else None

        # For HK/US: the offshore adapter already populates belong_boards from
        # yfinance sector/industry. Don't overwrite it (and we have no AkShare
        # sector endpoint for those markets anyway). Default to [] when callers
        # pass a minimal context without the key.
        if market != "cn":
            enriched_context["belong_boards"] = existing_board_list or []
            return enriched_context

        if boards_status == "not_supported" or boards_coverage == "not_supported":
            enriched_context["belong_boards"] = existing_board_list or []
            return enriched_context

        boards: List[Dict[str, Any]] = []
        try:
            raw_boards = self.fetcher_manager.get_belong_boards(code)
            if isinstance(raw_boards, list):
                boards = raw_boards
        except Exception as e:
            logger.debug("%s attach belong_boards failed (fail-open): %s", code, e)

        enriched_context["belong_boards"] = boards or existing_board_list or []
        self._attach_concept_rankings_to_fundamental_context(code, enriched_context, market)
        return enriched_context

    def _attach_concept_rankings_to_fundamental_context(
        self,
        code: str,
        enriched_context: Dict[str, Any],
        market: str,
    ) -> None:
        """Attach concept/theme rankings for A-share related-board signals."""
        if market != "cn" or isinstance(enriched_context.get("concept_boards"), dict):
            return

        top_concepts, bottom_concepts = self._get_concept_rankings_for_market(market)

        if top_concepts or bottom_concepts:
            enriched_context["concept_boards"] = {
                "status": "ok" if top_concepts and bottom_concepts else "partial",
                "data": {
                    "top": top_concepts,
                    "bottom": bottom_concepts,
                },
            }

    def _get_concept_rankings_for_market(
        self,
        market: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetch market-wide concept rankings once per pipeline run."""
        if market != "cn":
            return [], []

        cache = getattr(self, "_concept_rankings_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._concept_rankings_cache = cache

        lock = getattr(self, "_concept_rankings_cache_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._concept_rankings_cache_lock = lock

        with lock:
            if market in cache:
                top_concepts, bottom_concepts = cache[market]
                return list(top_concepts), list(bottom_concepts)

            top_concepts: List[Dict[str, Any]] = []
            bottom_concepts: List[Dict[str, Any]] = []
            try:
                fetch_rankings = getattr(self.fetcher_manager, "get_concept_rankings", None)
                if callable(fetch_rankings):
                    rankings = fetch_rankings(5)
                    if isinstance(rankings, tuple) and len(rankings) == 2:
                        raw_top, raw_bottom = rankings
                        if isinstance(raw_top, list):
                            top_concepts = list(raw_top)
                        if isinstance(raw_bottom, list):
                            bottom_concepts = list(raw_bottom)
            except Exception as e:
                logger.debug("attach concept_rankings failed (fail-open): %s", e)

            cache[market] = (top_concepts, bottom_concepts)
            return list(top_concepts), list(bottom_concepts)

    def _ensure_agent_history(self, code: str, min_days: int = 240) -> None:
        """Ensure at least *min_days* of K-line history is in DB for agent tools."""
        from src.services.history_loader import get_frozen_target_date

        target = get_frozen_target_date()
        if target is None:
            target = self._resolve_resume_target_date(code)
        start = target - timedelta(days=int(min_days * 1.8))
        bars = self.db.get_data_range(code, start, target)
        if bars and len(bars) >= min(min_days, 200):
            logger.debug("[%s] Agent history: %d bars in DB, sufficient", code, len(bars))
            return
        try:
            df, source = self.fetcher_manager.get_daily_data(code, days=min_days)
            if df is not None and not df.empty:
                self.db.save_daily_data(df, code, source)
                logger.info("[%s] Prefetched %d rows of history for agent (source: %s)", code, len(df), source)
        except Exception as e:
            logger.warning("[%s] Agent history prefetch failed: %s", code, e)

    def _analyze_with_agent(
        self,
        code: str,
        report_type: ReportType,
        query_id: str,
        stock_name: str,
        realtime_quote: Any,
        chip_data: Optional[ChipDistribution],
        fundamental_context: Optional[Dict[str, Any]] = None,
        trend_result: Optional[TrendAnalysisResult] = None,
        *,
        market_phase_context: Optional[Dict[str, Any]] = None,
        market_phase_summary: Optional[Dict[str, Any]] = None,
        daily_market_context: Optional[DailyMarketContext] = None,
        portfolio_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[AnalysisResult]:
        """
        \u4f7f\u7528 Agent modeanalyze\u5355stocks.
        """
        try:
            from src.agent.factory import build_agent_executor
            report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))

            requested_skills = (
                self.analysis_skills
                if self.analysis_skills is not None
                else (getattr(self.config, 'agent_skills', None) or None)
            )
            # Build executor from shared factory (ToolRegistry and SkillManager prototype are cached)
            executor = build_agent_executor(self.config, requested_skills)

            # Build initial context to avoid redundant tool calls
            initial_context = {
                "stock_code": code,
                "stock_name": stock_name,
                "report_type": report_type.value,
                "report_language": report_language,
                "fundamental_context": fundamental_context,
            }
            if isinstance(portfolio_context, dict):
                initial_context["portfolio_context"] = dict(portfolio_context)
            if self.analysis_skills is not None:
                initial_context["skills"] = self.analysis_skills
            if market_phase_context is not None:
                initial_context["market_phase_context"] = market_phase_context
            self._attach_daily_market_context(
                initial_context,
                daily_market_context,
                report_language=report_language,
            )

            if realtime_quote:
                initial_context["realtime_quote"] = self._safe_to_dict(realtime_quote)
            if chip_data:
                initial_context["chip_distribution"] = self._safe_to_dict(chip_data)
            if trend_result:
                initial_context["trend_result"] = self._safe_to_dict(trend_result)

            # Agent path: inject social sentiment as news_context so both
            # executor (_build_user_message) and orchestrator (ctx.set_data)
            # can consume it through the existing news_context channel
            if self.social_sentiment_service is not None and self.social_sentiment_service.is_available and is_us_stock_code(code):
                try:
                    social_context = self.social_sentiment_service.get_social_context(code)
                    if social_context:
                        existing = initial_context.get("news_context")
                        if existing:
                            initial_context["news_context"] = existing + "\n\n" + social_context
                        else:
                            initial_context["news_context"] = social_context
                        logger.info(f"[{code}] Agent mode: social sentiment data injected into news_context")
                except Exception as e:
                    logger.warning(f"[{code}] Agent mode: social sentiment fetch failed: {e}")

            persisted_intelligence_context = self._load_persisted_intelligence_context(
                code=code,
                stock_name=stock_name,
                market=get_market_for_stock(normalize_stock_code(code)) or "cn",
            )
            if persisted_intelligence_context:
                existing = initial_context.get("news_context")
                initial_context["news_context"] = (
                    f"{existing}\n\n{persisted_intelligence_context}"
                    if existing
                    else persisted_intelligence_context
                )
                logger.info(f"[{code}] Agent mode: local intelligence evidence injected into news_context")

            # Issue #1066: ensure deep history is in DB before agent tools run
            self._ensure_agent_history(code)

            analysis_context = self._load_agent_analysis_context(code, stock_name)
            market = get_market_for_stock(normalize_stock_code(code))
            (
                analysis_context_pack_summary,
                analysis_context_pack_overview,
            ) = self._build_analysis_context_pack_outputs(
                self._build_agent_analysis_artifacts(
                    code=code,
                    stock_name=stock_name,
                    market=market,
                    phase=market_phase_context,
                    initial_context=initial_context,
                    fundamental_context=fundamental_context,
                    query_id=query_id,
                    base_context=analysis_context,
                    portfolio_context=portfolio_context,
                ),
                report_language=report_language,
                code=code,
                query_id=query_id,
            )
            if analysis_context_pack_summary:
                initial_context["analysis_context_pack_summary"] = analysis_context_pack_summary

            # \u8fd0\u884c Agent
            if report_language in ("en", "ko"):
                message = f"Analyze stock {code} ({stock_name}) and return the full decision dashboard JSON."
            else:
                message = f"\u8bf7analyze stock {code} ({stock_name}); \u5e76\u751f\u6210\u51b3\u7b56\u4eea\u8868\u76d8report."
            llm_started_at = time.monotonic()
            try:
                record_llm_run_started(
                    model=getattr(self.config, "agent_litellm_model", None),
                    call_type="agent_analysis",
                )
                agent_result = executor.run(message, context=initial_context)
            except Exception as exc:
                record_llm_run(
                    success=False,
                    model=getattr(self.config, "agent_litellm_model", None),
                    call_type="agent_analysis",
                    duration_ms=int((time.monotonic() - llm_started_at) * 1000),
                    error_type=type(exc).__name__,
                    error_message=exc,
                )
                raise

            # \u8f6c\u6362\u4e3a AnalysisResult
            result = self._agent_result_to_analysis_result(
                agent_result,
                code,
                stock_name,
                report_type,
                query_id,
                trend_result=trend_result,
            )
            record_llm_run(
                success=bool(result and getattr(result, "success", True)),
                model=getattr(result, "model_used", None) if result else getattr(agent_result, "model", None),
                call_type="agent_analysis",
                duration_ms=int((time.monotonic() - llm_started_at) * 1000),
                error_type=(
                    None
                    if result and getattr(result, "success", True)
                    else "AgentResultError"
                ),
                error_message=(
                    getattr(result, "error_message", None)
                    if result and not getattr(result, "success", True)
                    else ("Agent returned empty result" if result is None else None)
                ),
            )
            if result:
                result.query_id = query_id
            # Agent weak integrity: placeholder fill only, no LLM retry
            if result and getattr(self.config, "report_integrity_enabled", False):
                from src.analyzer import check_content_integrity, apply_placeholder_fill

                pass_integrity, missing = check_content_integrity(
                    result,
                    require_phase_decision=isinstance(market_phase_summary, dict),
                )
                if not pass_integrity:
                    apply_placeholder_fill(result, missing)
                    logger.info(
                        "[LLM\u5b8c\u6574] integrity_mode=agent_weak required\u5b57\u6bb5\u7f3a\u5931 %s; \u5df2\u5360characters\u8865\u5168",
                        missing,
                    )
            # chip_structure fallback (Issue #589), before save_analysis_history
            if result and chip_data is not None:
                normalize_chip_structure_availability(result, chip_data)

            # price_position fallback (same as non-agent path Step 7.7)
            if result:
                fill_price_position_if_needed(result, trend_result, realtime_quote)
                realtime_data = initial_context.get("realtime_quote", {})
                if isinstance(realtime_data, dict):
                    result.current_price = realtime_data.get("price")
                    result.change_pct = realtime_data.get("change_pct")
                action_source_advice = getattr(result, "operation_advice", None)
                stabilize_decision_with_structure(result, trend_result, fundamental_context)
                adjustments = apply_phase_decision_guardrails(
                    result,
                    market_phase_summary=market_phase_summary,
                    analysis_context_pack_overview=analysis_context_pack_overview,
                    report_language=getattr(result, "report_language", None)
                    or getattr(self.config, "report_language", "zh"),
                )
                if adjustments:
                    logger.info("[phase_decision_guardrail] Applied agent adjustments for %s: %s", code, adjustments)
                market_context_adjustments = apply_daily_market_context_guardrail(
                    result,
                    daily_market_context=initial_context.get("daily_market_context"),
                    report_language=getattr(result, "report_language", None)
                    or getattr(self.config, "report_language", "zh"),
                )
                if market_context_adjustments:
                    logger.info(
                        "[daily_market_context_guardrail] Applied agent adjustments for %s: %s",
                        code,
                        market_context_adjustments,
                    )
                if isinstance(fundamental_context, dict):
                    result.fundamental_context = fundamental_context
                result.market_phase_summary = market_phase_summary
                result.analysis_context_pack_overview = analysis_context_pack_overview
                self._refresh_decision_action_for_final_result(
                    result,
                    report_type=report_type.value,
                    previous_operation_advice=action_source_advice,
                )

            resolved_stock_name = result.name if result and result.name else stock_name

            # \u4fdd\u5b58news\u60c5\u62a5\u5230\u6570\u636elibrary (Agent \u5de5\u5177result\u4ec5\u7528\u4e8e LLM \u4e0a\u4e0b\u6587; \u672a\u6301\u4e45\u5316; Fixes #396)
            # \u4f7f\u7528 search_stock_news (\u4e0e Agent \u5de5\u5177\u8c03\u7528\u903b\u8f91\u4e00\u81f4); \u4ec5 1 \u6b21 API \u8c03\u7528; \u65e0\u989d\u5916\u5ef6\u8fdf
            if self.search_service is not None and self.search_service.is_available:
                try:
                    news_response = self.search_service.search_stock_news(
                        stock_code=code,
                        stock_name=resolved_stock_name,
                        max_results=5
                    )
                    if news_response.success and news_response.results:
                        query_context = self._build_query_context(query_id=query_id)
                        self.db.save_news_intel(
                            code=code,
                            name=resolved_stock_name,
                            dimension="latest_news",
                            query=news_response.query,
                            response=news_response,
                            query_context=query_context
                        )
                        logger.info(f"[{code}] Agent mode: news\u60c5\u62a5\u5df2\u4fdd\u5b58 {len(news_response.results)} \u6761")
                except Exception as e:
                    logger.warning(f"[{code}] Agent mode\u4fdd\u5b58news\u60c5\u62a5failed: {e}")

            # \u4fdd\u5b58analyzehistory records
            if result and result.success:
                try:
                    agent_context_snapshot = self._build_context_snapshot(
                        enhanced_context={
                            **self._without_runtime_prompt_context(initial_context),
                            "stock_name": resolved_stock_name,
                        },
                        news_content=initial_context.get("news_context"),
                        realtime_quote=realtime_quote,
                        chip_data=chip_data,
                        analysis_context_pack_overview=analysis_context_pack_overview,
                        market_phase_summary=market_phase_summary,
                    )
                    result.diagnostic_context_snapshot = agent_context_snapshot
                    agent_context_snapshot["stock_name"] = resolved_stock_name
                    saved_history_id = self.db.save_analysis_history(
                        result=result,
                        query_id=query_id,
                        report_type=report_type.value,
                        news_content=None,
                        context_snapshot=agent_context_snapshot,
                        save_snapshot=self.save_context_snapshot,
                    )
                    valid_saved_history_id = (
                        isinstance(saved_history_id, int)
                        and not isinstance(saved_history_id, bool)
                        and saved_history_id > 0
                    )
                    record_history_run(
                        report_saved=bool(saved_history_id),
                        metadata_saved=bool(saved_history_id),
                        analysis_history_id=(
                            saved_history_id if valid_saved_history_id else None
                        ),
                    )
                    if valid_saved_history_id:
                        self._extract_decision_signal_after_history_save(
                            result=result,
                            query_id=query_id,
                            source_report_id=saved_history_id,
                            report_type=report_type.value,
                            context_snapshot=agent_context_snapshot,
                            portfolio_context=portfolio_context,
                        )
                    latest_diagnostic_snapshot = current_diagnostic_snapshot()
                    if latest_diagnostic_snapshot is not None:
                        agent_context_snapshot["diagnostics"] = latest_diagnostic_snapshot
                        result.diagnostic_context_snapshot = agent_context_snapshot
                except Exception as e:
                    record_history_run(
                        report_saved=False,
                        metadata_saved=False,
                        error_message=e,
                    )
                    logger.warning(f"[{code}] \u4fdd\u5b58 Agent analyzehistoryfailed: {e}")

            return result

        except Exception as e:
            logger.error(f"[{code}] Agent analyzefailed: {e}")
            logger.exception(f"[{code}] Agent \u8be6\u7ec6errorinfo:")
            return None

    def _load_agent_analysis_context(self, code: str, stock_name: str) -> Dict[str, Any]:
        """Load daily-bar context for Agent pack summaries without blocking analysis."""
        try:
            context = self._get_analysis_context_with_market_fallback(code)
        except Exception as exc:
            logger.warning(
                "[%s] Agent analysis context load failed; daily_bars will be marked missing: %s",
                code,
                exc,
            )
            context = None

        if isinstance(context, dict) and context:
            enriched = dict(context)
            enriched.setdefault("code", code)
            if stock_name:
                enriched.setdefault("stock_name", stock_name)
            return enriched

        return {
            "code": code,
            "stock_name": stock_name,
            "data_missing": True,
            "today": {},
            "yesterday": {},
        }

    def _get_analysis_context_with_market_fallback(self, code: str) -> Optional[Dict[str, Any]]:
        """Load analysis context, fetching JP/KR/TW daily bars when DB has no context."""
        context = self.db.get_analysis_context(code)
        if isinstance(context, dict) and context:
            return context

        market = get_market_for_stock(normalize_stock_code(code))
        if market not in {"jp", "kr", "tw"}:
            return context

        try:
            df, source_name = self.fetcher_manager.get_daily_data(code, days=60)
        except Exception as exc:
            logger.warning("[%s] JP/KR daily fallback fetch failed: %s", code, exc)
            return context

        if df is None or df.empty:
            logger.warning("[%s] JP/KR daily fallback returned empty data", code)
            return context

        try:
            self.db.save_daily_data(df, code, source_name)
            refreshed = self.db.get_analysis_context(code)
            if isinstance(refreshed, dict) and refreshed:
                return refreshed
        except Exception as exc:
            logger.warning("[%s] JP/KR daily fallback persistence failed: %s", code, exc)

        return self._build_analysis_context_from_daily_df(code, df)

    def _build_analysis_context_from_daily_df(self, code: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if df is None or df.empty:
            return None

        frame = df.copy()
        frame.columns = [str(column).lower() for column in frame.columns]
        if "date" in frame.columns:
            frame = frame.sort_values("date")
        frame = frame.tail(2)
        rows = frame.to_dict(orient="records")
        if not rows:
            return None

        def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
            normalized: Dict[str, Any] = {"code": row.get("code") or code}
            for key in ("open", "high", "low", "close", "volume", "amount", "pct_chg", "ma5", "ma10", "ma20", "volume_ratio"):
                value = row.get(key)
                if pd.notna(value):
                    normalized[key] = float(value)
            row_date = row.get("date")
            if hasattr(row_date, "date"):
                row_date = row_date.date()
            normalized["date"] = row_date.isoformat() if hasattr(row_date, "isoformat") else str(row_date)
            return normalized

        today = normalize_row(rows[-1])
        context: Dict[str, Any] = {
            "code": code,
            "date": today.get("date"),
            "today": today,
        }
        if len(rows) > 1:
            yesterday = normalize_row(rows[-2])
            context["yesterday"] = yesterday
            yesterday_volume = yesterday.get("volume")
            if yesterday_volume:
                context["volume_change_ratio"] = round(float(today.get("volume", 0)) / float(yesterday_volume), 2)
            yesterday_close = yesterday.get("close")
            if yesterday_close:
                context["price_change_ratio"] = round(
                    (float(today.get("close", 0)) - float(yesterday_close)) / float(yesterday_close) * 100,
                    2,
                )
            context["ma_status"] = self.db._analyze_ma_status(SimpleNamespace(**today))

        return context

    def _load_daily_market_context(
        self,
        market: str,
        *,
        force_refresh: bool = False,
        target_date: Optional[date] = None,
    ) -> Optional[DailyMarketContext]:
        """Load/generate today's market context when market review is explicitly enabled."""
        if getattr(self, "daily_market_context_enabled", True) is not True:
            return None
        if getattr(self.config, "daily_market_context_enabled", True) is not True:
            return None
        if getattr(self.config, "market_review_enabled", None) is not True:
            return None

        try:
            service = getattr(self, "_daily_market_context_service", None)
            if service is None:
                service_lock = self._get_daily_market_context_service_lock()
                with service_lock:
                    service = getattr(self, "_daily_market_context_service", None)
                    if service is None:
                        service = DailyMarketContextService(db_manager=self.db)
                        self._daily_market_context_service = service
            get_context_kwargs = {
                "region": market,
                "config": self.config,
                "notifier": self.notifier,
                "analyzer": self.analyzer,
                "search_service": self.search_service,
                "force_refresh": force_refresh,
                "allow_generate": getattr(self, "daily_market_context_allow_generate", True),
                "target_date": target_date,
            }
            current_query_id = getattr(self, "query_id", None)
            if isinstance(current_query_id, str) and current_query_id.strip():
                get_context_kwargs["current_query_id"] = current_query_id
            return service.get_context(**get_context_kwargs)
        except Exception as exc:
            logger.warning("load\u5927\u76d8\u73af\u5883\u4e0a\u4e0b\u6587failed; individual stocksanalyze\u7ee7\u7eed: %s", exc, exc_info=True)
            return None

    def _get_daily_market_context_service_lock(self) -> threading.Lock:
        service_lock = getattr(self, "_daily_market_context_service_lock", None)
        if service_lock is not None:
            return service_lock
        with _DAILY_MARKET_CONTEXT_SERVICE_LOCK_INIT_GUARD:
            service_lock = getattr(self, "_daily_market_context_service_lock", None)
            if service_lock is None:
                service_lock = threading.Lock()
                self._daily_market_context_service_lock = service_lock
            return service_lock

    @staticmethod
    def _coerce_daily_market_context_date(value: Any) -> Optional[date]:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _attach_daily_market_context(
        target_context: Dict[str, Any],
        daily_market_context: Optional[DailyMarketContext],
        *,
        report_language: str,
    ) -> None:
        """Attach only the safe daily market summary to runtime analysis context."""
        if daily_market_context is None:
            return
        safe_context = daily_market_context.to_safe_dict()
        prompt_section = format_daily_market_context_prompt_section(
            safe_context,
            report_language=report_language,
        )
        if not prompt_section:
            return
        target_context["daily_market_context"] = safe_context
        target_context["daily_market_context_summary"] = prompt_section

    def _agent_result_to_analysis_result(
        self,
        agent_result,
        code: str,
        stock_name: str,
        report_type: ReportType,
        query_id: str,
        trend_result: Optional[TrendAnalysisResult] = None,
    ) -> AnalysisResult:
        """
        \u5c06 AgentResult \u8f6c\u6362\u4e3a AnalysisResult.
        """
        report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))
        dash = None
        result = AnalysisResult(
            code=code,
            name=stock_name,
            sentiment_score=50,
            trend_prediction=get_unknown_text(report_language),
            operation_advice=localize_operation_advice("Watch", report_language),
            confidence_level=localize_confidence_level("medium", report_language),
            report_language=report_language,
            success=agent_result.success,
            error_message=agent_result.error or None,
            data_sources=f"agent:{agent_result.provider}",
            model_used=agent_result.model or None,
        )

        if agent_result.success and agent_result.dashboard:
            dash = agent_result.dashboard
            ai_stock_name = str(dash.get("stock_name", "")).strip()
            if ai_stock_name and self._is_placeholder_stock_name(stock_name, code):
                result.name = ai_stock_name

            nested_dashboard = dash.get("dashboard") if isinstance(dash, dict) else None

            raw_score = self._agent_dashboard_value(
                dash,
                nested_dashboard,
                "sentiment_score",
                scalar=True,
            )
            if self._is_agent_field_missing(raw_score, scalar=True):
                fallback_score = self._trend_score_fallback(trend_result)
                if fallback_score is not None:
                    result.sentiment_score = fallback_score
                    self._mark_trend_fallback_source(result)
            else:
                result.sentiment_score = self._safe_int(raw_score, 50)

            raw_trend = self._agent_dashboard_value(
                dash,
                nested_dashboard,
                "trend_prediction",
                scalar=True,
                expect_text=True,
            )
            if self._is_agent_field_missing(raw_trend, scalar=True, expect_text=True):
                trend_label = self._trend_label_fallback(
                    trend_result,
                    report_language,
                )
                if trend_label:
                    result.trend_prediction = trend_label
                    self._mark_trend_fallback_source(result)
            else:
                result.trend_prediction = str(raw_trend)

            raw_advice = self._agent_dashboard_value(
                dash,
                nested_dashboard,
                "operation_advice",
                scalar=True,
                allow_dict=True,
                expect_text=True,
            )
            extracted_advice = ""
            if isinstance(raw_advice, dict):
                # LLM may return {"no_position": "...", "has_position": "..."}
                extracted_advice = self._extract_advice_text_from_dict(raw_advice)
                if extracted_advice:
                    result.operation_advice = localize_operation_advice(
                        extracted_advice,
                        report_language,
                    )
                else:
                    signal_label = self._trend_signal_fallback(
                        trend_result,
                        report_language,
                    )
                    if signal_label:
                        result.operation_advice = signal_label
                        self._mark_trend_fallback_source(result)
            elif not self._is_agent_field_missing(
                raw_advice,
                scalar=True,
                allow_dict=True,
                expect_text=True,
            ):
                result.operation_advice = str(raw_advice) if raw_advice else (localize_operation_advice("Watch", report_language))
            else:
                signal_label = self._trend_signal_fallback(trend_result, report_language)
                if signal_label:
                    result.operation_advice = signal_label
                    self._mark_trend_fallback_source(result)
            from src.agent.protocols import normalize_decision_signal

            raw_decision = self._agent_dashboard_value(
                dash,
                nested_dashboard,
                "decision_type",
                scalar=True,
                expect_text=True,
            )
            if self._is_agent_field_missing(raw_decision, scalar=True, expect_text=True):
                trend_decision = self._trend_decision_fallback(trend_result)
                decision_from_advice = infer_decision_type_from_advice(
                    result.operation_advice,
                    default="",
                )
                if decision_from_advice:
                    result.decision_type = decision_from_advice
                    if (
                        self._is_agent_field_missing(
                            raw_advice,
                            scalar=True,
                            allow_dict=True,
                            expect_text=True,
                        )
                        and not extracted_advice
                        and trend_decision
                    ):
                        self._mark_trend_fallback_source(result)
                else:
                    result.decision_type = trend_decision or "hold"
                    if trend_decision:
                        self._mark_trend_fallback_source(result)
            else:
                result.decision_type = normalize_decision_signal(raw_decision)
            result.confidence_level = localize_confidence_level(
                self._agent_dashboard_value(dash, nested_dashboard, "confidence_level")
                or result.confidence_level,
                report_language,
            )
            raw_summary = self._agent_dashboard_value(
                dash,
                nested_dashboard,
                "analysis_summary",
                scalar=True,
                expect_text=True,
            )
            if not self._is_agent_field_missing(raw_summary, scalar=True, expect_text=True):
                result.analysis_summary = str(raw_summary)
            else:
                result.analysis_summary = self._summary_fallback_from_result(result, report_language)
            top_level_phase_decision = dash.get("phase_decision") if isinstance(dash, dict) else None
            if isinstance(nested_dashboard, dict) and isinstance(top_level_phase_decision, dict):
                nested_dashboard = dict(nested_dashboard)
                nested_dashboard.setdefault("phase_decision", top_level_phase_decision)

            # The AI returns a top-level dict that contains a nested 'dashboard' sub-key
            # with core_conclusion / battle_plan / intelligence.  AnalysisResult's helper
            # methods (get_sniper_points, get_core_conclusion, etc.) expect that inner
            # structure, so we unwrap it here.
            result.dashboard = nested_dashboard or dash
            self._backfill_agent_dashboard_fields(result, trend_result, report_language)
        else:
            self._apply_trend_fallback(result, trend_result, report_language)
            if trend_result is not None:
                result.analysis_summary = (
                    result.analysis_summary
                    or self._summary_fallback_from_result(result, report_language)
                )
                self._backfill_agent_dashboard_fields(result, trend_result, report_language)
            if not result.error_message:
                result.error_message = (
                    "Agent failed to generate a valid decision dashboard" if report_language == "en"
                    else "에이전트가 유효한 결정 대시보드를 생성하지 못했습니다" if report_language == "ko"
                    else "Agent \u672a\u80fd\u751f\u6210\u6709\u6548\u7684\u51b3\u7b56\u4eea\u8868\u76d8"
                )

        explicit_action = dash.get("action") if isinstance(dash, dict) else None
        if explicit_action is None and isinstance(getattr(result, "dashboard", None), dict):
            explicit_action = result.dashboard.get("action")
        return populate_decision_action_fields(result, explicit_action=explicit_action)

    @staticmethod
    def _refresh_decision_action_for_final_result(
        result: AnalysisResult,
        *,
        report_type: Any,
        previous_operation_advice: Any,
    ) -> AnalysisResult:
        previous_advice = str(previous_operation_advice or "").strip()
        current_advice = str(getattr(result, "operation_advice", None) or "").strip()
        explicit_action = current_advice if previous_advice != current_advice else None
        return populate_decision_action_fields(
            result,
            explicit_action=explicit_action,
            report_type=report_type,
            use_existing_action=(previous_advice == current_advice),
            align_with_score=(previous_advice == current_advice),
        )

    @staticmethod
    def _agent_dashboard_value(
        dash: Dict[str, Any],
        nested_dashboard: Any,
        key: str,
        *,
        scalar: bool = False,
        allow_dict: bool = False,
        expect_text: bool = False,
    ) -> Any:
        """Read a scalar from top-level agent payload, then nested dashboard fallback."""
        value = dash.get(key) if isinstance(dash, dict) else None
        if isinstance(nested_dashboard, dict) and StockAnalysisPipeline._is_agent_field_missing(
            value,
            scalar=scalar,
            allow_dict=allow_dict,
            expect_text=expect_text,
        ):
            nested_value = nested_dashboard.get(key)
            if not StockAnalysisPipeline._is_agent_field_missing(
                nested_value,
                scalar=scalar,
                allow_dict=allow_dict,
                expect_text=expect_text,
            ):
                value = nested_value
        return value

    @staticmethod
    def _extract_advice_text_from_dict(raw_advice: dict) -> str:
        for field in ("has_position", "no_position"):
            if isinstance(raw_advice.get(field), str):
                text = raw_advice[field].strip()
                if not StockAnalysisPipeline._is_agent_placeholder_text(text):
                    return text

        for value in raw_advice.values():
            if isinstance(value, str):
                text = value.strip()
                if not StockAnalysisPipeline._is_agent_placeholder_text(text):
                    return text

        return ""

    @staticmethod
    def _is_agent_placeholder_text(text: str) -> bool:
        if not text:
            return True
        return text.lower() in {"n/a", "na", "none", "null", "unknown", "tbd"} or text in {
            "unknown",
            "\u5f85\u8865\u5145",
            "\u6570\u636e\u7f3a\u5931",
            "\u65e0",
        }

    @staticmethod
    def _is_agent_field_missing(
        value: Any,
        *,
        scalar: bool = False,
        allow_dict: bool = False,
        expect_text: bool = False,
    ) -> bool:
        if scalar and isinstance(value, dict):
            if not allow_dict or not value:
                return True
            return not StockAnalysisPipeline._extract_advice_text_from_dict(value)
        if value is None:
            return True
        if expect_text and scalar:
            if not isinstance(value, str):
                return True
        if isinstance(value, str):
            text = value.strip()
            return StockAnalysisPipeline._is_agent_placeholder_text(text)
        if isinstance(value, dict):
            if scalar:
                return not allow_dict
            return not value
        if scalar and isinstance(value, (list, tuple, set)):
            return True
        return False

    @staticmethod
    def _trend_score_fallback(trend_result: Optional[TrendAnalysisResult]) -> Optional[int]:
        if trend_result is None:
            return None
        try:
            score = int(getattr(trend_result, "signal_score", 0))
        except (TypeError, ValueError):
            return None
        return score if score > 0 else None

    @staticmethod
    def _trend_label_fallback(
        trend_result: Optional[TrendAnalysisResult],
        report_language: str = "zh",
    ) -> str:
        if trend_result is None:
            return ""
        trend_status = getattr(trend_result, "trend_status", None)
        value = getattr(trend_status, "value", None) or str(trend_status or "").strip()
        if report_language != "en":
            return value
        return localize_trend_prediction(value, report_language)

    @staticmethod
    def _trend_signal_fallback(
        trend_result: Optional[TrendAnalysisResult],
        report_language: str = "zh",
    ) -> str:
        if trend_result is None:
            return ""
        buy_signal = getattr(trend_result, "buy_signal", None)
        value = getattr(buy_signal, "value", None) or str(buy_signal or "").strip()
        return localize_operation_advice(value, report_language)

    @staticmethod
    def _trend_decision_fallback(trend_result: Optional[TrendAnalysisResult]) -> Optional[str]:
        if trend_result is None:
            return None
        signal_name = getattr(getattr(trend_result, "buy_signal", None), "name", "").lower()
        return {
            "strong_buy": "buy",
            "buy": "buy",
            "hold": "hold",
            "wait": "hold",
            "sell": "sell",
            "strong_sell": "sell",
        }.get(signal_name)

    @staticmethod
    def _mark_trend_fallback_source(result: AnalysisResult) -> None:
        if "trend:fallback" in (result.data_sources or ""):
            return
        result.data_sources = (
            f"{result.data_sources},trend:fallback"
            if result.data_sources
            else "trend:fallback"
        )

    @staticmethod
    def _summary_fallback_from_result(result: AnalysisResult, report_language: str) -> str:
        trend = (result.trend_prediction or "").strip()
        advice = (result.operation_advice or "").strip()
        if trend and advice:
            if report_language == "en":
                return f"Trend view: {trend}; action advice: {advice}."
            if report_language == "ko":
                return f"추세 결론: {trend}; 대응 전략: {advice}."
            return f"\u8d8b\u52bf\u7ed3\u8bba: {trend}；operation advice: {advice}."
        return ""

    def _backfill_agent_dashboard_fields(
        self,
        result: AnalysisResult,
        trend_result: Optional[TrendAnalysisResult],
        report_language: str,
    ) -> None:
        if not isinstance(result.dashboard, dict):
            result.dashboard = {}
        dashboard = result.dashboard

        for key in (
            "sentiment_score",
            "trend_prediction",
            "operation_advice",
            "decision_type",
            "confidence_level",
            "analysis_summary",
        ):
            current = dashboard.get(key)
            if key == "sentiment_score":
                if self._is_agent_field_missing(current, scalar=True):
                    dashboard[key] = getattr(result, key)
            elif self._is_agent_field_missing(current, scalar=True, expect_text=True):
                dashboard[key] = getattr(result, key)

        core = dashboard.get("core_conclusion")
        if not isinstance(core, dict):
            core = {}
            dashboard["core_conclusion"] = core
        if self._is_agent_field_missing(core.get("one_sentence"), scalar=True):
            core["one_sentence"] = result.analysis_summary or self._summary_fallback_from_result(
                result,
                report_language,
            ) or (
                "Analysis pending" if report_language == "en"
                else "분석 보완 예정" if report_language == "ko"
                else "analyze\u5f85\u8865\u5145"
            )

        intelligence = dashboard.get("intelligence")
        if not isinstance(intelligence, dict):
            intelligence = {}
            dashboard["intelligence"] = intelligence
        risk_alerts = intelligence.get("risk_alerts")
        if (
            "risk_alerts" not in intelligence
            or self._is_agent_field_missing(risk_alerts)
            or not isinstance(risk_alerts, list)
        ):
            risk_factors = getattr(trend_result, "risk_factors", None) or []
            intelligence["risk_alerts"] = list(risk_factors)

        if result.decision_type in ("buy", "hold"):
            battle = dashboard.get("battle_plan")
            if not isinstance(battle, dict):
                battle = {}
                dashboard["battle_plan"] = battle
            sniper_points = battle.get("sniper_points")
            if not isinstance(sniper_points, dict):
                sniper_points = {}
                battle["sniper_points"] = sniper_points
            if self._is_agent_field_missing(sniper_points.get("stop_loss"), scalar=True):
                sniper_points["stop_loss"] = self._stop_loss_fallback_from_trend(
                    trend_result,
                    report_language,
                )

    @staticmethod
    def _stop_loss_fallback_from_trend(
        trend_result: Optional[TrendAnalysisResult],
        report_language: str,
    ) -> Any:
        levels = getattr(trend_result, "support_levels", None) if trend_result else None
        if levels:
            return levels[0]
        return get_placeholder_text(report_language)

    @staticmethod
    def _apply_trend_fallback(
        result: AnalysisResult,
        trend_result: Optional[TrendAnalysisResult],
        report_language: str,
    ) -> None:
        if trend_result is None:
            result.sentiment_score = 50
            result.operation_advice = localize_operation_advice("Watch", report_language)
            return

        score = getattr(trend_result, "signal_score", None)
        try:
            numeric_score = int(score)
        except (TypeError, ValueError):
            numeric_score = 50
        result.sentiment_score = numeric_score if numeric_score > 0 else 50

        trend_label = StockAnalysisPipeline._trend_label_fallback(trend_result, report_language)
        if trend_label:
            result.trend_prediction = trend_label

        buy_signal = getattr(trend_result, "buy_signal", None)
        signal_label = StockAnalysisPipeline._trend_signal_fallback(
            trend_result,
            report_language,
        )
        if signal_label:
            result.operation_advice = signal_label
        else:
            result.operation_advice = localize_operation_advice("Watch", report_language)

        from src.agent.protocols import normalize_decision_signal

        signal_name = getattr(buy_signal, "name", "").lower()
        signal_to_decision = {
            "strong_buy": "buy",
            "buy": "buy",
            "hold": "hold",
            "wait": "hold",
            "sell": "sell",
            "strong_sell": "sell",
        }
        result.decision_type = signal_to_decision.get(signal_name, result.decision_type or "hold")
        result.decision_type = normalize_decision_signal(result.decision_type)
        result.data_sources = f"{result.data_sources},trend:fallback" if result.data_sources else "trend:fallback"

    @staticmethod
    def _is_placeholder_stock_name(name: str, code: str) -> bool:
        """Return True when the stock name is missing or placeholder-like."""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized == code:
            return True
        if normalized.startswith("\u80a1\u7968"):
            return True
        if "Unknown" in normalized:
            return True
        return False

    @staticmethod
    def _safe_int(value: Any, default: int = 50) -> int:
        """\u5b89\u5168\u5730\u5c06\u503c\u8f6c\u6362\u4e3a\u6574\u6570."""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            import re
            match = re.search(r'-?\d+', value)
            if match:
                return int(match.group())
        return default

    def _describe_volume_ratio(self, volume_ratio: float) -> str:
        """
        \u91cf\u6bd4\u63cf\u8ff0

        \u91cf\u6bd4 = \u5f53\u524dvolume / \u8fc7\u53bb5\u65e5\u5e73\u5747volume
        """
        if volume_ratio < 0.5:
            return "\u6781\u5ea6\u840e\u7f29"
        elif volume_ratio < 0.8:
            return "\u660e\u663e\u840e\u7f29"
        elif volume_ratio < 1.2:
            return "\u6b63\u5e38"
        elif volume_ratio < 2.0:
            return "\u6e29\u548c\u653e\u91cf"
        elif volume_ratio < 3.0:
            return "\u660e\u663e\u653e\u91cf"
        else:
            return "\u5de8\u91cf"

    @staticmethod
    def _compute_ma_status(close: float, ma5: float, ma10: float, ma20: float) -> str:
        """
        Compute MA alignment status from price and MA values.
        Logic mirrors storage._analyze_ma_status (Issue #234).
        """
        close = close or 0
        ma5 = ma5 or 0
        ma10 = ma10 or 0
        ma20 = ma20 or 0
        if close > ma5 > ma10 > ma20 > 0:
            return "\u591a\u5934\u6392\u5217 📈"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "\u7a7a\u5934\u6392\u5217 📉"
        elif close > ma5 and ma5 > ma10:
            return "\u77ed\u671f\u5411\u597d 🔼"
        elif close < ma5 and ma5 < ma10:
            return "\u77ed\u671f\u8d70\u5f31 🔽"
        else:
            return "\u9707\u8361\u6574\u7406 ↔️"

    def _augment_historical_with_realtime(
        self, df: pd.DataFrame, realtime_quote: Any, code: str
    ) -> pd.DataFrame:
        """
        \u4f7f\u7528\u5f53\u65e5realtime quote\u8865\u9f50history OHLCV; \u7528\u4e8e\u76d8Medium MA \u8ba1\u7b97.
        Issue #234: technical indicators\u4f7f\u7528\u5b9e\u65f6price; \u800c\u4e0d\u662f\u6cbf\u7528\u6628\u65e5\u6536\u76d8\u4ef7.
        """
        if df is None or df.empty or 'close' not in df.columns:
            return df
        if realtime_quote is None:
            return df
        price = getattr(realtime_quote, 'price', None)
        if price is None or not (isinstance(price, (int, float)) and price > 0):
            return df

        # \u975e\u4ea4\u6613\u65e5\u53efskipping\u5b9e\u65f6\u8865\u9f50；\u5f02\u5e38\u60c5\u51b5\u4e0b\u4fdd\u6301failed\u5f00\u653e.
        enable_realtime_tech = getattr(
            self.config, 'enable_realtime_technical_indicators', True
        )
        if not enable_realtime_tech:
            return df
        market = get_market_for_stock(code)
        market_today = get_market_now(market).date()
        if market and not is_market_open(market, market_today):
            return df

        last_val = df['date'].max()
        last_date = (
            last_val.date() if hasattr(last_val, 'date') else
            (last_val if isinstance(last_val, date) else pd.Timestamp(last_val).date())
        )
        yesterday_close = float(df.iloc[-1]['close']) if len(df) > 0 else price
        open_p = getattr(realtime_quote, 'open_price', None) or getattr(
            realtime_quote, 'pre_close', None
        ) or yesterday_close
        high_p = getattr(realtime_quote, 'high', None) or price
        low_p = getattr(realtime_quote, 'low', None) or price
        vol = getattr(realtime_quote, 'volume', None) or 0
        amt = getattr(realtime_quote, 'amount', None)
        pct = getattr(realtime_quote, 'change_pct', None)

        if last_date >= market_today:
            # \u4f7f\u7528\u5b9e\u65f6\u6536\u76d8\u4ef7\u66f4\u65b0\u6700\u540e\u4e00\u884c；\u5148\u590d\u5236; \u907f\u514d\u4fee\u6539\u8c03\u7528\u65b9\u4f20\u5165\u7684 df.
            df = df.copy()
            idx = df.index[-1]
            df.loc[idx, 'close'] = price
            if open_p is not None:
                df.loc[idx, 'open'] = open_p
            if high_p is not None:
                df.loc[idx, 'high'] = high_p
            if low_p is not None:
                df.loc[idx, 'low'] = low_p
            if vol:
                df.loc[idx, 'volume'] = vol
            if amt is not None:
                df.loc[idx, 'amount'] = amt
            if pct is not None:
                df.loc[idx, 'pct_chg'] = pct
        else:
            # \u8ffd\u52a0\u4e00\u884c\u865a\u62df\u7684\u5f53\u65e5\u5b9e\u65f6 K \u7ebf.
            new_row = {
                'code': code,
                'date': market_today,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': price,
                'volume': vol,
                'amount': amt if amt is not None else 0,
                'pct_chg': pct if pct is not None else 0,
            }
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
        return df

    def _build_context_snapshot(
        self,
        enhanced_context: Dict[str, Any],
        news_content: Optional[str],
        realtime_quote: Any,
        chip_data: Optional[ChipDistribution],
        news_result_count: Optional[int] = None,
        analysis_context_pack_overview: Optional[Dict[str, Any]] = None,
        market_phase_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        \u6784\u5efaanalyze\u4e0a\u4e0b\u6587\u5feb\u7167
        """
        snapshot = {
            "enhanced_context": self._without_runtime_prompt_context(enhanced_context),
            "news_content": news_content,
            "realtime_quote_raw": self._safe_to_dict(realtime_quote),
            "chip_distribution_raw": self._safe_to_dict(chip_data),
        }
        if news_content is not None:
            snapshot["news_retrieval_content"] = news_content
        if news_result_count is not None:
            snapshot["news_result_count"] = news_result_count
        if analysis_context_pack_overview is not None:
            snapshot["analysis_context_pack_overview"] = analysis_context_pack_overview
        if market_phase_summary is not None:
            snapshot[MARKET_PHASE_SUMMARY_KEY] = market_phase_summary
        diagnostic_snapshot = current_diagnostic_snapshot()
        if diagnostic_snapshot is not None:
            snapshot["diagnostics"] = diagnostic_snapshot
        if self.analysis_skills is not None:
            snapshot["skills"] = list(self.analysis_skills)
        return snapshot

    def _extract_decision_signal_after_history_save(
        self,
        *,
        result: AnalysisResult,
        query_id: str,
        source_report_id: int,
        report_type: str,
        context_snapshot: Dict[str, Any],
        portfolio_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort DecisionSignal extraction after analysis history is saved."""

        assert (
            isinstance(source_report_id, int)
            and not isinstance(source_report_id, bool)
            and source_report_id > 0
        )

        try:
            diagnostic_context = get_current_diagnostic_context()
            trace_id = (
                getattr(diagnostic_context, "trace_id", None)
                or getattr(self, "trace_id", None)
                or query_id
            )
            signal_result = extract_and_persist_from_analysis_result(
                result,
                context_snapshot=context_snapshot,
                source_report_id=source_report_id,
                trace_id=str(trace_id),
                query_source=getattr(self, "query_source", None) or "system",
                report_type=report_type,
                portfolio_context=portfolio_context,
                profile_source="auto_default",
            )
            if isinstance(signal_result, dict):
                summary = summarize_decision_signal(signal_result.get("item"))
                if summary:
                    setattr(result, "decision_signal_summary", summary)
        except Exception as exc:
            logger.warning(
                "Decision signal extraction skipped after history save: query_id=%s stock_code=%s error=%s",
                query_id,
                getattr(result, "code", None),
                exc,
                exc_info=True,
            )

    @staticmethod
    def _build_notification_run_snapshot(
        *,
        channel: str,
        status: str,
        success: bool,
        attempts: int = 1,
        error_message: Optional[Any] = None,
    ) -> Dict[str, Any]:
        payload = {
            "channel": channel,
            "status": status,
            "success": success,
            "attempts": attempts,
            "created_at": datetime.now().isoformat(),
        }
        sanitized_error = sanitize_diagnostic_text(error_message)
        if sanitized_error:
            payload["error_message_sanitized"] = sanitized_error
        return payload

    def _refresh_saved_diagnostic_snapshot(
        self,
        *,
        result: Optional[AnalysisResult] = None,
        results: Optional[List[AnalysisResult]] = None,
        fallback_code: Optional[str] = None,
        notification_run: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Patch persisted history diagnostics with notification outcomes."""
        if not getattr(self, "save_context_snapshot", True):
            return

        db = getattr(self, "db", None)
        updater = getattr(db, "update_analysis_history_diagnostics", None)
        if not callable(updater):
            return

        diagnostic_snapshot = current_diagnostic_snapshot()
        if diagnostic_snapshot is not None:
            query_id = (
                diagnostic_snapshot.get("query_id")
                or getattr(result, "query_id", None)
                or getattr(self, "query_id", None)
            )
            code = (
                getattr(result, "code", None)
                or fallback_code
                or diagnostic_snapshot.get("stock_code")
            )
            if not query_id:
                return
            try:
                updater(query_id=query_id, code=code, diagnostics=diagnostic_snapshot)
            except Exception as exc:
                logger.warning("\u56de\u5199\u8fd0\u884c\u8bca\u65ad\u5feb\u7167failed (fail-open): %s", exc)
            return

        if notification_run is None:
            return

        target_results = list(results or ([] if result is None else [result]))
        for item in target_results:
            query_id = getattr(item, "query_id", None) or getattr(self, "query_id", None)
            if not query_id:
                continue
            code = getattr(item, "code", None) or fallback_code
            try:
                updater(
                    query_id=query_id,
                    code=code,
                    notification_runs=[notification_run],
                )
            except Exception as exc:
                logger.warning("\u56de\u5199\u901a\u77e5\u8bca\u65ad\u5feb\u7167failed (fail-open): %s", exc)

    def _load_persisted_intelligence_context(
        self,
        *,
        code: str,
        stock_name: str,
        market: str,
        limit: int = 6,
    ) -> Optional[str]:
        """Load locally persisted intelligence as fail-open evidence context."""
        try:
            service = IntelligenceService(config=self.config)
            service.refresh_auto_sources()
            days = max(1, int(self.config.get_effective_news_window_days() or 1))
            collected: list[Dict[str, Any]] = []
            seen_urls: set[str] = set()
            symbol_filters = [
                {"scope_type": "symbol", "scope_value": scope_value, "market": market}
                for scope_value in _symbol_scope_lookup_values(code, market)
            ]
            for filters in symbol_filters + [{"scope_type": "market", "market": market}]:
                payload = service.list_items(published_days=days, page=1, page_size=limit, **filters)
                for item in payload.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    url = str(item.get("url") or "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    collected.append(item)
                    if len(collected) >= limit:
                        break
                if len(collected) >= limit:
                    break
            if not collected:
                return None
            lines = [f"## \u672c\u5730\u8d44\u8baf\u8bc1\u636e\u6c60 ({stock_name}/{code})"]
            for idx, item in enumerate(collected[:limit], 1):
                title = str(item.get("title") or "\u672a\u547d\u540d\u8d44\u8baf").strip()
                summary = str(item.get("summary") or "").strip()
                source = str(item.get("source") or item.get("source_name") or "local-intel").strip()
                published = str(item.get("published_at") or "").strip()
                url = str(item.get("url") or "").strip()
                meta = " / ".join(part for part in (source, published) if part)
                lines.append(f"{idx}. {title}" + (f" ({meta})" if meta else ""))
                if summary:
                    lines.append(f"   summary: {summary[:220]}")
                if url and not url.startswith("no-url:intel:"):
                    lines.append(f"   source: {url}")
            return "\n".join(lines)
        except Exception as exc:
            logger.debug("\u8bfb\u53d6\u672c\u5730\u8d44\u8baf\u8bc1\u636efailed (fail-open): %s", exc)
            return None

    def _build_legacy_analysis_artifacts(
        self,
        *,
        code: str,
        stock_name: str,
        market: str,
        phase: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        enhanced_context: Dict[str, Any],
        realtime_quote: Any,
        trend_result: Optional[TrendAnalysisResult],
        chip_data: Optional[ChipDistribution],
        fundamental_context: Optional[Dict[str, Any]],
        news_context: Optional[str],
        news_result_count: Optional[int],
        query_id: str,
        portfolio_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineAnalysisArtifacts:
        return PipelineAnalysisArtifacts(
            code=code,
            stock_name=stock_name,
            market=market,
            phase=phase,
            base_context=context,
            enhanced_context=enhanced_context,
            realtime_quote=realtime_quote,
            trend_result=trend_result,
            chip_data=chip_data,
            fundamental_context=fundamental_context,
            news_context=news_context,
            news_result_count=news_result_count,
            metadata={
                "query_id": query_id,
                "trigger_source": self.query_source,
            },
            portfolio_context=dict(portfolio_context) if isinstance(portfolio_context, dict) else None,
        )

    def _build_agent_analysis_artifacts(
        self,
        *,
        code: str,
        stock_name: str,
        market: str,
        phase: Optional[Dict[str, Any]],
        initial_context: Dict[str, Any],
        fundamental_context: Optional[Dict[str, Any]],
        query_id: str,
        base_context: Optional[Dict[str, Any]] = None,
        portfolio_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineAnalysisArtifacts:
        context_candidate = base_context
        if not isinstance(context_candidate, dict):
            context_candidate = initial_context.get("analysis_context")
        if isinstance(context_candidate, dict) and context_candidate:
            daily_context = dict(context_candidate)
            daily_context.setdefault("code", code)
            if stock_name:
                daily_context.setdefault("stock_name", stock_name)
        else:
            daily_context = {
                "code": code,
                "stock_name": stock_name,
                "data_missing": True,
                "today": {},
                "yesterday": {},
            }

        return PipelineAnalysisArtifacts(
            code=code,
            stock_name=stock_name,
            market=market,
            phase=phase,
            base_context=daily_context,
            enhanced_context={},
            realtime_quote=initial_context.get("realtime_quote"),
            trend_result=initial_context.get("trend_result"),
            chip_data=initial_context.get("chip_distribution"),
            fundamental_context=fundamental_context,
            news_context=initial_context.get("news_context"),
            news_result_count=None,
            metadata={
                "query_id": query_id,
                "trigger_source": self.query_source,
            },
            portfolio_context=dict(portfolio_context) if isinstance(portfolio_context, dict) else None,
        )

    def _build_analysis_context_pack_outputs(
        self,
        artifacts: PipelineAnalysisArtifacts,
        *,
        report_language: str,
        code: str,
        query_id: str,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        try:
            pack = AnalysisContextBuilder.build(artifacts)
            summary = format_analysis_context_pack_prompt_section(
                pack,
                report_language=report_language,
            )
            overview = render_analysis_context_pack_overview(
                pack,
                report_language=report_language,
            )
            return summary, overview
        except Exception as exc:
            logger.warning(
                "AnalysisContextPack output generation failed for %s query_id=%s: %s",
                code,
                query_id,
                exc,
            )
            return "", None

    @staticmethod
    def _without_runtime_prompt_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a shallow copy without runtime-only prompt context.

        Market phase and AnalysisContextPack summaries are prompt inputs only.
        P4 stores only the separately rendered public overview at snapshot top level.
        """
        sanitized = dict(context)
        sanitized.pop("market_phase_context", None)
        sanitized.pop("portfolio_context", None)
        sanitized.pop("analysis_context_pack", None)
        sanitized.pop("analysis_context_pack_summary", None)
        sanitized.pop("daily_market_context_summary", None)
        enhanced_context = sanitized.get("enhanced_context")
        if isinstance(enhanced_context, dict):
            enhanced_context = dict(enhanced_context)
            enhanced_context.pop("daily_market_context_summary", None)
            sanitized["enhanced_context"] = enhanced_context
        return sanitized

    _without_market_phase_context = _without_runtime_prompt_context

    @staticmethod
    def _resolve_resume_target_date(
        code: str, current_time: Optional[datetime] = None
    ) -> date:
        """
        Resolve the trading date used by checkpoint/resume checks.
        """
        market = get_market_for_stock(normalize_stock_code(code))
        return get_effective_trading_date(market, current_time=current_time)

    @staticmethod
    def _safe_to_dict(value: Any) -> Optional[Dict[str, Any]]:
        """
        \u5b89\u5168\u8f6c\u6362\u4e3a\u5b57\u5178
        """
        if value is None:
            return None
        if hasattr(value, "to_dict"):
            try:
                return value.to_dict()
            except Exception:
                return None
        if hasattr(value, "__dict__"):
            try:
                return dict(value.__dict__)
            except Exception:
                return None
        return None

    def _resolve_query_source(self, query_source: Optional[str] = None) -> str:
        """
        \u89e3\u6790requestsource.

        \u4f18\u5148\u7ea7 (\u4eceHigh\u5230Low):
        1. \u663e\u5f0f\u4f20\u5165\u7684 query_source: \u8c03\u7528\u65b9\u660e\u786e\u6307\u5b9a\u65f6\u4f18\u5148\u4f7f\u7528; \u4fbf\u4e8e\u8986\u76d6\u63a8\u65adresultor\u517c\u5bb9\u672a\u6765 source_message \u6765\u81ea\u975e bot \u7684\u573a\u666f
        2. \u5b58\u5728 source_message \u65f6\u63a8\u65ad\u4e3a "bot": \u5f53\u524d\u7ea6\u5b9a\u4e3a\u673a\u5668\u4ebaconversation\u4e0a\u4e0b\u6587
        3. \u5b58\u5728 query_id \u65f6\u63a8\u65ad\u4e3a "web": Web \u89e6\u53d1\u7684request\u4f1a\u5e26\u4e0a query_id
        4. default "system": scheduled taskor CLI \u7b49\u65e0\u4e0a\u8ff0\u4e0a\u4e0b\u6587\u65f6

        Args:
            query_source: \u8c03\u7528\u65b9\u663e\u5f0f\u6307\u5b9a\u7684source; \u5982 "bot" / "web" / "cli" / "system"

        Returns:
            \u5f52\u4e00\u5316\u540e\u7684source\u6807\u8bc6\u5b57\u7b26\u4e32; \u5982 "bot" / "web" / "cli" / "system"
        """
        if query_source:
            return query_source
        if getattr(self, "source_message", None):
            return "bot"
        if getattr(self, "query_id", None):
            return "web"
        return "system"

    def _build_query_context(self, query_id: Optional[str] = None) -> Dict[str, str]:
        """
        \u751f\u6210userquery\u5173\u8054info
        """
        effective_query_id = query_id or self.query_id or ""

        context: Dict[str, str] = {
            "query_id": effective_query_id,
            "query_source": self.query_source or "",
        }

        if self.source_message:
            context.update({
                "requester_platform": self.source_message.platform or "",
                "requester_user_id": self.source_message.user_id or "",
                "requester_user_name": self.source_message.user_name or "",
                "requester_chat_id": self.source_message.chat_id or "",
                "requester_message_id": self.source_message.message_id or "",
                "requester_query": self.source_message.content or "",
            })

        return context

    def process_single_stock(
        self,
        code: str,
        skip_analysis: bool = False,
        single_stock_notify: bool = False,
        report_type: ReportType = ReportType.SIMPLE,
        analysis_query_id: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> Optional[AnalysisResult]:
        """
        \u5904\u7406\u5355stocks\u7684\u5b8c\u6574\u6d41\u7a0b

        \u5305\u62ec:
        1. \u83b7\u53d6\u6570\u636e
        2. \u4fdd\u5b58\u6570\u636e
        3. AI analyze
        4. \u5355\u80a1\u63a8\u9001 (optional; #55)

        \u6b64\u65b9\u6cd5\u4f1a\u88ab\u7ebf\u7a0b\u6c60\u8c03\u7528; \u9700\u8981\u5904\u7406\u597d\u5f02\u5e38

        Args:
            analysis_query_id: query\u94fe\u8def\u5173\u8054 id
            code: stock code
            skip_analysis: \u662f\u5426skipping AI analyze
            single_stock_notify: \u662f\u5426\u542f\u7528\u5355\u80a1\u63a8\u9001mode (\u6bcfanalyze\u5b8c\u4e00\u53ea\u7acb\u5373\u63a8\u9001)
            report_type: report type\u679a\u4e3e (\u4ececonfig\u8bfb\u53d6; Issue #119)
            current_time: \u672c\u8f6e\u8fd0\u884c\u51bb\u7ed3\u7684\u53c2\u8003\u65f6\u95f4; \u7528\u4e8e\u7edf\u4e00\u65ad\u70b9\u7eed\u4f20\u76ee\u6807\u4ea4\u6613\u65e5\u5224\u65ad

        Returns:
            AnalysisResult or None
        """
        logger.info(f"========== \u5f00\u59cb\u5904\u7406 {code} ==========")

        from src.services.history_loader import set_frozen_target_date, reset_frozen_target_date
        frozen_td = self._resolve_resume_target_date(code, current_time=current_time)
        token = set_frozen_target_date(frozen_td)
        effective_query_id = analysis_query_id or getattr(self, "query_id", None) or uuid.uuid4().hex
        effective_trace_id = getattr(self, "trace_id", None) or effective_query_id
        diag_token = None
        if get_current_diagnostic_context() is None:
            diag_token = activate_run_diagnostic_context(
                trace_id=effective_trace_id,
                query_id=effective_query_id,
                stock_code=code,
                trigger_source=getattr(self, "query_source", None),
            )
        try:
            self._emit_progress(12, f"{code}: \u6b63\u5728\u51c6\u5907analysis task")
            # Step 1: \u83b7\u53d6\u5e76\u4fdd\u5b58\u6570\u636e
            success, error = self.fetch_and_save_stock_data(
                code, current_time=current_time
            )

            if not success:
                logger.warning(f"[{code}] \u6570\u636efetch failed: {error}")
                # \u5373\u4f7ffetch failed; \u4e5f\u5c1d\u8bd5\u7528\u5df2\u6709\u6570\u636eanalyze
            else:
                self._emit_progress(16, f"{code}: \u884c\u60c5\u6570\u636e\u51c6\u5907\u5b8c\u6210")

            # Step 2: AI analyze
            if skip_analysis:
                logger.info(f"[{code}] skipping AI analyze (dry-run mode)")
                return None

            analyze_kwargs = {"query_id": effective_query_id}
            if current_time is not None:
                analyze_kwargs["current_time"] = current_time
            result = self.analyze_stock(code, report_type, **analyze_kwargs)

            if result and result.success:
                logger.info(
                    f"[{code}] analysis completed: {result.operation_advice}, "
                    f"\u8bc4\u5206 {result.sentiment_score}"
                )

                # \u5355\u80a1\u63a8\u9001mode (#55): \u6bcfanalyze\u5b8c\u4e00stocks\u7acb\u5373\u63a8\u9001
                if single_stock_notify:
                    self._send_single_stock_notification(
                        result,
                        report_type=report_type,
                        fallback_code=code,
                    )
            elif result:
                logger.warning(
                    f"[{code}] analyze\u672asuccess: {result.error_message or 'unknown error'}"
                )

            return result

        except Exception as e:
            # \u6355\u83b7\u6240\u6709\u5f02\u5e38; \u786e\u4fdd\u5355\u80a1failed\u4e0d\u5f71\u54cd\u6574\u4f53
            logger.exception(f"[{code}] \u5904\u7406\u8fc7\u7a0b\u53d1\u751funknown\u5f02\u5e38: {e}")
            return None
        finally:
            reset_run_diagnostic_context(diag_token)
            reset_frozen_target_date(token)

    def run(
        self,
        stock_codes: Optional[List[str]] = None,
        dry_run: bool = False,
        send_notification: bool = True,
        merge_notification: bool = False,
        current_time: Optional[datetime] = None,
    ) -> List[AnalysisResult]:
        """
        \u8fd0\u884c\u5b8c\u6574\u7684analysis flow

        \u6d41\u7a0b:
        1. \u83b7\u53d6\u5f85analyze\u7684\u80a1\u7968\u5217\u8868
        2. \u4f7f\u7528\u7ebf\u7a0b\u6c60\u5e76\u53d1\u5904\u7406
        3. \u6536\u96c6analysis result
        4. send notification

        Args:
            stock_codes: stock code\u5217\u8868 (optional; default\u4f7f\u7528configMedium\u7684watchlist)
            dry_run: \u662f\u5426\u4ec5\u83b7\u53d6\u6570\u636e\u4e0danalyze
            send_notification: \u662f\u5426\u53d1\u9001\u63a8\u9001\u901a\u77e5
            merge_notification: \u662f\u5426\u5408\u5e76\u63a8\u9001 (skippingthis run\u63a8\u9001; \u7531 main \u5c42\u5408\u5e76individual stocks+\u5927\u76d8\u540e\u7edf\u4e00\u53d1\u9001; Issue #190)
            current_time: \u672c\u8f6e\u8fd0\u884c\u51bb\u7ed3\u7684\u53c2\u8003\u65f6\u95f4；\u4e3a\u7a7a\u65f6\u5728 run \u5185\u751f\u6210

        Returns:
            analysis result\u5217\u8868
        """
        start_time = time.time()

        # \u4f7f\u7528configMedium\u7684\u80a1\u7968\u5217\u8868
        if stock_codes is None:
            self.config.refresh_stock_list()
            stock_codes = self.config.stock_list

        if not stock_codes:
            logger.error("not configuredwatchlist\u5217\u8868; \u8bf7\u5728 .env \u6587\u4ef6Medium\u8bbe\u7f6e STOCK_LIST")
            return []

        logger.info(f"===== \u5f00\u59cbanalyze {len(stock_codes)} stocks =====")
        logger.info(f"\u80a1\u7968\u5217\u8868: {', '.join(stock_codes)}")
        run_mode = '\u4ec5\u83b7\u53d6\u6570\u636e' if dry_run else '\u5b8c\u6574analyze'
        logger.info(f"\u5e76\u53d1\u6570: {self.max_workers}, mode: {run_mode}")

        # \u51bb\u7ed3\u672c\u8f6e\u8fd0\u884c\u7684\u7edf\u4e00\u53c2\u8003\u65f6\u95f4; \u907f\u514d\u8de8market\u6536\u76d8\u8fb9\u754c\u65f6\u540c\u6279\u80a1\u7968\u4f7f\u7528\u4e0d\u540c\u76ee\u6807\u4ea4\u6613\u65e5.
        resume_reference_time = current_time or datetime.now(timezone.utc)

        # === batch\u9884\u53d6realtime quote (\u4f18\u5316: \u907f\u514d\u6bcfstocks\u90fd\u89e6\u53d1\u5168\u91cf\u62c9\u53d6)===
        # \u53ea\u6709\u80a1\u7968count >= 5 \u65f6\u624d\u8fdb\u884c\u9884\u53d6; \u5c11\u91cf\u80a1\u7968\u76f4\u63a5\u9010\u4e2aquery\u66f4High\u6548
        if len(stock_codes) >= 5:
            daily_prefetch_count = self.fetcher_manager.prefetch_daily_klines(stock_codes, days=30)
            if daily_prefetch_count > 0:
                logger.info(
                    "[prefetch] component=daily_kline_prefetch action=complete "
                    "provider=TickFlowFetcher cached=%d stock_count=%d",
                    daily_prefetch_count,
                    len(stock_codes),
                )

            prefetch_count = self.fetcher_manager.prefetch_realtime_quotes(stock_codes)
            if prefetch_count > 0:
                logger.info(f"enabledbatch\u9884\u53d6\u67b6\u6784: \u4e00\u6b21\u62c9\u53d6\u5168market\u6570\u636e; {len(stock_codes)} stocks\u5171\u4eabcache")

        # Issue #455: \u9884\u53d6stock name; \u907f\u514d\u5e76\u53d1analyze\u65f6\u663e\u793a「\u80a1\u7968xxxxx」
        # dry_run \u4ec5\u505a\u6570\u636e\u62c9\u53d6; \u4e0d\u9700\u8981name\u9884\u53d6; \u907f\u514d\u989d\u5916\u7f51\u7edc\u5f00\u9500
        if not dry_run:
            self.fetcher_manager.prefetch_stock_names(stock_codes, use_bulk=False)

        # \u5355\u80a1\u63a8\u9001mode (#55): \u4ececonfig\u8bfb\u53d6
        single_stock_notify = getattr(self.config, 'single_stock_notify', False)
        # Issue #119: \u4ececonfig\u8bfb\u53d6report type
        report_type_str = getattr(self.config, 'report_type', 'simple').lower()
        if report_type_str == 'brief':
            report_type = ReportType.BRIEF
        elif report_type_str == 'full':
            report_type = ReportType.FULL
        else:
            report_type = ReportType.SIMPLE
        # Issue #128: \u4ececonfig\u8bfb\u53d6analyze\u95f4\u9694
        analysis_delay = getattr(self.config, 'analysis_delay', 0)

        if single_stock_notify:
            logger.info(
                "enabled\u5355\u80a1\u63a8\u9001mode: analyze\u4ecd\u5e76\u53d1\u6267\u884c; \u901a\u77e5\u6539\u4e3a\u5728result\u6536\u96c6\u4fa7\u4e32\u884c\u53d1\u9001 (report type: %s)",
                report_type_str,
            )

        results: List[AnalysisResult] = []

        # \u4f7f\u7528\u7ebf\u7a0b\u6c60\u5e76\u53d1\u5904\u7406
        # \u6ce8\u610f: max_workers \u8bbe\u7f6e\u8f83Low (default3)\u4ee5\u907f\u514d\u89e6\u53d1\u53cd\u722c
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # \u63d0\u4ea4task
            future_to_code = {
                executor.submit(
                    self.process_single_stock,
                    code,
                    skip_analysis=dry_run,
                    single_stock_notify=False,
                    report_type=report_type,  # Issue #119: \u4f20\u9012report type
                    analysis_query_id=uuid.uuid4().hex,
                    current_time=resume_reference_time,
                ): code
                for code in stock_codes
            }

            # \u6536\u96c6result
            for idx, future in enumerate(as_completed(future_to_code)):
                code = future_to_code[future]
                try:
                    result = future.result()
                    if result and result.success:
                        results.append(result)
                        if single_stock_notify and send_notification and not dry_run:
                            self._send_single_stock_notification(
                                result,
                                report_type=report_type,
                                fallback_code=code,
                            )
                    elif result and not result.success:
                        logger.warning(
                            f"[{code}] analysis result\u6807\u8bb0\u4e3afailed; \u4e0d\u8ba1\u5165\u6c47\u603b: "
                            f"{result.error_message or 'unknownreason'}"
                        )

                    # Issue #128: analyze\u95f4\u9694 - \u5728individual stocksanalyze\u548c\u5927\u76d8analyze\u4e4b\u95f4\u6dfb\u52a0\u5ef6\u8fdf
                    if idx < len(stock_codes) - 1 and analysis_delay > 0:
                        # \u6ce8\u610f: \u6b64 sleep \u53d1\u751f\u5728“\u4e3b\u7ebf\u7a0b\u6536\u96c6 future \u7684\u5faa\u73af”Medium;
                        # \u5e76\u4e0d\u4f1a\u963b\u6b62\u7ebf\u7a0b\u6c60Medium\u7684task\u540c\u65f6\u53d1\u8d77\u7f51\u7edcrequest.
                        # \u56e0\u6b64\u5b83\u5bf9\u964dLow\u5e76\u53d1request\u5cf0\u503c\u7684\u6548\u679c\u6709\u9650；\u771f\u6b63\u7684\u5cf0\u503c\u4e3b\u8981\u7531 max_workers \u51b3\u5b9a.
                        # \u8be5\u884c\u4e3a\u76ee\u524d\u4fdd\u7559 (\u6309\u9700\u6c42\u4e0d\u6539\u903b\u8f91).
                        logger.debug(f"waiting {analysis_delay} \u79d2\u540e\u7ee7\u7eed\u4e0b\u4e00stocks...")
                        time.sleep(analysis_delay)

                except Exception as e:
                    logger.error(f"[{code}] taskexecution failed: {e}")

        # \u7edf\u8ba1
        elapsed_time = time.time() - start_time

        # dry-run mode\u4e0b; \u6570\u636efetch succeeded\u5373\u89c6\u4e3asuccess
        if dry_run:
            # \u68c0check\u54ea\u4e9b\u80a1\u7968\u7684\u6700\u65b0\u53ef\u590d\u7528\u4ea4\u6613\u65e5\u6570\u636ealready exists
            success_count = sum(
                1
                for code in stock_codes
                if self.db.has_today_data(
                    code,
                    self._resolve_resume_target_date(
                        code, current_time=resume_reference_time
                    ),
                )
            )
            fail_count = len(stock_codes) - success_count
        else:
            success_count = len(results)
            fail_count = len(stock_codes) - success_count

        logger.info("===== analysis completed =====")
        logger.info(f"success: {success_count}, failed: {fail_count}, elapsed: {elapsed_time:.2f} \u79d2")

        # \u4fdd\u5b58report\u5230\u672c\u5730\u6587\u4ef6 (\u65e0\u8bba\u662f\u5426\u63a8\u9001\u901a\u77e5\u90fd\u4fdd\u5b58)
        if results and not dry_run:
            self._save_local_report(results, report_type)

        # send notification (\u5355\u80a1\u63a8\u9001mode\u4e0bskipping\u6c47\u603b\u63a8\u9001; \u907f\u514d\u91cd\u590d)
        if results and send_notification and not dry_run:
            if single_stock_notify:
                # \u5355\u80a1\u63a8\u9001mode: \u53ea\u4fdd\u5b58\u6c47\u603breport; \u4e0d\u518d\u91cd\u590d\u63a8\u9001
                logger.info("\u5355\u80a1\u63a8\u9001mode: skipping\u6c47\u603b\u63a8\u9001; \u4ec5\u4fdd\u5b58report\u5230\u672c\u5730")
                self._send_notifications(results, report_type, skip_push=True)
            elif merge_notification:
                # \u5408\u5e76mode (Issue #190): \u4ec5\u4fdd\u5b58; \u4e0d\u63a8\u9001; \u7531 main \u5c42\u5408\u5e76individual stocks+\u5927\u76d8\u540e\u7edf\u4e00\u53d1\u9001
                logger.info("\u5408\u5e76\u63a8\u9001mode: skippingthis run\u63a8\u9001; \u5c06\u5728individual stocks+market review\u540e\u7edf\u4e00\u53d1\u9001")
                self._send_notifications(results, report_type, skip_push=True)
            else:
                self._send_notifications(results, report_type)

        return results

    def _send_single_stock_notification(
        self,
        result: AnalysisResult,
        report_type: ReportType = ReportType.SIMPLE,
        fallback_code: Optional[str] = None,
    ) -> None:
        """\u53d1\u9001\u5355\u80a1\u901a\u77e5; \u4f9b\u76f4\u63a5\u5355\u80a1\u5165\u53e3\u548cbatch\u4e32\u884c\u63a8\u9001\u5171\u7528."""
        if not self.notifier.is_available():
            notification_run = self._build_notification_run_snapshot(
                channel="report",
                status="not_configured",
                success=False,
                attempts=0,
            )
            record_notification_run(
                channel="report",
                status="not_configured",
                success=False,
                attempts=0,
            )
            self._refresh_saved_diagnostic_snapshot(
                result=result,
                fallback_code=fallback_code,
                notification_run=notification_run,
            )
            return

        stock_code = getattr(result, "code", None) or fallback_code or "unknown"
        notify_lock = getattr(self, "_single_stock_notify_lock", None)
        if notify_lock is None:
            with _SINGLE_STOCK_NOTIFY_LOCK_INIT_GUARD:
                notify_lock = getattr(self, "_single_stock_notify_lock", None)
                if notify_lock is None:
                    notify_lock = threading.Lock()
                    setattr(self, "_single_stock_notify_lock", notify_lock)

        with notify_lock:
            try:
                if report_type == ReportType.FULL:
                    report_content = self.notifier.generate_dashboard_report([result])
                    logger.info(f"[{stock_code}] \u4f7f\u7528\u5b8c\u6574report\u683c\u5f0f")
                elif report_type == ReportType.BRIEF:
                    report_content = self.notifier.generate_brief_report([result])
                    logger.info(f"[{stock_code}] \u4f7f\u7528\u7b80\u6d01report\u683c\u5f0f")
                else:
                    report_content = self.notifier.generate_single_stock_report(result)
                    logger.info(f"[{stock_code}] \u4f7f\u7528\u7cbe\u7b80report\u683c\u5f0f")

                sent = self.notifier.send(
                    report_content,
                    email_stock_codes=[stock_code],
                    route_type="report",
                    severity="info",
                    dedup_key=f"report:single:{stock_code}:{report_type.value}",
                    cooldown_key=f"report:single:{stock_code}:{report_type.value}",
                )
                notification_run = self._build_notification_run_snapshot(
                    channel="report",
                    status="success" if sent else "failed",
                    success=sent,
                )
                record_notification_run(
                    channel="report",
                    status="success" if sent else "failed",
                    success=sent,
                )
                self._refresh_saved_diagnostic_snapshot(
                    result=result,
                    fallback_code=fallback_code,
                    notification_run=notification_run,
                )
                if sent:
                    logger.info(f"[{stock_code}] \u5355\u80a1\u63a8\u9001success")
                else:
                    logger.warning(f"[{stock_code}] \u5355\u80a1\u63a8\u9001failed")
            except Exception as e:
                notification_run = self._build_notification_run_snapshot(
                    channel="report",
                    status="failed",
                    success=False,
                    error_message=e,
                )
                record_notification_run(
                    channel="report",
                    status="failed",
                    success=False,
                    error_message=e,
                )
                self._refresh_saved_diagnostic_snapshot(
                    result=result,
                    fallback_code=fallback_code,
                    notification_run=notification_run,
                )
                logger.error(f"[{stock_code}] \u5355\u80a1\u63a8\u9001\u5f02\u5e38: {e}")

    def _save_local_report(
        self,
        results: List[AnalysisResult],
        report_type: ReportType = ReportType.SIMPLE,
    ) -> None:
        """\u4fdd\u5b58analyzereport\u5230\u672c\u5730\u6587\u4ef6 (\u4e0e\u901a\u77e5\u63a8\u9001\u89e3\u8026)"""
        try:
            report = self._generate_aggregate_report(results, report_type)
            filepath = self.notifier.save_report_to_file(report)
            logger.info(f"\u51b3\u7b56\u4eea\u8868\u76d8\u65e5\u62a5\u5df2\u4fdd\u5b58: {filepath}")
        except Exception as e:
            logger.error(f"\u4fdd\u5b58\u672c\u5730reportfailed: {e}")

    def _send_notifications(
        self,
        results: List[AnalysisResult],
        report_type: ReportType = ReportType.SIMPLE,
        skip_push: bool = False,
    ) -> None:
        """
        \u53d1\u9001analysis result\u901a\u77e5

        \u751f\u6210\u51b3\u7b56\u4eea\u8868\u76d8\u683c\u5f0f\u7684report

        Args:
            results: analysis result\u5217\u8868
            skip_push: \u662f\u5426skipping\u63a8\u9001 (\u4ec5\u4fdd\u5b58\u5230\u672c\u5730; \u7528\u4e8e\u5355\u80a1\u63a8\u9001mode)
        """
        noise_decision = None
        noise_finalized = False
        try:
            logger.info("\u751f\u6210\u51b3\u7b56\u4eea\u8868\u76d8\u65e5\u62a5...")
            report = self._generate_aggregate_report(results, report_type)

            # skipping\u63a8\u9001 (\u5355\u80a1\u63a8\u9001mode / \u5408\u5e76mode: report\u5df2\u7531 _save_local_report \u4fdd\u5b58)
            if skip_push:
                notification_run = self._build_notification_run_snapshot(
                    channel="report",
                    status="skipped",
                    success=False,
                    attempts=0,
                )
                record_notification_run(
                    channel="report",
                    status="skipped",
                    success=False,
                    attempts=0,
                )
                self._refresh_saved_diagnostic_snapshot(
                    results=results,
                    notification_run=notification_run,
                )
                return

            # \u63a8\u9001\u901a\u77e5
            if self.notifier.is_available():
                channels = self.notifier.get_available_channels()
                channels = self.notifier.get_channels_for_route("report", channels=channels)

                def _send_channel_safely(
                    channel_label: str,
                    send_func: Callable[[], bool],
                ) -> tuple[bool, Optional[Exception]]:
                    try:
                        return bool(send_func()), None
                    except Exception as e:
                        logger.exception(
                            "notification channel %s \u63a8\u9001\u5f02\u5e38; continuing to tryother\u6e20\u9053: %s",
                            channel_label,
                            e,
                        )
                        return False, e

                def _record_channel_result(
                    channel_label: str,
                    success: bool,
                    error_message: Optional[Exception] = None,
                    target_results: Optional[List[AnalysisResult]] = None,
                ) -> None:
                    notification_run = self._build_notification_run_snapshot(
                        channel=channel_label,
                        status="success" if success else "failed",
                        success=success,
                        error_message=error_message,
                    )
                    record_notification_run(
                        channel=channel_label,
                        status="success" if success else "failed",
                        success=success,
                        error_message=error_message,
                    )
                    self._refresh_saved_diagnostic_snapshot(
                        results=results if target_results is None else target_results,
                        notification_run=notification_run,
                    )

                send_context = self.notifier.send_to_context(report)
                if send_context:
                    _record_channel_result("__context__", True)

                should_broadcast_static = True
                should_broadcast_static_func = getattr(
                    self.notifier,
                    "should_broadcast_static_channels",
                    None,
                )
                if callable(should_broadcast_static_func):
                    should_broadcast_static = bool(should_broadcast_static_func())
                if not should_broadcast_static:
                    if not send_context:
                        _record_channel_result("__context__", False)
                    if send_context:
                        logger.info("\u51b3\u7b56\u4eea\u8868\u76d8\u63a8\u9001success")
                    else:
                        logger.warning("\u51b3\u7b56\u4eea\u8868\u76d8\u63a8\u9001failed")
                    logger.info("\u4ea4\u4e92\u5f0f\u6d88\u606f\u4e0a\u4e0b\u6587\u56de\u590dmode: \u5df2skipping\u9759\u6001notification channel")
                    return

                if channels and hasattr(self.notifier, "evaluate_noise_control"):
                    report_type_key = report_type.value if isinstance(report_type, ReportType) else str(report_type)
                    codes_key = ",".join(
                        sorted(str(getattr(result, "code", "") or "") for result in results)
                    )
                    noise_key = f"report:aggregate:{report_type_key}:{codes_key}"
                    noise_decision = self.notifier.evaluate_noise_control(
                        report,
                        route_type="report",
                        severity="info",
                        dedup_key=noise_key,
                        cooldown_key=noise_key,
                    )
                    if not noise_decision.should_send:
                        notification_run = self._build_notification_run_snapshot(
                            channel="report",
                            status="skipped",
                            success=False,
                            attempts=0,
                        )
                        record_notification_run(
                            channel="report",
                            status="skipped",
                            success=False,
                            attempts=0,
                        )
                        self._refresh_saved_diagnostic_snapshot(
                            results=results,
                            notification_run=notification_run,
                        )
                        logger.info(noise_decision.message)
                        return

                # Issue #455: Markdown \u8f6c\u56fe\u7247 (\u4e0e notification.send \u903b\u8f91\u4e00\u81f4)
                from src.md2img import markdown_to_image

                channels_needing_image = {
                    ch for ch in channels
                    if ch.value in self.notifier._markdown_to_image_channels
                    and ch not in {NotificationChannel.NTFY, NotificationChannel.GOTIFY}
                }
                non_wechat_channels_needing_image = {
                    ch for ch in channels_needing_image if ch != NotificationChannel.WECHAT
                }

                def _get_md2img_hint() -> str:
                    try:
                        engine = getattr(get_config(), "md2img_engine", "wkhtmltoimage")
                    except Exception:
                        engine = "wkhtmltoimage"
                    return (
                        "npm i -g markdown-to-file" if engine == "markdown-to-file"
                        else "wkhtmltopdf (apt install wkhtmltopdf / brew install wkhtmltopdf)"
                    )

                image_bytes = None
                if non_wechat_channels_needing_image:
                    image_bytes = markdown_to_image(
                        report, max_chars=self.notifier._markdown_to_image_max_chars
                    )
                    if image_bytes:
                        logger.info(
                            "Markdown \u5df2\u8f6c\u6362\u4e3a\u56fe\u7247; \u5c06\u5411 %s \u53d1\u9001\u56fe\u7247",
                            [ch.value for ch in non_wechat_channels_needing_image],
                        )
                    else:
                        logger.warning(
                            "Markdown \u8f6c\u56fe\u7247failed; \u5c06\u56de\u9000\u4e3a\u6587\u672c\u53d1\u9001.\u8bf7\u68c0check MARKDOWN_TO_IMAGE_CHANNELS config\u5e76\u5b89\u88c5 %s",
                            _get_md2img_hint(),
                        )

                # WeCom: \u53ea\u53d1\u7cbe\u7b80\u7248 (\u5e73\u53f0limit)
                wechat_success = False
                if NotificationChannel.WECHAT in channels:
                    def _send_wechat_report() -> bool:
                        if report_type == ReportType.BRIEF:
                            dashboard_content = self.notifier.generate_brief_report(results)
                        else:
                            dashboard_content = self.notifier.generate_wechat_dashboard(results)
                        logger.info(f"WeCom\u4eea\u8868\u76d8\u957f\u5ea6: {len(dashboard_content)} \u5b57\u7b26")
                        logger.debug(f"WeCom\u63a8\u9001\u5185\u5bb9:\n{dashboard_content}")
                        wechat_image_bytes = None
                        if NotificationChannel.WECHAT in channels_needing_image:
                            wechat_image_bytes = markdown_to_image(
                                dashboard_content,
                                max_chars=self.notifier._markdown_to_image_max_chars,
                            )
                            if wechat_image_bytes is None:
                                logger.warning(
                                    "WeCom Markdown \u8f6c\u56fe\u7247failed; \u5c06\u56de\u9000\u4e3a\u6587\u672c\u53d1\u9001.\u8bf7\u68c0check MARKDOWN_TO_IMAGE_CHANNELS config\u5e76\u5b89\u88c5 %s",
                                    _get_md2img_hint(),
                                )
                        use_image = self.notifier._should_use_image_for_channel(
                            NotificationChannel.WECHAT, wechat_image_bytes
                        )
                        if use_image:
                            return self.notifier._send_wechat_image(wechat_image_bytes)
                        return self.notifier.send_to_wechat(dashboard_content)

                    wechat_success, wechat_error = _send_channel_safely(
                        NotificationChannel.WECHAT.value,
                        _send_wechat_report,
                    )
                    _record_channel_result(
                        NotificationChannel.WECHAT.value,
                        wechat_success,
                        wechat_error,
                    )

                # other\u6e20\u9053: \u53d1\u5b8c\u6574report (\u907f\u514d\u81ea\u5b9a\u4e49 Webhook \u88ab wechat \u622a\u65ad\u903b\u8f91\u6c61\u67d3)
                non_wechat_success = False
                stock_email_groups = getattr(self.config, 'stock_email_groups', []) or []
                for channel in channels:
                    if channel == NotificationChannel.WECHAT:
                        continue
                    if channel == NotificationChannel.FEISHU:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_feishu(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.TELEGRAM:
                        def _send_telegram_report() -> bool:
                            use_image = self.notifier._should_use_image_for_channel(
                                channel, image_bytes
                            )
                            if use_image:
                                return self.notifier._send_telegram_photo(image_bytes)
                            return self.notifier.send_to_telegram(report)

                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            _send_telegram_report,
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.EMAIL:
                        if stock_email_groups:
                            code_to_emails: Dict[str, Optional[List[str]]] = {}
                            for r in results:
                                if r.code not in code_to_emails:
                                    canonical = normalize_stock_code(r.code)
                                    emails = []
                                    for stocks, emails_list in stock_email_groups:
                                        if canonical in stocks:
                                            emails.extend(emails_list)
                                    code_to_emails[r.code] = list(dict.fromkeys(emails)) if emails else None
                            emails_to_results: Dict[Optional[Tuple], List] = defaultdict(list)
                            for r in results:
                                recs = code_to_emails.get(r.code)
                                key = tuple(recs) if recs else None
                                emails_to_results[key].append(r)
                            for key, group_results in emails_to_results.items():
                                receivers = list(key) if key is not None else None

                                def _send_email_group(
                                    group_results=group_results,
                                    receivers=receivers,
                                ) -> bool:
                                    grp_report = self._generate_aggregate_report(group_results, report_type)
                                    grp_image_bytes = None
                                    if channel.value in self.notifier._markdown_to_image_channels:
                                        grp_image_bytes = markdown_to_image(
                                            grp_report,
                                            max_chars=self.notifier._markdown_to_image_max_chars,
                                        )
                                    use_image = self.notifier._should_use_image_for_channel(
                                        channel, grp_image_bytes
                                    )
                                    if use_image:
                                        return self.notifier._send_email_with_inline_image(
                                            grp_image_bytes, receivers=receivers
                                        )
                                    return self.notifier.send_to_email(
                                        grp_report, receivers=receivers
                                    )

                                email_label = (
                                    f"{channel.value}:{','.join(receivers)}"
                                    if receivers else f"{channel.value}:default"
                                )
                                channel_success, channel_error = _send_channel_safely(
                                    email_label,
                                    _send_email_group,
                                )
                                non_wechat_success = channel_success or non_wechat_success
                                _record_channel_result(
                                    email_label,
                                    channel_success,
                                    channel_error,
                                    target_results=group_results,
                                )
                        else:
                            def _send_email_report() -> bool:
                                use_image = self.notifier._should_use_image_for_channel(
                                    channel, image_bytes
                                )
                                if use_image:
                                    return self.notifier._send_email_with_inline_image(image_bytes)
                                return self.notifier.send_to_email(report)

                            channel_success, channel_error = _send_channel_safely(
                                channel.value,
                                _send_email_report,
                            )
                            non_wechat_success = channel_success or non_wechat_success
                            _record_channel_result(
                                channel.value,
                                channel_success,
                                channel_error,
                            )
                    elif channel == NotificationChannel.CUSTOM:
                        def _send_custom_report() -> bool:
                            use_image = self.notifier._should_use_image_for_channel(
                                channel, image_bytes
                            )
                            if use_image:
                                return self.notifier._send_custom_webhook_image(
                                    image_bytes, fallback_content=report
                                )
                            return self.notifier.send_to_custom(report)

                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            _send_custom_report,
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.PUSHPLUS:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_pushplus(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.SERVERCHAN3:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_serverchan3(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.DISCORD:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_discord(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.PUSHOVER:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_pushover(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.NTFY:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_ntfy(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.GOTIFY:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_gotify(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.ASTRBOT:
                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            lambda: self.notifier.send_to_astrbot(report),
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    elif channel == NotificationChannel.SLACK:
                        def _send_slack_report() -> bool:
                            use_image = self.notifier._should_use_image_for_channel(
                                channel, image_bytes
                            )
                            if use_image and self.notifier._slack_bot_token and self.notifier._slack_channel_id:
                                return self.notifier._send_slack_image(
                                    image_bytes, fallback_content=report
                                )
                            return self.notifier.send_to_slack(report)

                        channel_success, channel_error = _send_channel_safely(
                            channel.value,
                            _send_slack_report,
                        )
                        non_wechat_success = channel_success or non_wechat_success
                        _record_channel_result(
                            channel.value,
                            channel_success,
                            channel_error,
                        )
                    else:
                        logger.warning(f"unknownnotification channel: {channel}")

                has_targeted_channels = bool(channels)
                success = wechat_success or non_wechat_success or send_context
                if (
                    (wechat_success or non_wechat_success)
                    and noise_decision is not None
                    and hasattr(self.notifier, "record_noise_control")
                ):
                    self.notifier.record_noise_control(noise_decision)
                    noise_finalized = True
                elif (
                    noise_decision is not None
                    and hasattr(self.notifier, "release_noise_control")
                ):
                    self.notifier.release_noise_control(noise_decision)
                    noise_finalized = True
                if success:
                    logger.info("\u51b3\u7b56\u4eea\u8868\u76d8\u63a8\u9001success")
                else:
                    logger.warning("\u51b3\u7b56\u4eea\u8868\u76d8\u63a8\u9001failed")
                if not has_targeted_channels and not send_context:
                    channel_label = ",".join(channel.value for channel in channels) or "report"
                    notification_run = self._build_notification_run_snapshot(
                        channel=channel_label,
                        status="success" if success else "failed",
                        success=success,
                    )
                    record_notification_run(
                        channel=channel_label,
                        status="success" if success else "failed",
                        success=success,
                    )
                    self._refresh_saved_diagnostic_snapshot(
                        results=results,
                        notification_run=notification_run,
                    )
            else:
                notification_run = self._build_notification_run_snapshot(
                    channel="report",
                    status="not_configured",
                    success=False,
                    attempts=0,
                )
                record_notification_run(
                    channel="report",
                    status="not_configured",
                    success=False,
                    attempts=0,
                )
                self._refresh_saved_diagnostic_snapshot(
                    results=results,
                    notification_run=notification_run,
                )
                logger.info("notification channelnot configured; skipping\u63a8\u9001")

        except Exception as e:
            notification_run = self._build_notification_run_snapshot(
                channel="report",
                status="failed",
                success=False,
                error_message=e,
            )
            record_notification_run(
                channel="report",
                status="failed",
                success=False,
                error_message=e,
            )
            self._refresh_saved_diagnostic_snapshot(
                results=results,
                notification_run=notification_run,
            )
            if (
                noise_decision is not None
                and not noise_finalized
                and hasattr(self.notifier, "release_noise_control")
            ):
                self.notifier.release_noise_control(noise_decision)
            import traceback
            logger.error(f"send notificationfailed: {e}\n{traceback.format_exc()}")

    def _generate_aggregate_report(
        self,
        results: List[AnalysisResult],
        report_type: ReportType,
    ) -> str:
        """Generate aggregate report with backward-compatible notifier fallback."""
        generator = getattr(self.notifier, "generate_aggregate_report", None)
        if callable(generator):
            return generator(results, report_type)
        if report_type == ReportType.BRIEF and hasattr(self.notifier, "generate_brief_report"):
            return self.notifier.generate_brief_report(results)
        return self.notifier.generate_dashboard_report(results)
