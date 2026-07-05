# -*- coding: utf-8 -*-
"""
===================================
history records\u63a5\u53e3
===================================

\u804c\u8d23:
1. \u63d0\u4f9b GET /api/v1/history history\u5217\u8868query\u63a5\u53e3
2. \u63d0\u4f9b GET /api/v1/history/{query_id} history\u8be6\u60c5query\u63a5\u53e3
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Body

from api.deps import get_database_manager
from api.v1.schemas.history import (
    HistoryListResponse,
    HistoryItem,
    DeleteHistoryRequest,
    DeleteHistoryResponse,
    NewsIntelItem,
    NewsIntelResponse,
    AnalysisReport,
    ReportMeta,
    ReportSummary,
    ReportStrategy,
    ReportDetails,
    MarkdownReportResponse,
    RunDiagnosticSummaryResponse,
    StockBarItem,
    StockBarResponse,
)
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.run_flow import RunFlowSnapshot
from src.storage import DatabaseManager
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.services.history_service import HistoryService, MarkdownReportGenerationError
from src.schemas.decision_action import build_action_fields
from src.utils.data_processing import (
    normalize_model_used,
    extract_fundamental_detail_fields,
    extract_board_detail_fields,
    extract_realtime_detail_fields,
)
from src.analysis_context_pack_overview import (
    extract_analysis_context_pack_overview,
    sanitize_context_snapshot_for_api,
)
from src.market_phase_summary import extract_market_phase_summary

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_code_for_grouping(code: str) -> str:
    """Normalize stock code for deduplication grouping.

    Delegates to data_provider.base.normalize_stock_code which handles
    SH600519, 600519.SH, HK00700, 00700.HK, BJ920748, etc.
    """
    from data_provider.base import normalize_stock_code
    return normalize_stock_code(code or "")


def _raw_result_value(raw_result: Any, key: str) -> Any:
    if not isinstance(raw_result, dict):
        return None

    value = raw_result.get(key)
    if value is not None and value != "":
        return value

    for container_key in ("summary", "dashboard"):
        container = raw_result.get(container_key)
        if isinstance(container, dict):
            nested_value = container.get(key)
            if nested_value is not None and nested_value != "":
                return nested_value

    return None


def _coalesce_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _coalesce_int(*values: Any) -> Optional[int]:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


def _extract_guardrail_reason(raw_result: Any) -> Optional[str]:
    if not isinstance(raw_result, dict):
        return None
    for reason in (
        raw_result.get("guardrail_reason"),
        raw_result.get("downgrade_reason"),
        raw_result.get("decision_score_guardrail_reason"),
    ):
        if reason is not None:
            text = str(reason).strip()
            if text:
                return text

    metadata = raw_result.get("metadata")
    if isinstance(metadata, dict):
        metadata_reason = metadata.get("guardrail_reason") or metadata.get("downgrade_reason")
        if metadata_reason is not None:
            text = str(metadata_reason).strip()
            if text:
                return text
    return None


@router.get(
    "",
    response_model=HistoryListResponse,
    responses={
        200: {"description": "history records\u5217\u8868"},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6historyanalyze\u5217\u8868",
    description="\u5206\u9875\u83b7\u53d6historyanalyze\u8bb0\u5f55summary; \u652f\u6301\u6309stock code\u548cdate\u8303\u56f4\u7b5b\u9009"
)
def get_history_list(
    stock_code: Optional[str] = Query(None, description="stock code\u7b5b\u9009"),
    report_type: Optional[str] = Query(None, description="report type\u7b5b\u9009; \u5982 market_review"),
    start_date: Optional[str] = Query(None, description="\u5f00\u59cbdate (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="\u7ed3\u675fdate (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="\u9875\u7801 (\u4ece 1 \u5f00\u59cb)"),
    limit: int = Query(20, ge=1, le=100, description="\u6bcf\u9875count"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> HistoryListResponse:
    """
    \u83b7\u53d6historyanalyze\u5217\u8868

    \u5206\u9875\u83b7\u53d6historyanalyze\u8bb0\u5f55summary; \u652f\u6301\u6309stock code\u548cdate\u8303\u56f4\u7b5b\u9009

    Args:
        stock_code: stock code\u7b5b\u9009
        report_type: report type\u7b5b\u9009
        start_date: \u5f00\u59cbdate
        end_date: \u7ed3\u675fdate
        page: \u9875\u7801
        limit: \u6bcf\u9875count
        db_manager: \u6570\u636elibrary\u7ba1\u7406\u5668\u4f9d\u8d56

    Returns:
        HistoryListResponse: history records\u5217\u8868
    """
    try:
        service = HistoryService(db_manager)

        # \u4f7f\u7528 def \u800c\u975e async def; FastAPI \u81ea\u52a8\u5728\u7ebf\u7a0b\u6c60Medium\u6267\u884c
        result = service.get_history_list(
            stock_code=stock_code,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )

        # \u8f6c\u6362\u4e3a\u54cd\u5e94\u6a21\u578b
        items = [
            HistoryItem(
                id=item.get("id"),
                query_id=item.get("query_id", ""),
                stock_code=item.get("stock_code", ""),
                stock_name=item.get("stock_name"),
                report_type=item.get("report_type"),
                trend_prediction=item.get("trend_prediction"),
                analysis_summary=item.get("analysis_summary"),
                sentiment_score=item.get("sentiment_score"),
                operation_advice=item.get("operation_advice"),
                action=item.get("action"),
                action_label=item.get("action_label"),
                current_price=item.get("current_price"),
                change_pct=item.get("change_pct"),
                volume_ratio=item.get("volume_ratio"),
                turnover_rate=item.get("turnover_rate"),
                model_used=item.get("model_used"),
                created_at=item.get("created_at"),
                market_phase_summary=item.get("market_phase_summary"),
            )
            for item in result.get("items", [])
        ]

        return HistoryListResponse(
            total=result.get("total", 0),
            page=page,
            limit=limit,
            items=items
        )

    except Exception as e:
        logger.error(f"queryhistory\u5217\u8868failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"queryhistory\u5217\u8868failed: {str(e)}"
            }
        )


@router.delete(
    "/by-code/{stock_code}",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "delete succeeded"},
        404: {"description": "\u672a\u627e\u5230\u8bb0\u5f55", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u6309stock code\u5220\u9664historyanalyze\u8bb0\u5f55",
    description="\u5220\u9664\u6307\u5b9astock code\u7684\u6240\u6709analyzehistory records (\u652f\u6301code\u53d8\u4f53\u5f52\u4e00\u5316\u5339\u914d)",
)
def delete_history_by_code(
    stock_code: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> DeleteHistoryResponse:
    try:
        candidates = HistoryService._history_code_filter_candidates(stock_code)
        records, _ = db_manager.get_analysis_history_paginated(code=candidates, limit=10000)
        record_ids = [r.id for r in records if r.id is not None]
        if not record_ids:
            return DeleteHistoryResponse(deleted=0)
        deleted = db_manager.delete_analysis_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except Exception as e:
        logger.error(f"\u6309stock code\u5220\u9664history recordsfailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"delete failed: {str(e)}"},
        )


@router.delete(
    "",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "delete succeeded"},
        400: {"description": "requestinvalid parameters", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u5220\u9664historyanalyze\u8bb0\u5f55",
    description="\u6309history records\u4e3b\u952e ID batch\u5220\u9664analyzehistory"
)
def delete_history_records(
    request: DeleteHistoryRequest = Body(...),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DeleteHistoryResponse:
    """
    \u6309\u4e3b\u952e ID batch\u5220\u9664historyanalyze\u8bb0\u5f55.
    """
    record_ids = sorted({record_id for record_id in request.record_ids if record_id is not None})
    if not record_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": "record_ids cannot be empty"
            }
        )

    try:
        service = HistoryService(db_manager)
        deleted = service.delete_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"\u5220\u9664history recordsfailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"\u5220\u9664history recordsfailed: {str(e)}"
            }
        )


@router.get(
    "/stocks",
    response_model=StockBarResponse,
    responses={
        200: {"description": "\u4e0d\u91cd\u590dindividual stocks\u5217\u8868"},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6\u4e0d\u91cd\u590dindividual stocks\u5217\u8868",
    description="\u8fd4\u56dehistory recordsMedium\u6bcfstocks\u7684\u6700\u65b0\u4e00\u6761analyzesummary; \u4e0d\u5305\u542bmarket review (code=MARKET).",
)
def get_stock_bar(
    start_date: Optional[str] = Query(None, description="\u5f00\u59cbdate (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="\u7ed3\u675fdate (YYYY-MM-DD)"),
    limit: int = Query(200, ge=1, le=500, description="\u6700\u5927\u8fd4\u56decount"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> StockBarResponse:
    try:
        from datetime import date as date_type
        from src.utils.data_processing import parse_json_field

        service = HistoryService(db_manager)
        start = date_type.fromisoformat(start_date) if start_date else None
        end = date_type.fromisoformat(end_date) if end_date else None

        # Fetch more than limit to compensate for normalization dedup shrinkage
        # (e.g. 002460 + 002460.SZ both initially counted but merged to one)
        fetch_limit = min(limit * 3, 500)
        records = db_manager.get_distinct_stocks_from_history(
            start_date=start,
            end_date=end,
            limit=fetch_limit,
        )

        # Deduplicate by normalized code, keeping the record with highest id
        seen: dict = {}
        for record in records:
            display_code = service._display_stock_code(record.code or "")
            norm_code = _normalize_code_for_grouping(display_code)
            if norm_code not in seen or record.id > seen[norm_code].id:
                seen[norm_code] = record

        items = []
        for norm_code in seen:
            record = seen[norm_code]
            raw_result = parse_json_field(getattr(record, "raw_result", None))
            model_used = raw_result.get("model_used") if isinstance(raw_result, dict) else None
            sentiment_score = _coalesce_int(
                record.sentiment_score,
                _raw_result_value(raw_result, "sentiment_score"),
            )
            operation_advice = _coalesce_text(
                record.operation_advice,
                _raw_result_value(raw_result, "operation_advice"),
            )
            action_fields = build_action_fields(
                operation_advice=operation_advice,
                explicit_action=_raw_result_value(raw_result, "action"),
                report_type=record.report_type,
                report_language=normalize_report_language(
                    _raw_result_value(raw_result, "report_language")
                ),
                sentiment_score=sentiment_score,
                guardrail_reason=_extract_guardrail_reason(raw_result),
                align_with_score=True,
            )

            display_stock_code = service._display_stock_code(record.code)
            analysis_count = db_manager.get_analysis_history_paginated(
                code=HistoryService._history_code_filter_candidates(display_stock_code),
                limit=1,
            )[1]
            items.append(
                StockBarItem(
                    id=record.id,
                    stock_code=display_stock_code,
                    stock_name=record.name,
                    report_type=record.report_type,
                    sentiment_score=sentiment_score,
                    operation_advice=operation_advice,
                    action=action_fields["action"],
                    action_label=action_fields["action_label"],
                    analysis_count=analysis_count,
                    last_analysis_time=(
                        record.created_at.isoformat() if record.created_at else None
                    ),
                    model_used=normalize_model_used(model_used),
                    market_phase_summary=service._display_market_phase_summary(
                        record.code,
                        getattr(record, "context_snapshot", None),
                    ),
                )
            )

        items = items[:limit]
        return StockBarResponse(total=len(items), items=items)

    except Exception as e:
        logger.error(f"queryindividual stocks\u680ffailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"queryindividual stocks\u680ffailed: {str(e)}",
            },
        )


@router.get(
    "/{record_id}",
    response_model=AnalysisReport,
    responses={
        200: {"description": "report\u8be6\u60c5"},
        404: {"description": "reportdoes not exist", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6historyreport\u8be6\u60c5",
    description="\u6839\u636eanalyzehistory records ID or query_id \u83b7\u53d6\u5b8c\u6574\u7684historyanalyzereport"
)
def get_history_detail(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> AnalysisReport:
    """
    \u83b7\u53d6historyreport\u8be6\u60c5

    \u6839\u636eanalyzehistory records\u4e3b\u952e ID or query_id \u83b7\u53d6\u5b8c\u6574\u7684historyanalyzereport.
    \u4f18\u5148\u5c1d\u8bd5\u6309\u4e3b\u952e ID (\u6574\u6570)query; \u82e5parameter\u4e0d\u662f\u5408\u6cd5\u6574\u6570\u5219\u6309 query_id query.

    Args:
        record_id: analyzehistory records\u4e3b\u952e ID (\u6574\u6570)or query_id (\u5b57\u7b26\u4e32)
        db_manager: \u6570\u636elibrary\u7ba1\u7406\u5668\u4f9d\u8d56

    Returns:
        AnalysisReport: \u5b8c\u6574analyzereport

    Raises:
        HTTPException: 404 - reportdoes not exist
    """
    try:
        service = HistoryService(db_manager)

        # Try integer ID first, fall back to query_id string lookup
        result = service.resolve_and_get_detail(record_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"\u672a\u627e\u5230 id/query_id={record_id} \u7684analyze\u8bb0\u5f55"
                }
            )

        # \u4ece context_snapshot Medium\u63d0\u53d6priceinfo
        # \u6ce8\u610f: \u4f7f\u7528 `is None` \u800c\u975e `or`; \u907f\u514d\u628a 0.0 (\u5e73\u76d8)\u8bef\u5224\u4e3a\u7f3a\u5931\u503c；
        # \u540c\u65f6\u4e0d\u6df7\u7528 `change_60d` (60 \u65e5\u7d2f\u8ba1change\u5e45)\u4f5c\u4e3a\u65e5\u5185 change_pct \u7684\u515c\u5e95.
        context_snapshot = result.get("context_snapshot")
        analysis_context_pack_overview = extract_analysis_context_pack_overview(context_snapshot)
        market_phase_summary = result.get("market_phase_summary")
        if market_phase_summary is None:
            market_phase_summary = extract_market_phase_summary(context_snapshot)
        api_context_snapshot = sanitize_context_snapshot_for_api(context_snapshot)
        realtime_fields = extract_realtime_detail_fields(context_snapshot)
        current_price = realtime_fields.get("current_price")
        change_pct = realtime_fields.get("change_pct")

        raw_result = result.get("raw_result")
        if not isinstance(raw_result, dict):
            raw_result = {}
        report_language = normalize_report_language(
            result.get("report_language")
            or raw_result.get("report_language")
            or (
                context_snapshot.get("report_language")
                if isinstance(context_snapshot, dict)
                else None
            )
        )
        stock_name = get_localized_stock_name(
            result.get("stock_name"),
            result.get("stock_code", ""),
            report_language,
        )

        # \u6784\u5efa\u54cd\u5e94\u6a21\u578b
        meta = ReportMeta(
            id=result.get("id"),
            query_id=result.get("query_id", ""),
            stock_code=result.get("stock_code", ""),
            stock_name=stock_name,
            report_type=result.get("report_type"),
            report_language=report_language,
            created_at=result.get("created_at"),
            current_price=current_price,
            change_pct=change_pct,
            model_used=normalize_model_used(result.get("model_used")),
            market_phase_summary=market_phase_summary,
        )

        summary = ReportSummary(
            analysis_summary=result.get("analysis_summary"),
            operation_advice=localize_operation_advice(
                result.get("operation_advice"),
                report_language,
            ),
            action=result.get("action"),
            action_label=result.get("action_label"),
            trend_prediction=localize_trend_prediction(
                result.get("trend_prediction"),
                report_language,
            ),
            sentiment_score=result.get("sentiment_score"),
            sentiment_label=(
                get_sentiment_label(result.get("sentiment_score"), report_language)
                if result.get("sentiment_score") is not None
                else result.get("sentiment_label")
            )
        )

        strategy = ReportStrategy(
            ideal_buy=result.get("ideal_buy"),
            secondary_buy=result.get("secondary_buy"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit")
        )

        fallback_fundamental = db_manager.get_latest_fundamental_snapshot(
            query_id=result.get("query_id", ""),
            code=result.get("storage_stock_code") or result.get("stock_code", ""),
        )
        extracted_fundamental = extract_fundamental_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )
        extracted_boards = extract_board_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )

        details = ReportDetails(
            news_content=result.get("news_content"),
            raw_result=result.get("raw_result"),
            context_snapshot=api_context_snapshot,
            analysis_context_pack_overview=analysis_context_pack_overview,
            financial_report=extracted_fundamental.get("financial_report"),
            dividend_metrics=extracted_fundamental.get("dividend_metrics"),
            belong_boards=extracted_boards.get("belong_boards"),
            sector_rankings=extracted_boards.get("sector_rankings"),
            concept_rankings=extracted_boards.get("concept_rankings"),
        )

        return AnalysisReport(
            meta=meta,
            summary=summary,
            strategy=strategy,
            details=details
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"queryhistory\u8be6\u60c5failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"queryhistory\u8be6\u60c5failed: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/diagnostics",
    response_model=RunDiagnosticSummaryResponse,
    responses={
        200: {"description": "\u8fd0\u884c\u8bca\u65adsummary"},
        404: {"description": "reportdoes not exist", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6historyreport\u8fd0\u884c\u8bca\u65adsummary",
    description="\u6839\u636eanalyzehistory records ID or query_id \u83b7\u53d6user\u53ef\u8bfb\u8bca\u65adsummary\u548c\u8131\u654f\u590d\u5236\u6587\u672c.",
)
def get_history_diagnostics(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunDiagnosticSummaryResponse:
    """
    \u83b7\u53d6historyreport\u8fd0\u884c\u8bca\u65adsummary.
    """
    try:
        service = HistoryService(db_manager)
        summary = service.resolve_and_get_diagnostics(record_id)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"\u672a\u627e\u5230 id/query_id={record_id} \u7684analyze\u8bb0\u5f55",
                },
            )
        return RunDiagnosticSummaryResponse.model_validate(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"query\u8fd0\u884c\u8bca\u65adsummaryfailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"query\u8fd0\u884c\u8bca\u65adsummaryfailed: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/flow",
    response_model=RunFlowSnapshot,
    responses={
        200: {"description": "\u8fd0\u884c\u6d41\u5feb\u7167"},
        404: {"description": "reportdoes not exist", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6historyreport\u8fd0\u884c\u6d41",
    description="\u6839\u636eanalyzehistory records ID or query_id \u83b7\u53d6\u6570\u636e\u6d41/info\u6d41\u5feb\u7167.",
)
def get_history_run_flow(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunFlowSnapshot:
    """
    \u83b7\u53d6historyreport\u8fd0\u884c\u6d41.
    """
    try:
        service = HistoryService(db_manager)
        snapshot = service.resolve_and_get_run_flow(record_id)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"\u672a\u627e\u5230 id/query_id={record_id} \u7684analyze\u8bb0\u5f55",
                },
            )
        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"query\u8fd0\u884c\u6d41\u5feb\u7167failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"query\u8fd0\u884c\u6d41\u5feb\u7167failed: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/news",
    response_model=NewsIntelResponse,
    responses={
        200: {"description": "news\u60c5\u62a5\u5217\u8868"},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6historyreport\u5173\u8054news",
    description="\u6839\u636eanalyzehistory records ID \u83b7\u53d6\u5173\u8054\u7684news\u60c5\u62a5\u5217\u8868 (\u4e3a\u7a7a\u4e5f\u8fd4\u56de 200)"
)
def get_history_news(
    record_id: str,
    limit: int = Query(20, ge=1, le=100, description="\u8fd4\u56decountlimit"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> NewsIntelResponse:
    """
    \u83b7\u53d6historyreport\u5173\u8054news

    \u6839\u636eanalyzehistory records ID or query_id \u83b7\u53d6\u5173\u8054\u7684news\u60c5\u62a5\u5217\u8868.
    \u5728\u5185\u90e8\u5b8c\u6210 record_id → query_id \u7684\u89e3\u6790.

    Args:
        record_id: analyzehistory records\u4e3b\u952e ID (\u6574\u6570)or query_id (\u5b57\u7b26\u4e32)
        limit: \u8fd4\u56decountlimit
        db_manager: \u6570\u636elibrary\u7ba1\u7406\u5668\u4f9d\u8d56

    Returns:
        NewsIntelResponse: news\u60c5\u62a5\u5217\u8868
    """
    try:
        service = HistoryService(db_manager)
        items = service.resolve_and_get_news(record_id=record_id, limit=limit)

        response_items = [
            NewsIntelItem(
                title=item.get("title", ""),
                snippet=item.get("snippet"),
                url=item.get("url", "")
            )
            for item in items
        ]

        return NewsIntelResponse(
            total=len(response_items),
            items=response_items
        )

    except Exception as e:
        logger.error(f"querynews\u60c5\u62a5failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"querynews\u60c5\u62a5failed: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/markdown",
    response_model=MarkdownReportResponse,
    responses={
        200: {"description": "Markdown \u683c\u5f0freport"},
        404: {"description": "reportdoes not exist", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6historyreport Markdown \u683c\u5f0f",
    description="\u6839\u636eanalyzehistory records ID \u83b7\u53d6 Markdown \u683c\u5f0f\u7684\u5b8c\u6574analyzereport"
)
def get_history_markdown(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> MarkdownReportResponse:
    """
    \u83b7\u53d6historyreport\u7684 Markdown \u683c\u5f0f\u5185\u5bb9

    \u6839\u636eanalyzehistory records ID or query_id \u751f\u6210\u4e0e\u63a8\u9001\u901a\u77e5\u683c\u5f0f\u4e00\u81f4\u7684 Markdown report.

    Args:
        record_id: analyzehistory records\u4e3b\u952e ID (\u6574\u6570)or query_id (\u5b57\u7b26\u4e32)
        db_manager: \u6570\u636elibrary\u7ba1\u7406\u5668\u4f9d\u8d56

    Returns:
        MarkdownReportResponse: Markdown \u683c\u5f0f\u7684\u5b8c\u6574report

    Raises:
        HTTPException: 404 - reportdoes not exist
        HTTPException: 500 - report\u751f\u6210failed (\u670d\u52a1\u5668\u5185\u90e8error)
    """
    service = HistoryService(db_manager)

    try:
        markdown_content = service.get_markdown_report(record_id)
    except MarkdownReportGenerationError as e:
        logger.error(f"Markdown report generation failed for {record_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": f"\u751f\u6210 Markdown reportfailed: {e.message}"
            }
        )
    except Exception as e:
        logger.error(f"\u83b7\u53d6 Markdown reportfailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"\u83b7\u53d6 Markdown reportfailed: {str(e)}"
            }
        )

    if markdown_content is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"\u672a\u627e\u5230 id/query_id={record_id} \u7684analyze\u8bb0\u5f55"
            }
        )

    return MarkdownReportResponse(content=markdown_content)
