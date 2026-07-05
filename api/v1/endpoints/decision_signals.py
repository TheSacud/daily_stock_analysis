# -*- coding: utf-8 -*-
"""DecisionSignal API endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyCookie

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.decision_signals import (
    DecisionSignalCreateRequest,
    DecisionSignalFeedbackItem,
    DecisionSignalFeedbackRequest,
    DecisionSignalItem,
    DecisionSignalListResponse,
    DecisionSignalMutationResponse,
    DecisionSignalOutcomeListResponse,
    DecisionSignalOutcomeRunRequest,
    DecisionSignalOutcomeRunResponse,
    DecisionSignalOutcomeStatsResponse,
    DecisionSignalReassessRequest,
    DecisionSignalReassessResponse,
    DecisionSignalStatusUpdateRequest,
)
from src.auth import COOKIE_NAME
from src.services.decision_signal_service import (
    DecisionSignalNotFoundError,
    DecisionSignalService,
    DecisionSignalStorageError,
)
from src.services.decision_signal_outcome_service import DecisionSignalOutcomeService
from src.services.decision_signal_reassess_service import (
    DecisionSignalReassessService,
    DecisionSignalReassessUnsupportedOperationError,
    DecisionSignalSourceReportNotFoundError,
    DecisionSignalUnsupportedReportSnapshotError,
    DecisionSignalUnsupportedReportTypeError,
)


logger = logging.getLogger(__name__)

admin_session_cookie = APIKeyCookie(
    name=COOKIE_NAME,
    scheme_name="AdminSessionCookie",
    auto_error=False,
)
router = APIRouter(dependencies=[Security(admin_session_cookie)])

AUTH_RESPONSE = {
    401: {
        "model": ErrorResponse,
        "description": "\u672a\u767b\u5f55or\u7ba1\u7406\u5458conversation\u65e0\u6548 (ADMIN_AUTH_ENABLED=true \u65f6)",
    },
}


def _bad_request(exc: Exception, *, error: str = "validation_error") -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": error, "message": str(exc)},
    )


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": str(exc)},
    )


def _error(status_code: int, exc: Exception, *, error: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": str(exc)},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": message},
    )


@router.post(
    "",
    response_model=DecisionSignalMutationResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "request\u5b57\u6bb5\u975e\u6cd5"},
        422: {"model": ErrorResponse, "description": "request\u4f53or\u8def\u5f84parametervalidation failed"},
        500: {"model": ErrorResponse, "description": "create failed"},
    },
    summary="\u521b\u5efaor\u53bb\u91cd\u51b3\u7b56\u4fe1\u53f7",
    description=(
        "\u663e\u5f0f\u5199\u5165 DecisionSignal.\u672a\u4f20 horizon/expires_at \u65f6\u7531\u670d\u52a1\u8865default\u751f\u547d\u5468\u671f；"
        "\u547dMedium\u540c\u6e90\u53bb\u91cd\u952eor\u7a84 relaxed \u53bb\u91cd\u65f6\u8fd4\u56de\u5df2\u6709\u8bb0\u5f55\u548c created=false；"
        "active \u65b0\u5efaor expired \u7eed\u671f\u4f1a\u5931\u6548\u540c\u80a1\u65e7 active \u76f8\u53cd\u4fe1\u53f7; "
        "active duplicate retry \u4e5f\u4f1a\u91cd\u8dd1\u8be5\u4fee\u590d；\u666e\u901a\u65e7 duplicate/replay \u4e0d\u4f5c\u4e3a\u65b0\u7684\u6fc0\u6d3b\u4e8b\u4ef6；"
        "\u4e0d\u4fdd\u8bc1\u5e76\u53d1\u7edd\u5bf9\u5e42\u7b49."
    ),
    operation_id="createDecisionSignal",
)
def create_signal(request: DecisionSignalCreateRequest) -> DecisionSignalMutationResponse:
    service = DecisionSignalService()
    try:
        payload = request.model_dump(exclude_unset=True)
        return DecisionSignalMutationResponse(**service.create_signal(payload))
    except DecisionSignalStorageError as exc:
        raise _internal_error("Create decision signal failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create decision signal failed", exc)


@router.get(
    "",
    response_model=DecisionSignalListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "queryparameter\u975e\u6cd5"},
        422: {"model": ErrorResponse, "description": "queryparametervalidation failed"},
        500: {"model": ErrorResponse, "description": "query failed"},
    },
    summary="query\u51b3\u7b56\u4fe1\u53f7\u5217\u8868",
    description=(
        "\u5206\u9875query DecisionSignal；\u8bfb\u53d6\u524d\u4f1a\u61d2\u8fc7\u671f\u5df2\u5230 expires_at \u7684 active \u4fe1\u53f7."
        "\u5f53 source_type=analysis \u4e14\u53ea\u4f20 source_report_id query\u65f6; \u82e5\u65e0\u547dMedium\u4fe1\u53f7\u4f1a\u5c1d\u8bd5\u57fa\u4e8e\u8be5historyreport\u4e00\u6b21\u61d2\u56de\u586b "
        " (\u4ec5\u9996\u6b21\u547dMedium\u5217\u8868\u573a\u666f; \u4e14\u8be5\u7cbe\u786equery\u4f1a\u89e6\u53d1history\u51b3\u7b56\u4fe1\u53f7\u56de\u586b\u5199\u5165; \u5c5e\u4e8e read-with-write \u884c\u4e3a；"
        "\u4e0d\u5f71\u54cdother\u5206\u9875\u5217\u8868\u7b5b\u9009parameter\u573a\u666f)."
        "holding_only=true \u53ea\u8bfb\u53d6 active \u8d26\u6237\u7684 portfolio_positions cache\u6301\u4ed3; \u4e0d\u89e6\u53d1 portfolio snapshot replay."
    ),
    operation_id="listDecisionSignals",
)
def list_signals(
    market: Optional[str] = Query(None, description="Optional market filter: cn/hk/us/jp/kr/tw"),
    stock_code: Optional[str] = Query(None, description="Optional stock code filter"),
    action: Optional[str] = Query(None, description="Optional decision action filter"),
    market_phase: Optional[str] = Query(None, description="Optional market phase filter"),
    source_type: Optional[str] = Query(None, description="Optional source type filter"),
    source_report_id: Optional[int] = Query(None, description="Optional source report id filter"),
    trace_id: Optional[str] = Query(None, description="Optional trace id filter"),
    trigger_source: Optional[str] = Query(None, description="Optional trigger source filter"),
    status: Optional[str] = Query(None, description="Optional status filter"),
    created_from: Optional[str] = Query(None, description="Inclusive created_at lower bound"),
    created_to: Optional[str] = Query(None, description="Inclusive created_at upper bound"),
    expires_from: Optional[str] = Query(None, description="Inclusive expires_at lower bound"),
    expires_to: Optional[str] = Query(None, description="Inclusive expires_at upper bound"),
    holding_only: bool = Query(False, description="Filter to active cached portfolio holdings only"),
    account_id: Optional[int] = Query(
        None,
        description="Optional active portfolio account id for holding_only",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DecisionSignalListResponse:
    service = DecisionSignalService()
    try:
        return DecisionSignalListResponse(
            **service.list_signals(
                market=market,
                stock_code=stock_code,
                action=action,
                market_phase=market_phase,
                source_type=source_type,
                source_report_id=source_report_id,
                trace_id=trace_id,
                trigger_source=trigger_source,
                status=status,
                created_from=created_from,
                created_to=created_to,
                expires_from=expires_from,
                expires_to=expires_to,
                holding_only=holding_only,
                account_id=account_id,
                page=page,
                page_size=page_size,
            )
        )
    except DecisionSignalStorageError as exc:
        raise _internal_error("List decision signals failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List decision signals failed", exc)


@router.post(
    "/outcomes/run",
    response_model=DecisionSignalOutcomeRunResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "request\u5b57\u6bb5\u975e\u6cd5"},
        404: {"model": ErrorResponse, "description": "\u4fe1\u53f7does not exist"},
        422: {"model": ErrorResponse, "description": "request\u4f53validation failed"},
        500: {"model": ErrorResponse, "description": "\u540e\u9a8c\u8ba1\u7b97failed"},
    },
    summary="\u89e6\u53d1\u51b3\u7b56\u4fe1\u53f7\u540e\u9a8c\u8bc4\u4f30",
    description=(
        "\u663e\u5f0f\u89e6\u53d1 signal-level outcome \u8ba1\u7b97；defaultskipping completed \u548c\u7ec8\u6001 unable; "
        "\u4f46\u4f1a\u91cd\u7b97\u7f3a\u5c11\u884c\u60c5\u6570\u636e\u7b49\u53ef\u6062\u590d unable；force=true \u4f1a\u91cd\u7b97\u5e76\u8986\u76d6\u540c\u4e00 "
        "signal_id+horizon+engine_version."
    ),
    operation_id="runDecisionSignalOutcomes",
)
def run_outcomes(request: DecisionSignalOutcomeRunRequest) -> DecisionSignalOutcomeRunResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeRunResponse(
            **service.run_outcomes(
                signal_id=request.signal_id,
                horizons=request.horizons,
                force=request.force,
                market=request.market,
                stock_code=request.stock_code,
                action=request.action,
                source_type=request.source_type,
                status=request.status,
                limit=request.limit,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Run decision signal outcomes failed", exc)


@router.get(
    "/outcomes",
    response_model=DecisionSignalOutcomeListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "queryparameter\u975e\u6cd5"},
        422: {"model": ErrorResponse, "description": "queryparametervalidation failed"},
        500: {"model": ErrorResponse, "description": "query failed"},
    },
    summary="query\u51b3\u7b56\u4fe1\u53f7\u540e\u9a8cresult",
    description="\u5206\u9875query signal-level outcome；default\u53eacheck\u5f53\u524d signal \u540e\u9a8c engine_version.",
    operation_id="listDecisionSignalOutcomes",
)
def list_outcomes(
    signal_id: Optional[int] = Query(None, gt=0),
    horizon: Optional[str] = Query(None),
    engine_version: Optional[str] = Query(None),
    eval_status: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DecisionSignalOutcomeListResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeListResponse(
            **service.list_outcomes(
                signal_id=signal_id,
                horizon=horizon,
                engine_version=engine_version,
                eval_status=eval_status,
                outcome=outcome,
                page=page,
                page_size=page_size,
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List decision signal outcomes failed", exc)


@router.get(
    "/outcomes/stats",
    response_model=DecisionSignalOutcomeStatsResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "queryparameter\u975e\u6cd5"},
        422: {"model": ErrorResponse, "description": "queryparametervalidation failed"},
        500: {"model": ErrorResponse, "description": "\u7edf\u8ba1failed"},
    },
    summary="query\u51b3\u7b56\u4fe1\u53f7\u540e\u9a8c\u7edf\u8ba1",
    description="default\u7edf\u8ba1\u5f53\u524d engine_version; \u4e14\u6392\u9664 archived \u4fe1\u53f7.",
    operation_id="getDecisionSignalOutcomeStats",
)
def get_outcome_stats(
    horizons: Optional[List[str]] = Query(None),
    engine_version: Optional[str] = Query(None),
    statuses: Optional[List[str]] = Query(None),
) -> DecisionSignalOutcomeStatsResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeStatsResponse(
            **service.get_stats(
                horizons=horizons,
                engine_version=engine_version,
                statuses=statuses,
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal outcome stats failed", exc)


@router.post(
    "/reassess",
    response_model=DecisionSignalReassessResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "\u91cd\u8bc4\u4f30requestdoes not supportorhistoryreport\u4e0d\u9002\u7528"},
        404: {"model": ErrorResponse, "description": "sourcehistoryreportdoes not exist"},
        422: {"model": ErrorResponse, "description": "request\u4f53validation failed"},
        500: {"model": ErrorResponse, "description": "\u91cd\u8bc4\u4f30failed"},
    },
    summary="\u9884\u89c8\u51b3\u7b56\u98ce\u683c\u91cd\u8bc4\u4f30",
    description=(
        "\u57fa\u4e8e source_report_id \u5bf9\u5e94\u7684\u6301\u4e45\u5316historyreport\u5feb\u7167\u751f\u6210 decision_profile preview；"
        "P3a \u4ec5\u652f\u6301 persist=false; \u4e0d\u5199\u5165 DecisionSignal."
    ),
    operation_id="reassessDecisionSignalPreview",
)
def reassess_signal(request: DecisionSignalReassessRequest) -> DecisionSignalReassessResponse:
    if request.persist:
        raise _error(
            400,
            DecisionSignalReassessUnsupportedOperationError(
                "Persisting reassessed decision_profile signals requires decision_profile "
                "to be promoted to a first-class field."
            ),
            error="unsupported_operation",
        )

    service = DecisionSignalReassessService()
    try:
        return DecisionSignalReassessResponse(
            **service.reassess(
                source_report_id=request.source_report_id,
                decision_profile=request.decision_profile,
                persist=request.persist,
            )
        )
    except DecisionSignalSourceReportNotFoundError as exc:
        raise _error(404, exc, error="source_report_not_found")
    except DecisionSignalUnsupportedReportTypeError as exc:
        raise _error(400, exc, error="unsupported_report_type")
    except DecisionSignalUnsupportedReportSnapshotError as exc:
        raise _error(400, exc, error="unsupported_report_snapshot")
    except DecisionSignalReassessUnsupportedOperationError as exc:
        raise _error(400, exc, error="unsupported_operation")
    except Exception as exc:
        raise _internal_error("Reassess decision signal preview failed", exc)


@router.get(
    "/latest/{stock_code}",
    response_model=DecisionSignalListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "requestparameter\u975e\u6cd5"},
        422: {"model": ErrorResponse, "description": "\u8def\u5f84orqueryparametervalidation failed"},
        500: {"model": ErrorResponse, "description": "query failed"},
    },
    summary="query\u80a1\u7968\u6700\u65b0 active \u51b3\u7b56\u4fe1\u53f7",
    description="\u8fd4\u56de\u6307\u5b9a\u80a1\u7968\u6700\u65b0 active \u4fe1\u53f7\u5217\u8868；\u8bfb\u53d6\u524d\u4f1a\u6267\u884c\u61d2\u8fc7\u671f.",
    operation_id="getLatestDecisionSignals",
)
def get_latest_active(
    stock_code: str,
    market: Optional[str] = Query(None, description="Optional market filter: cn/hk/us/jp/kr/tw"),
    limit: int = Query(1, ge=1, le=100),
) -> DecisionSignalListResponse:
    service = DecisionSignalService()
    try:
        return DecisionSignalListResponse(
            **service.get_latest_active(
                stock_code=stock_code,
                market=market,
                limit=limit,
            )
        )
    except DecisionSignalStorageError as exc:
        raise _internal_error("Get latest decision signals failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get latest decision signals failed", exc)


@router.get(
    "/{signal_id}",
    response_model=DecisionSignalItem,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "\u4fe1\u53f7does not exist"},
        422: {"model": ErrorResponse, "description": "\u8def\u5f84parametervalidation failed"},
        500: {"model": ErrorResponse, "description": "query failed"},
    },
    summary="query\u5355\u6761\u51b3\u7b56\u4fe1\u53f7",
    description="\u6309 ID query\u5355\u6761 DecisionSignal；\u8bfb\u53d6\u524d\u4f1a\u6267\u884c\u61d2\u8fc7\u671f.",
    operation_id="getDecisionSignal",
)
def get_signal(signal_id: int) -> DecisionSignalItem:
    service = DecisionSignalService()
    try:
        return DecisionSignalItem(**service.get_signal(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except DecisionSignalStorageError as exc:
        raise _internal_error("Get decision signal failed", exc)
    except Exception as exc:
        raise _internal_error("Get decision signal failed", exc)


@router.get(
    "/{signal_id}/outcomes",
    response_model=DecisionSignalOutcomeListResponse,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "\u4fe1\u53f7does not exist"},
        422: {"model": ErrorResponse, "description": "\u8def\u5f84parametervalidation failed"},
        500: {"model": ErrorResponse, "description": "query failed"},
    },
    summary="query\u5355\u4e2a\u51b3\u7b56\u4fe1\u53f7\u540e\u9a8cresult",
    description="\u8fd4\u56de\u6307\u5b9a signal_id \u5728\u5f53\u524d engine_version \u4e0b\u7684\u540e\u9a8cresult.",
    operation_id="listDecisionSignalOutcomesBySignal",
)
def list_signal_outcomes(signal_id: int) -> DecisionSignalOutcomeListResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeListResponse(**service.list_signal_outcomes(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except Exception as exc:
        raise _internal_error("List decision signal outcomes failed", exc)


@router.get(
    "/{signal_id}/feedback",
    response_model=DecisionSignalFeedbackItem,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "\u4fe1\u53f7does not exist"},
        422: {"model": ErrorResponse, "description": "\u8def\u5f84parametervalidation failed"},
        500: {"model": ErrorResponse, "description": "query failed"},
    },
    summary="query\u51b3\u7b56\u4fe1\u53f7user\u53cd\u9988",
    description="\u6ca1\u6709\u53cd\u9988\u65f6\u8fd4\u56de feedback_value=null；\u4fe1\u53f7does not exist\u65f6\u8fd4\u56de 404.",
    operation_id="getDecisionSignalFeedback",
)
def get_feedback(signal_id: int) -> DecisionSignalFeedbackItem:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalFeedbackItem(**service.get_feedback(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal feedback failed", exc)


@router.put(
    "/{signal_id}/feedback",
    response_model=DecisionSignalFeedbackItem,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "request\u5b57\u6bb5\u975e\u6cd5"},
        404: {"model": ErrorResponse, "description": "\u4fe1\u53f7does not exist"},
        422: {"model": ErrorResponse, "description": "request\u4f53or\u8def\u5f84parametervalidation failed"},
        500: {"model": ErrorResponse, "description": "update failed"},
    },
    summary="\u5199\u5165\u51b3\u7b56\u4fe1\u53f7user\u53cd\u9988",
    description="\u6309 signal_id upsert \u6700\u65b0 useful/not_useful \u53cd\u9988.",
    operation_id="putDecisionSignalFeedback",
)
def put_feedback(signal_id: int, request: DecisionSignalFeedbackRequest) -> DecisionSignalFeedbackItem:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalFeedbackItem(
            **service.put_feedback(
                signal_id,
                feedback_value=request.feedback_value,
                reason_code=request.reason_code,
                note=request.note,
                source=request.source,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Put decision signal feedback failed", exc)


@router.patch(
    "/{signal_id}/status",
    response_model=DecisionSignalItem,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "status\u975e\u6cd5"},
        404: {"model": ErrorResponse, "description": "\u4fe1\u53f7does not exist"},
        422: {"model": ErrorResponse, "description": "request\u4f53or\u8def\u5f84parametervalidation failed"},
        500: {"model": ErrorResponse, "description": "update failed"},
    },
    summary="\u66f4\u65b0\u51b3\u7b56\u4fe1\u53f7status",
    description=(
        "\u53ea\u66f4\u65b0\u5408\u6cd5status\u548coptional metadata；\u4f20\u5165 metadata \u65f6\u6309\u6574\u5305\u66ff\u6362\u4fdd\u5b58."
        "expired/invalidated/closed/archived \u7b49 terminal status\u4e0d\u80fd\u76f4\u63a5 PATCH \u56de active."
    ),
    operation_id="updateDecisionSignalStatus",
)
def update_status(signal_id: int, request: DecisionSignalStatusUpdateRequest) -> DecisionSignalItem:
    service = DecisionSignalService()
    try:
        return DecisionSignalItem(
            **service.update_status(
                signal_id,
                status=request.status,
                metadata=request.metadata,
                replace_metadata="metadata" in request.model_fields_set,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except DecisionSignalStorageError as exc:
        raise _internal_error("Update decision signal status failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update decision signal status failed", exc)
