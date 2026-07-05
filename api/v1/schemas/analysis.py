# -*- coding: utf-8 -*-
"""
===================================
analyze\u76f8\u5173\u6a21\u578b
===================================

\u804c\u8d23:
1. \u5b9a\u4e49analyzerequest\u548c\u54cd\u5e94\u6a21\u578b
2. \u5b9a\u4e49taskstatus\u6a21\u578b
3. \u5b9a\u4e49\u5f02\u6b65taskqueue\u76f8\u5173\u6a21\u578b
"""

from typing import Optional, List, Any, Literal
from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN


class TaskStatusEnum(str, Enum):
    """taskstatus\u679a\u4e3e"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


AnalysisPhase = Literal["auto", "premarket", "intraday", "postmarket"]


class AnalyzeRequest(BaseModel):
    """Analysis request parameters"""

    stock_code: Optional[str] = Field(
        None,
        description="\u5355\u53eastock code",
        json_schema_extra={"example": "600519"},
    )
    stock_codes: Optional[List[str]] = Field(
        None,
        description="\u591a\u53eastock code (\u4e0e stock_code \u4e8c\u9009\u4e00)",
        json_schema_extra={"example": ["600519", "000858"]},
    )
    report_type: str = Field(
        "detailed",
        description="report type: simple(\u7cbe\u7b80) / detailed(\u5b8c\u6574) / full(\u5b8c\u6574) / brief(\u7b80\u6d01)",
        pattern="^(simple|detailed|full|brief)$",
    )
    force_refresh: bool = Field(
        False,
        description="\u662f\u5426\u5f3a\u5236\u5237\u65b0 (\u5ffd\u7565cache)"
    )
    async_mode: bool = Field(
        False,
        description="\u662f\u5426\u4f7f\u7528\u5f02\u6b65mode"
    )
    analysis_phase: AnalysisPhase = Field(
        "auto",
        description="analyze\u9636\u6bb5\u8986\u76d6: auto(\u81ea\u52a8\u63a8\u65ad) / premarket(\u76d8\u524d) / intraday(\u76d8Medium) / postmarket(\u76d8\u540e)",
    )
    stock_name: Optional[str] = Field(
        None,
        description="user\u9009Medium\u7684stock name (\u81ea\u52a8\u8865\u5168\u65f6\u63d0\u4f9b)",
        json_schema_extra={"example": "\u8d35\u5dde\u8305\u53f0"},
    )
    original_query: Optional[str] = Field(
        None,
        description="user\u539f\u59cb\u8f93\u5165 (\u5982\u8305\u53f0、gzmt、600519)",
        json_schema_extra={"example": "\u8305\u53f0"},
    )
    selection_source: Optional[str] = Field(
        None,
        description="\u80a1\u7968\u9009\u62e9source: manual(\u624b\u52a8\u8f93\u5165) | autocomplete(\u81ea\u52a8\u8865\u5168) | import(\u5bfc\u5165) | image(\u56fe\u7247\u8bc6\u522b)",
        pattern=SELECTION_SOURCE_PATTERN,
        json_schema_extra={"example": "autocomplete"},
    )
    notify: bool = Field(
        True,
        description="\u662f\u5426\u53d1\u9001\u63a8\u9001\u901a\u77e5 (Telegram/WeCom\u7b49)"
    )
    report_language: Optional[Literal["zh", "en", "ko"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="this runanalyzereport\u8f93\u51fa\u8bed\u8a00；\u672a\u4f20\u65f6\u4f7f\u7528\u5168\u5c40 REPORT_LANGUAGE",
    )
    skills: Optional[List[str]] = Field(
        None,
        validation_alias=AliasChoices("skills", "strategies"),
        description="this runanalyze\u4f7f\u7528\u7684strategy skill ID \u5217\u8868；\u517c\u5bb9 legacy strategies \u5b57\u6bb5",
        json_schema_extra={"example": ["bull_trend", "growth_quality"]},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "report_type": "detailed",
            "force_refresh": False,
            "async_mode": False,
            "analysis_phase": "auto",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "original_query": "\u8305\u53f0",
            "selection_source": "autocomplete",
            "notify": True,
            "report_language": "en",
            "skills": ["bull_trend"]
        }
    })


class MarketReviewRequest(BaseModel):
    """Market review trigger parameters."""

    send_notification: bool = Field(
        True,
        description="\u662f\u5426\u5728market review\u5b8c\u6210\u540e\u53d1\u9001\u63a8\u9001\u901a\u77e5",
    )
    report_language: Optional[Literal["zh", "en", "ko"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="this runmarket reviewreport\u8f93\u51fa\u8bed\u8a00；\u672a\u4f20\u65f6\u4f7f\u7528\u5168\u5c40 REPORT_LANGUAGE",
    )


class MarketReviewAccepted(BaseModel):
    """Market review background task accepted response."""

    status: str = Field("accepted", description="\u63d0\u4ea4status")
    message: str = Field(..., description="\u63d0\u793ainfo")
    send_notification: bool = Field(..., description="\u662f\u5426send notification")
    trace_id: Optional[str] = Field(
        None,
        description="this run\u540e\u53f0task\u7684\u8bca\u65ad trace ID",
    )
    task_id: Optional[str] = Field(
        None,
        description="task ID (\u4ec5\u5f53task\u5b9e\u9645\u63d0\u4ea4\u65f6\u8fd4\u56de)",
    )


class AnalysisResultResponse(BaseModel):
    """analysis result\u54cd\u5e94\u6a21\u578b"""

    query_id: str = Field(..., description="analyze\u8bb0\u5f55\u552f\u4e00\u6807\u8bc6")
    trace_id: Optional[str] = Field(None, description="\u8bca\u65ad trace ID")
    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    report: Optional[Any] = Field(None, description="analyzereport")
    diagnostic_summary: Optional[Any] = Field(None, description="\u8fd0\u884c\u8bca\u65adsummary")
    created_at: str = Field(..., description="\u521b\u5efa\u65f6\u95f4")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query_id": "abc123def456",
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "report": {
                "summary": {
                    "sentiment_score": 75,
                    "operation_advice": "\u6301\u6709"
                }
            },
            "created_at": "2024-01-01T12:00:00"
        }
    })


class TaskAccepted(BaseModel):
    """\u5f02\u6b65task\u63a5\u53d7\u54cd\u5e94"""

    task_id: str = Field(..., description="task ID; \u7528\u4e8equerystatus")
    trace_id: Optional[str] = Field(None, description="\u8bca\u65ad trace ID")
    status: str = Field(
        ...,
        description="taskstatus",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="\u63d0\u793ainfo")
    analysis_phase: AnalysisPhase = Field("auto", description="request\u7684analyze\u9636\u6bb5")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "pending",
            "message": "Analysis task accepted",
            "analysis_phase": "auto"
        }
    })


class BatchTaskAcceptedItem(BaseModel):
    """batch\u5f02\u6b65taskMedium\u7684\u5355\u4e2asuccess\u63d0\u4ea4\u9879."""

    task_id: str = Field(..., description="task ID; \u7528\u4e8equerystatus")
    trace_id: Optional[str] = Field(None, description="\u8bca\u65ad trace ID")
    stock_code: str = Field(..., description="stock code")
    status: str = Field(
        ...,
        description="taskstatus",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="\u63d0\u793ainfo")
    analysis_phase: AnalysisPhase = Field("auto", description="request\u7684analyze\u9636\u6bb5")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "stock_code": "600519",
            "status": "pending",
            "message": "analysis taskaddedqueue: 600519",
            "analysis_phase": "auto"
        }
    })


class BatchDuplicateTaskItem(BaseModel):
    """batch\u5f02\u6b65taskMedium\u7684\u91cd\u590d\u63d0\u4ea4\u9879."""

    stock_code: str = Field(..., description="stock code")
    existing_task_id: str = Field(..., description="already exists\u7684task ID")
    message: str = Field(..., description="errorinfo")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "existing_task_id": "task_existing_123",
            "message": "\u80a1\u7968 600519 \u6b63\u5728analyzeMedium (task_id: task_existing_123)"
        }
    })


class BatchTaskAcceptedResponse(BaseModel):
    """batch\u5f02\u6b65task\u63a5\u53d7\u54cd\u5e94."""

    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="success\u63d0\u4ea4\u7684task\u5217\u8868")
    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="\u91cd\u590d\u800cskipping\u7684task\u5217\u8868")
    message: str = Field(..., description="\u6c47\u603binfo")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "accepted": [
                {
                    "task_id": "task_abc123",
                    "stock_code": "600519",
                    "status": "pending",
                    "message": "analysis taskaddedqueue: 600519",
                    "analysis_phase": "auto"
                }
            ],
            "duplicates": [
                {
                    "stock_code": "000858",
                    "existing_task_id": "task_existing_456",
                    "message": "\u80a1\u7968 000858 \u6b63\u5728analyzeMedium (task_id: task_existing_456)"
                }
            ],
            "message": "\u5df2\u63d0\u4ea4 1 \u4e2atask; 1 \u4e2a\u91cd\u590dskipping"
        }
    })


class TaskStatus(BaseModel):
    """Task status model"""

    task_id: str = Field(..., description="task ID")
    trace_id: Optional[str] = Field(None, description="\u8bca\u65ad trace ID")
    status: TaskStatusEnum = Field(
        ...,
        description="taskstatus",
    )
    progress: Optional[int] = Field(
        None,
        description="\u8fdb\u5ea6\u767e\u5206\u6bd4 (0-100)",
        ge=0,
        le=100
    )
    result: Optional[AnalysisResultResponse] = Field(
        None,
        description="analysis result (\u4ec5\u5728 completed \u65f6\u5b58\u5728)"
    )
    market_review_report: Optional[str] = Field(
        None,
        description="market reviewtask\u8fd4\u56de\u7684report\u6587\u672c (market review onlytask)",
    )
    market_review_payload: Optional[Any] = Field(
        None,
        description="Structured market-review payload for API/Web consumers.",
    )
    error: Optional[str] = Field(
        None,
        description="errorinfo (\u4ec5\u5728 failed \u65f6\u5b58\u5728)"
    )
    stock_name: Optional[str] = Field(None, description="stock name")
    original_query: Optional[str] = Field(None, description="user\u539f\u59cb\u8f93\u5165")
    selection_source: Optional[str] = Field(
        None,
        description="\u9009\u62e9source",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: Optional[AnalysisPhase] = Field(
        None,
        description="request\u7684analyze\u9636\u6bb5；\u65e0\u6301\u4e45\u5316\u5b57\u6bb5\u7684history DB fallback \u53ef\u80fd\u4e3a\u7a7a",
    )
    skills: Optional[List[str]] = Field(None, description="this runtask\u4f7f\u7528\u7684strategy skill ID \u5217\u8868")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "completed",
            "progress": 100,
            "result": None,
            "market_review_report": None,
            "error": None,
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "original_query": "\u8305\u53f0",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskInfo(BaseModel):
    """
    Task details model

    Used for task list and SSE event delivery
    """

    task_id: str = Field(..., description="task ID")
    trace_id: Optional[str] = Field(None, description="\u8bca\u65ad trace ID")
    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    status: TaskStatusEnum = Field(..., description="taskstatus")
    progress: int = Field(0, description="\u8fdb\u5ea6\u767e\u5206\u6bd4 (0-100)", ge=0, le=100)
    message: Optional[str] = Field(None, description="status\u6d88\u606f")
    report_type: str = Field("detailed", description="report type")
    created_at: str = Field(..., description="\u521b\u5efa\u65f6\u95f4")
    started_at: Optional[str] = Field(None, description="starting\u65f6\u95f4")
    completed_at: Optional[str] = Field(None, description="\u5b8c\u6210\u65f6\u95f4")
    error: Optional[str] = Field(None, description="errorinfo (\u4ec5\u5728 failed \u65f6\u5b58\u5728)")
    original_query: Optional[str] = Field(None, description="user\u539f\u59cb\u8f93\u5165")
    selection_source: Optional[str] = Field(
        None,
        description="\u9009\u62e9source",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: AnalysisPhase = Field("auto", description="request\u7684analyze\u9636\u6bb5")
    skills: Optional[List[str]] = Field(None, description="this runtask\u4f7f\u7528\u7684strategy skill ID \u5217\u8868")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "abc123def456",
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "status": "processing",
            "progress": 50,
            "message": "\u6b63\u5728analyzeMedium...",
            "report_type": "detailed",
            "created_at": "2026-02-05T10:30:00",
            "started_at": "2026-02-05T10:30:01",
            "completed_at": None,
            "error": None,
            "original_query": "\u8305\u53f0",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskListResponse(BaseModel):
    """task\u5217\u8868\u54cd\u5e94\u6a21\u578b"""

    total: int = Field(..., description="task\u603b\u6570")
    pending: int = Field(..., description="pending\u7684task\u6570")
    processing: int = Field(..., description="\u5904\u7406Medium\u7684task\u6570")
    tasks: List[TaskInfo] = Field(..., description="task\u5217\u8868")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 3,
            "pending": 1,
            "processing": 2,
            "tasks": []
        }
    })


class DuplicateTaskErrorResponse(BaseModel):
    """\u91cd\u590dtaskerror\u54cd\u5e94\u6a21\u578b"""

    error: str = Field("duplicate_task", description="error\u7c7b\u578b")
    message: str = Field(..., description="errorinfo")
    stock_code: str = Field(..., description="stock code")
    existing_task_id: str = Field(..., description="already exists\u7684task ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "duplicate_task",
            "message": "\u80a1\u7968 600519 \u6b63\u5728analyzeMedium",
            "stock_code": "600519",
            "existing_task_id": "abc123def456"
        }
    })
