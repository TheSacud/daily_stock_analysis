# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestResultItem,
    BacktestResultsResponse,
    PerformanceMetrics,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

BacktestAnalysisPhaseQuery = Literal["premarket", "intraday", "postmarket", "unknown"]


def _validate_analysis_date_range(
    analysis_date_from: Optional[date],
    analysis_date_to: Optional[date],
) -> None:
    if analysis_date_from and analysis_date_to and analysis_date_from > analysis_date_to:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_params",
                "message": "analysis_date_from cannot be after analysis_date_to",
            },
        )


@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "backtestcompleted"},
        400: {"description": "requestinvalid parameters", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u89e6\u53d1backtest",
    description="\u5bf9historyanalyze\u8bb0\u5f55\u8fdb\u884cbacktest\u8bc4\u4f30; \u5e76\u5199\u5165 backtest_results/backtest_summaries",
)
def run_backtest(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunResponse:
    try:
        _validate_analysis_date_range(request.analysis_date_from, request.analysis_date_to)
        service = BacktestService(db_manager)
        stats = service.run_backtest(
            code=request.code,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            analysis_date_from=request.analysis_date_from,
            analysis_date_to=request.analysis_date_to,
            limit=request.limit,
        )
        return BacktestRunResponse(**stats)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"backtestexecution failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"backtestexecution failed: {str(exc)}"},
        )


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "backtestresult\u5217\u8868"},
        400: {"description": "requestinvalid parameters", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6backtestresult",
    description="\u5206\u9875\u83b7\u53d6backtestresult; \u652f\u6301\u6309stock code\u8fc7\u6ee4",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="stock code\u7b5b\u9009"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="\u8bc4\u4f30\u7a97\u53e3\u8fc7\u6ee4"),
    analysis_date_from: Optional[date] = Query(None, description="analyzedate\u8d77\u59cb (\u542b)"),
    analysis_date_to: Optional[date] = Query(None, description="analyzedate\u7ed3\u675f (\u542b)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="analyze\u9636\u6bb5\u8fc7\u6ee4: premarket/intraday/postmarket/unknown"),
    page: int = Query(1, ge=1, description="\u9875\u7801"),
    limit: int = Query(20, ge=1, le=200, description="\u6bcf\u9875count"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        data = service.get_recent_evaluations(
            code=code,
            eval_window_days=eval_window_days,
            limit=limit,
            page=page,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(
            total=int(data.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"querybacktestresultfailed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"querybacktestresultfailed: {str(exc)}"},
        )


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "\u6574\u4f53backtest\u8868\u73b0"},
        400: {"description": "requestinvalid parameters", "model": ErrorResponse},
        404: {"description": "\u65e0backtest\u6c47\u603b", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6\u6574\u4f53backtest\u8868\u73b0",
)
def get_overall_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="\u8bc4\u4f30\u7a97\u53e3\u8fc7\u6ee4"),
    analysis_date_from: Optional[date] = Query(None, description="analyzedate\u8d77\u59cb (\u542b)"),
    analysis_date_to: Optional[date] = Query(None, description="analyzedate\u7ed3\u675f (\u542b)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="analyze\u9636\u6bb5\u8fc7\u6ee4: premarket/intraday/postmarket/unknown"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="overall",
            code=None,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "\u672a\u627e\u5230\u6574\u4f53backtest\u6c47\u603b"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"queryoverall performancefailed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"queryoverall performancefailed: {str(exc)}"},
        )


@router.get(
    "/performance/{code}",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "\u5355\u80a1backtest\u8868\u73b0"},
        400: {"description": "requestinvalid parameters", "model": ErrorResponse},
        404: {"description": "\u65e0backtest\u6c47\u603b", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6\u5355\u80a1backtest\u8868\u73b0",
)
def get_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="\u8bc4\u4f30\u7a97\u53e3\u8fc7\u6ee4"),
    analysis_date_from: Optional[date] = Query(None, description="analyzedate\u8d77\u59cb (\u542b)"),
    analysis_date_to: Optional[date] = Query(None, description="analyzedate\u7ed3\u675f (\u542b)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="analyze\u9636\u6bb5\u8fc7\u6ee4: premarket/intraday/postmarket/unknown"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="stock",
            code=code,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"\u672a\u627e\u5230 {code} \u7684backtest\u6c47\u603b"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"querysingle-stock performancefailed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"querysingle-stock performancefailed: {str(exc)}"},
        )
