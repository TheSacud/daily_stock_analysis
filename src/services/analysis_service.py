# -*- coding: utf-8 -*-
"""
===================================
analyze\u670d\u52a1\u5c42
===================================

\u804c\u8d23:
1. \u5c01\u88c5\u80a1\u7968analyze\u903b\u8f91
2. \u8c03\u7528 analyzer \u548c pipeline \u6267\u884canalyze
3. \u4fdd\u5b58analysis result\u5230\u6570\u636elibrary
"""

import logging
import copy
import uuid
from typing import Optional, Dict, Any, Callable, List

from src.repositories.analysis_repo import AnalysisRepository
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.market_phase_summary import extract_market_phase_summary
from src.schemas.decision_action import build_action_fields
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    build_run_diagnostic_summary,
    get_current_diagnostic_context,
    reset_run_diagnostic_context,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    analyze\u670d\u52a1

    \u5c01\u88c5\u80a1\u7968analyze\u76f8\u5173\u7684\u4e1a\u52a1\u903b\u8f91
    """

    def __init__(self):
        """\u521d\u59cb\u5316analyze\u670d\u52a1"""
        self.repo = AnalysisRepository()
        self.last_error: Optional[str] = None

    def analyze_stock(
        self,
        stock_code: str,
        report_type: str = "detailed",
        force_refresh: bool = False,
        query_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        send_notification: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        skills: Optional[List[str]] = None,
        analysis_phase: str = "auto",
        query_source: str = "api",
        portfolio_context: Optional[Dict[str, Any]] = None,
        report_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        \u6267\u884c\u80a1\u7968analyze

        Args:
            stock_code: stock code
            report_type: report type (simple/detailed)
            force_refresh: \u662f\u5426\u5f3a\u5236\u5237\u65b0
            query_id: query ID (optional)
            send_notification: \u662f\u5426send notification (API \u89e6\u53d1default\u53d1\u9001)
            analysis_phase: request\u7684analyze\u9636\u6bb5\u8986\u76d6 (auto/premarket/intraday/postmarket)

        Returns:
            analysis result\u5b57\u5178; \u5305\u542b:
            - stock_code: stock code
            - stock_name: stock name
            - report: analyzereport
        """
        try:
            self.last_error = None
            # \u5bfc\u5165analyze\u76f8\u5173\u6a21chunks
            from src.config import get_config
            from src.core.pipeline import StockAnalysisPipeline
            from src.enums import ReportType

            # \u751f\u6210 query_id
            if query_id is None:
                query_id = uuid.uuid4().hex
            effective_trace_id = trace_id or query_id
            diag_token = None
            if get_current_diagnostic_context() is None:
                diag_token = activate_run_diagnostic_context(
                    trace_id=effective_trace_id,
                    query_id=query_id,
                    stock_code=stock_code,
                    trigger_source=query_source or "api",
                )

            # \u83b7\u53d6config
            config = get_config()
            normalized_report_language = normalize_report_language(report_language, default="")
            if normalized_report_language:
                config = copy.copy(config)
                config.report_language = normalized_report_language

            # \u521b\u5efaanalyze\u6d41\u6c34\u7ebf
            pipeline = StockAnalysisPipeline(
                config=config,
                query_id=query_id,
                trace_id=effective_trace_id,
                query_source=query_source or "api",
                progress_callback=progress_callback,
                analysis_skills=skills,
                analysis_phase=analysis_phase,
                portfolio_context=portfolio_context,
            )

            # \u786e\u5b9areport type (API: simple/detailed/full/brief -> ReportType)
            rt = ReportType.from_str(report_type)

            # \u6267\u884canalyze
            result = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=send_notification,
                report_type=rt,
            )

            if result is None:
                logger.warning(f"analyze stock {stock_code} returned empty result")
                self.last_error = self.last_error or f"analyze stock {stock_code} returned empty result"
                return None

            if not getattr(result, "success", True):
                self.last_error = getattr(result, "error_message", None) or f"analyze stock {stock_code} failed"
                logger.warning(f"analyze stock {stock_code} \u672asuccess\u5b8c\u6210: {self.last_error}")
                return None

            # \u6784\u5efa\u54cd\u5e94
            return self._build_analysis_response(result, query_id, report_type=rt.value)

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"analyze stock {stock_code} failed: {e}", exc_info=True)
            return None
        finally:
            reset_run_diagnostic_context(locals().get("diag_token"))

    def _build_analysis_response(
        self,
        result: Any,
        query_id: str,
        report_type: str = "detailed",
    ) -> Dict[str, Any]:
        """
        \u6784\u5efaanalyze\u54cd\u5e94

        Args:
            result: AnalysisResult \u5bf9\u8c61
            query_id: query ID
            report_type: \u5f52\u4e00\u5316\u540e\u7684report type

        Returns:
            \u683c\u5f0f\u5316\u7684\u54cd\u5e94\u5b57\u5178
        """
        # \u83b7\u53d6\u72d9\u51fb\u70b9characters
        sniper_points = {}
        if hasattr(result, 'get_sniper_points'):
            sniper_points = result.get_sniper_points() or {}

        # \u8ba1\u7b97\u60c5\u7eea\u6807\u7b7e
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        sentiment_label = get_sentiment_label(result.sentiment_score, report_language)
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        action_fields = build_action_fields(
            operation_advice=getattr(result, "operation_advice", None),
            explicit_action=getattr(result, "action", None),
            report_type=report_type,
            report_language=report_language,
            sentiment_score=getattr(result, "sentiment_score", None),
            guardrail_reason=getattr(result, "guardrail_reason", None),
            align_with_score=True,
        )
        diagnostic_context = get_current_diagnostic_context()
        trace_id = diagnostic_context.trace_id if diagnostic_context is not None else query_id
        diagnostic_snapshot = diagnostic_context.snapshot() if diagnostic_context is not None else None
        diagnostic_context_snapshot = getattr(result, "diagnostic_context_snapshot", None)
        market_phase_summary = extract_market_phase_summary(diagnostic_context_snapshot)
        if isinstance(diagnostic_context_snapshot, dict):
            context_snapshot = dict(diagnostic_context_snapshot)
            if diagnostic_snapshot is not None:
                context_snapshot["diagnostics"] = diagnostic_snapshot
        elif diagnostic_snapshot is not None:
            context_snapshot = {"diagnostics": diagnostic_snapshot}
        else:
            context_snapshot = None
        diagnostic_summary = build_run_diagnostic_summary(
            context_snapshot=context_snapshot,
            raw_result=result.to_dict() if hasattr(result, "to_dict") else None,
            report_saved=True,
            query_id=query_id,
            stock_code=result.code,
        )

        # \u6784\u5efareport\u7ed3\u6784
        report = {
            "meta": {
                "query_id": query_id,
                "trace_id": trace_id,
                "stock_code": result.code,
                "stock_name": stock_name,
                "report_type": report_type,
                "report_language": report_language,
                "current_price": result.current_price,
                "change_pct": result.change_pct,
                "model_used": getattr(result, "model_used", None),
                "market_phase_summary": market_phase_summary,
            },
            "summary": {
                "analysis_summary": result.analysis_summary,
                "operation_advice": localize_operation_advice(result.operation_advice, report_language),
                "action": action_fields["action"],
                "action_label": action_fields["action_label"],
                "trend_prediction": localize_trend_prediction(result.trend_prediction, report_language),
                "sentiment_score": result.sentiment_score,
                "sentiment_label": sentiment_label,
            },
            "strategy": {
                "ideal_buy": sniper_points.get("ideal_buy"),
                "secondary_buy": sniper_points.get("secondary_buy"),
                "stop_loss": sniper_points.get("stop_loss"),
                "take_profit": sniper_points.get("take_profit"),
            },
            "details": {
                "news_summary": result.news_summary,
                "technical_analysis": result.technical_analysis,
                "fundamental_analysis": result.fundamental_analysis,
                "risk_warning": result.risk_warning,
            }
        }

        return {
            "query_id": query_id,
            "trace_id": trace_id,
            "stock_code": result.code,
            "stock_name": stock_name,
            "report": report,
            "diagnostic_summary": diagnostic_summary,
        }
