# -*- coding: utf-8 -*-
"""
===================================
history records\u76f8\u5173\u6a21\u578b
===================================

\u804c\u8d23:
1. \u5b9a\u4e49history records\u5217\u8868\u548c\u8be6\u60c5\u6a21\u578b
2. \u5b9a\u4e49analyzereport\u5b8c\u6574\u6a21\u578b
"""

from typing import Optional, List, Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.v1.schemas.market_phase import MarketPhaseSummary
from src.schemas.decision_action import DecisionAction


class HistoryItem(BaseModel):
    """history recordssummary (\u5217\u8868\u5c55\u793a\u7528)"""

    id: Optional[int] = Field(None, description="analyzehistory records\u4e3b\u952e ID")
    query_id: str = Field(..., description="analyze\u8bb0\u5f55\u5173\u8054 query_id (batchanalyze\u65f6\u91cd\u590d)")
    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    report_type: Optional[str] = Field(None, description="report type")
    trend_prediction: Optional[str] = Field(None, description="\u8d8b\u52bf\u9884\u6d4b")
    analysis_summary: Optional[str] = Field(None, description="analyzesummary")
    sentiment_score: Optional[int] = Field(
        None,
        description="\u60c5\u7eea\u8bc4\u5206 (history\u6570\u636e\u53ef\u80fd\u8d85\u51fa 0-100 \u8303\u56f4; \u8bfb\u53d6\u65f6\u4e0d\u505a\u7ea6\u675f)",
    )
    operation_advice: Optional[str] = Field(None, description="operation advice")
    action: Optional[DecisionAction] = Field(None, description="\u7ed3\u6784\u5316\u5efa\u8bae\u52a8\u4f5c taxonomy")
    action_label: Optional[str] = Field(None, description="\u5efa\u8bae\u52a8\u4f5c\u5c55\u793a\u6807\u7b7e")
    current_price: Optional[float] = Field(None, description="analyze\u65f6\u80a1\u4ef7")
    change_pct: Optional[float] = Field(None, description="analyze\u65f6change\u5e45(%)")
    volume_ratio: Optional[float] = Field(None, description="analyze\u65f6\u91cf\u6bd4")
    turnover_rate: Optional[float] = Field(None, description="analyze\u65f6turnover")
    model_used: Optional[str] = Field(
        None,
        description="analyzehistory recordsMedium\u7684\u6a21\u578b\u5feb\u7167; \u4ec5\u7528\u4e8e\u5c55\u793ahistory\u5143\u6570\u636e；\u4e0d\u53c2\u4e0e\u6a21\u578bconfigor\u8fd0\u884c\u65f6\u8def\u7531\u51b3\u7b56",
    )
    market_phase_summary: Optional[MarketPhaseSummary] = Field(
        None,
        description="this runanalyzemarket\u9636\u6bb5Low\u654fsummary",
    )
    created_at: Optional[str] = Field(None, description="\u521b\u5efa\u65f6\u95f4")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 1234,
            "query_id": "abc123",
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "report_type": "detailed",
            "sentiment_score": 75,
            "operation_advice": "\u6301\u6709",
            "created_at": "2024-01-01T12:00:00"
        }
    })


class HistoryListResponse(BaseModel):
    """history records\u5217\u8868\u54cd\u5e94"""

    total: int = Field(..., description="\u603b\u8bb0\u5f55\u6570")
    page: int = Field(..., description="\u5f53\u524d\u9875\u7801")
    limit: int = Field(..., description="\u6bcf\u9875count")
    items: List[HistoryItem] = Field(default_factory=list, description="\u8bb0\u5f55\u5217\u8868")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 100,
            "page": 1,
            "limit": 20,
            "items": []
        }
    })


class DeleteHistoryRequest(BaseModel):
    """\u5220\u9664history recordsrequest"""

    record_ids: List[int] = Field(default_factory=list, description="\u8981\u5220\u9664\u7684history records\u4e3b\u952e ID \u5217\u8868")


class DeleteHistoryResponse(BaseModel):
    """\u5220\u9664history records\u54cd\u5e94"""

    deleted: int = Field(..., description="\u5b9e\u9645\u5220\u9664\u7684history recordscount")


class NewsIntelItem(BaseModel):
    """news\u60c5\u62a5\u6761\u76ee"""

    title: str = Field(..., description="news\u6807\u9898")
    snippet: str = Field("", description="newssummary (\u6700\u591a200\u5b57)")
    url: str = Field(..., description="news\u94fe\u63a5")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "\u516c\u53f8\u53d1\u5e03\u4e1a\u7ee9\u5feb\u62a5; \u8425\u6536\u540c\u6bd4\u589e\u957f 20%",
            "snippet": "\u516c\u53f8\u516c\u544a\u663e\u793a; \u5b63\u5ea6\u8425\u6536\u540c\u6bd4\u589e\u957f 20%...",
            "url": "https://example.com/news/123"
        }
    })


class NewsIntelResponse(BaseModel):
    """news\u60c5\u62a5\u54cd\u5e94"""

    total: int = Field(..., description="news\u6761\u6570")
    items: List[NewsIntelItem] = Field(default_factory=list, description="news\u5217\u8868")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 2,
            "items": []
        }
    })


class ReportMeta(BaseModel):
    """report\u5143info"""

    model_config = ConfigDict(protected_namespaces=("model_validate", "model_dump"))

    id: Optional[int] = Field(None, description="analyzehistory records\u4e3b\u952e ID (\u4ec5historyreport\u6709\u6b64\u5b57\u6bb5)")
    query_id: str = Field(..., description="analyze\u8bb0\u5f55\u5173\u8054 query_id (batchanalyze\u65f6\u91cd\u590d)")
    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    report_type: Optional[str] = Field(None, description="report type")
    report_language: Optional[str] = Field(None, description="report\u8f93\u51fa\u8bed\u8a00 (zh/en)")
    created_at: Optional[str] = Field(None, description="\u521b\u5efa\u65f6\u95f4")
    current_price: Optional[float] = Field(None, description="analyze\u65f6\u80a1\u4ef7")
    change_pct: Optional[float] = Field(None, description="analyze\u65f6change\u5e45(%)")
    model_used: Optional[str] = Field(
        None,
        description="historyreport\u5143\u6570\u636eMedium\u7684\u6a21\u578b\u5feb\u7167; \u4ec5\u7528\u4e8e\u5c55\u793a; \u4e0d\u5f71\u54cd Provider/Model/Base URL \u8fd0\u884c\u65f6\u8def\u7531",
    )
    market_phase_summary: Optional[MarketPhaseSummary] = Field(
        None,
        description="this runanalyzemarket\u9636\u6bb5Low\u654fsummary",
    )


class ReportSummary(BaseModel):
    """report\u6982\u89c8\u533a"""

    analysis_summary: Optional[str] = Field(None, description="\u5173\u952e\u7ed3\u8bba")
    operation_advice: Optional[str] = Field(None, description="operation advice")
    action: Optional[DecisionAction] = Field(None, description="\u7ed3\u6784\u5316\u5efa\u8bae\u52a8\u4f5c taxonomy")
    action_label: Optional[str] = Field(None, description="\u5efa\u8bae\u52a8\u4f5c\u5c55\u793a\u6807\u7b7e")
    trend_prediction: Optional[str] = Field(None, description="\u8d8b\u52bf\u9884\u6d4b")
    sentiment_score: Optional[int] = Field(
        None,
        description="\u60c5\u7eea\u8bc4\u5206 (history\u6570\u636e\u53ef\u80fd\u8d85\u51fa 0-100 \u8303\u56f4; \u8bfb\u53d6\u65f6\u4e0d\u505a\u7ea6\u675f)",
    )
    sentiment_label: Optional[str] = Field(None, description="\u60c5\u7eea\u6807\u7b7e")


class ReportStrategy(BaseModel):
    """strategy\u70b9characters\u533a"""

    ideal_buy: Optional[str] = Field(None, description="\u7406\u60f3\u4e70\u5165\u4ef7")
    secondary_buy: Optional[str] = Field(None, description="\u7b2c\u4e8c\u4e70\u5165\u4ef7")
    stop_loss: Optional[str] = Field(None, description="\u6b62\u635f\u4ef7")
    take_profit: Optional[str] = Field(None, description="\u6b62\u76c8\u4ef7")


class AnalysisContextPackOverviewSubject(BaseModel):
    """AnalysisContextPack \u53ef\u89c1summary\u6807\u7684info"""

    code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    market: Optional[str] = Field(None, description="market")


class AnalysisContextPackOverviewBlock(BaseModel):
    """AnalysisContextPack \u53ef\u89c1summary\u6570\u636echunks"""

    key: str = Field(..., description="\u6570\u636echunks\u7a33\u5b9a key")
    label: str = Field(..., description="\u6570\u636echunks\u5c55\u793aname")
    status: Literal[
        "available",
        "missing",
        "not_supported",
        "fallback",
        "stale",
        "estimated",
        "partial",
        "fetch_failed",
    ] = Field(..., description="\u6570\u636echunks\u8d28\u91cfstatus")
    source: Optional[str] = Field(None, description="\u6570\u636esource")
    warnings: List[str] = Field(default_factory=list, description="\u6570\u636echunks\u544a\u8b66\u7801")
    missing_reasons: List[str] = Field(default_factory=list, description="\u7f3a\u5931reason")


class AnalysisContextPackOverviewCounts(BaseModel):
    """AnalysisContextPack \u53ef\u89c1summarystatus\u8ba1\u6570"""

    available: int = 0
    missing: int = 0
    not_supported: int = 0
    fallback: int = 0
    stale: int = 0
    estimated: int = 0
    partial: int = 0
    fetch_failed: int = 0


class AnalysisContextPackOverviewMetadata(BaseModel):
    """AnalysisContextPack \u53ef\u89c1summary\u5143\u6570\u636e"""

    trigger_source: Optional[str] = Field(None, description="\u89e6\u53d1source")
    news_result_count: Optional[int] = Field(None, description="newsresultcount")


class AnalysisContextPackOverviewDataQuality(BaseModel):
    """AnalysisContextPack \u53ef\u89c1summary\u6570\u636e\u8d28\u91cf\u8bc4\u5206"""

    overall_score: Optional[int] = Field(None, ge=0, le=100, description="\u8f93\u5165\u6570\u636e\u8d28\u91cf\u603b\u5206")
    level: Optional[Literal["good", "usable", "limited", "poor"]] = Field(
        None,
        description="\u8f93\u5165\u6570\u636e\u8d28\u91cf\u7b49\u7ea7",
    )
    block_scores: Dict[str, int] = Field(default_factory=dict, description="\u56fa\u5b9a\u6570\u636echunks\u8d28\u91cf\u5206")
    limitations: List[str] = Field(default_factory=list, description="Low\u654f\u6570\u636elimit\u8bf4\u660e")


class AnalysisContextPackOverview(BaseModel):
    """history/API \u53ef\u89c1\u7684Low\u654f AnalysisContextPack summary"""

    pack_version: str = Field(..., description="AnalysisContextPack \u7248\u672c")
    created_at: Optional[str] = Field(None, description="\u521b\u5efa\u65f6\u95f4")
    subject: AnalysisContextPackOverviewSubject
    blocks: List[AnalysisContextPackOverviewBlock] = Field(default_factory=list)
    counts: AnalysisContextPackOverviewCounts
    data_quality: Optional[AnalysisContextPackOverviewDataQuality] = Field(
        None,
        description="this runanalyze\u8f93\u5165\u6570\u636e\u8d28\u91cfLow\u654fsummary",
    )
    warnings: List[str] = Field(default_factory=list, description="\u9876\u5c42\u6570\u636e\u8d28\u91cf\u63d0\u9192")
    metadata: AnalysisContextPackOverviewMetadata = Field(default_factory=AnalysisContextPackOverviewMetadata)


class ReportDetails(BaseModel):
    """report\u8be6\u60c5\u533a"""

    news_content: Optional[str] = Field(None, description="newssummary")
    raw_result: Optional[Any] = Field(None, description="\u539f\u59cbanalysis result (JSON)")
    context_snapshot: Optional[Any] = Field(None, description="analyze\u65f6\u4e0a\u4e0b\u6587\u5feb\u7167 (JSON)")
    analysis_context_pack_overview: Optional[AnalysisContextPackOverview] = Field(
        None,
        description="this runanalyze\u8f93\u5165\u4e0a\u4e0b\u6587\u5305Low\u654fsummary",
    )
    financial_report: Optional[Any] = Field(None, description="\u7ed3\u6784\u5316\u8d22\u62a5summary (\u6765\u81ea fundamental_context)")
    dividend_metrics: Optional[Any] = Field(None, description="\u7ed3\u6784\u5316\u5206\u7ea2\u6307\u6807 (\u542b TTM \u53e3\u5f84)")
    belong_boards: Optional[Any] = Field(None, description="\u5173\u8054sector\u5217\u8868")
    sector_rankings: Optional[Any] = Field(None, description="sectorchange\u699c (\u7ed3\u6784 {top, bottom})")
    concept_rankings: Optional[Any] = Field(None, description="conceptsectorchange\u699c (\u7ed3\u6784 {top, bottom})")

    @model_validator(mode="after")
    def populate_concept_rankings_from_context(self) -> "ReportDetails":
        if self.concept_rankings is not None or self.context_snapshot is None:
            return self
        try:
            from src.utils.data_processing import extract_board_detail_fields

            extracted = extract_board_detail_fields(self.context_snapshot)
            self.concept_rankings = extracted.get("concept_rankings")
        except Exception:
            self.concept_rankings = None
        return self


class AnalysisReport(BaseModel):
    """\u5b8c\u6574analyzereport"""

    meta: ReportMeta = Field(..., description="\u5143info")
    summary: ReportSummary = Field(..., description="\u6982\u89c8\u533a")
    strategy: Optional[ReportStrategy] = Field(None, description="strategy\u70b9characters\u533a")
    details: Optional[ReportDetails] = Field(None, description="\u8be6\u60c5\u533a")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "meta": {
                "query_id": "abc123",
                "stock_code": "600519",
                "stock_name": "\u8d35\u5dde\u8305\u53f0",
                "report_type": "detailed",
                "report_language": "zh",
                "created_at": "2024-01-01T12:00:00"
            },
            "summary": {
                "analysis_summary": "\u6280\u672f\u9762\u5411\u597d; \u5efa\u8bae\u6301\u6709",
                "operation_advice": "\u6301\u6709",
                "trend_prediction": "\u770b\u591a",
                "sentiment_score": 75,
                "sentiment_label": "\u4e50\u89c2"
            },
            "strategy": {
                "ideal_buy": "1800.00",
                "secondary_buy": "1750.00",
                "stop_loss": "1700.00",
                "take_profit": "2000.00"
            },
            "details": None
        }
    })


class MarkdownReportResponse(BaseModel):
    """Markdown \u683c\u5f0freport\u54cd\u5e94"""

    content: str = Field(..., description="Markdown \u683c\u5f0f\u7684\u5b8c\u6574report\u5185\u5bb9")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "content": "# 📊 \u8d35\u5dde\u8305\u53f0 (600519) analyzereport\n\n> analyzedate: **2024-01-01**\n\n..."
        }
    })


class StockBarItem(BaseModel):
    """individual stocks\u680f\u6761\u76ee (\u53bb\u91cd\u540e\u7684\u80a1\u7968\u7ef4\u5ea6summary)"""

    id: int = Field(..., description="\u8be5\u80a1\u6700\u65b0\u4e00\u6b21analyze\u7684history records\u4e3b\u952e ID")
    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    report_type: Optional[str] = Field(None, description="report type")
    sentiment_score: Optional[int] = Field(
        None,
        description="\u6700\u65b0\u60c5\u7eea\u8bc4\u5206",
    )
    operation_advice: Optional[str] = Field(None, description="\u6700\u65b0operation advice")
    action: Optional[DecisionAction] = Field(None, description="\u7ed3\u6784\u5316\u5efa\u8bae\u52a8\u4f5c taxonomy")
    action_label: Optional[str] = Field(None, description="\u5efa\u8bae\u52a8\u4f5c\u5c55\u793a\u6807\u7b7e")
    analysis_count: int = Field(..., description="\u8be5\u80a1\u7968\u7684historyanalyze\u603b\u6b21\u6570")
    last_analysis_time: Optional[str] = Field(None, description="\u6700\u8fd1\u4e00\u6b21analyze\u65f6\u95f4")
    model_used: Optional[str] = Field(
        None,
        description="\u6700\u65b0analyze\u4f7f\u7528\u7684\u6a21\u578b\u5feb\u7167",
    )
    market_phase_summary: Optional[MarketPhaseSummary] = Field(
        None,
        description="\u6700\u65b0analyzemarket\u9636\u6bb5Low\u654fsummary",
    )
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 1234,
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "report_type": "detailed",
            "sentiment_score": 75,
            "operation_advice": "\u6301\u6709",
            "analysis_count": 18,
            "last_analysis_time": "2024-01-01T12:00:00",
            "model_used": "Gemini 2.5 Pro",
        }
    })


class StockBarResponse(BaseModel):
    """individual stocks\u680f\u5217\u8868\u54cd\u5e94"""

    total: int = Field(..., description="\u4e0d\u91cd\u590dindividual stocks\u6570")
    items: List[StockBarItem] = Field(default_factory=list, description="individual stocks\u5217\u8868")


class WatchlistRequest(BaseModel):
    """\u81ea\u9009queue\u64cd\u4f5crequest"""

    stock_code: str = Field(..., description="stock code", min_length=1)


class WatchlistResponse(BaseModel):
    """\u81ea\u9009queue\u54cd\u5e94"""

    stock_codes: List[str] = Field(default_factory=list, description="current watchlist hasqueuestock code\u5217\u8868")
    message: str = Field(..., description="\u64cd\u4f5cresult\u63cf\u8ff0")


class RunDiagnosticComponent(BaseModel):
    """\u5355\u4e2a\u8fd0\u884c\u8bca\u65ad\u7ec4\u4ef6summary."""

    key: str = Field(..., description="\u7ec4\u4ef6\u952e")
    label: str = Field(..., description="\u7ec4\u4ef6\u663e\u793aname")
    status: str = Field(..., description="\u7ec4\u4ef6status: ok/degraded/failed/unknown/not_configured/skipped")
    message: str = Field(..., description="user\u53ef\u8bfbsummary")
    details: Optional[Dict[str, Any]] = Field(None, description="\u6298\u53e0\u5c55\u793a\u7684\u8bca\u65ad\u7ec6\u8282")


class RunDiagnosticSummaryResponse(BaseModel):
    """historyreport\u8fd0\u884c\u8bca\u65adsummary."""

    trace_id: Optional[str] = Field(None, description="\u8bca\u65ad trace ID")
    task_id: Optional[str] = Field(None, description="task ID")
    query_id: Optional[str] = Field(None, description="analyze query ID")
    stock_code: Optional[str] = Field(None, description="stock code")
    trigger_source: Optional[str] = Field(None, description="\u89e6\u53d1source")
    status: str = Field(..., description="\u603b\u4f53status: normal/degraded/failed/unknown")
    status_label: str = Field(..., description="\u603b\u4f53statusMedium\u6587\u6807\u7b7e")
    reason: str = Field(..., description="\u6700\u4e3b\u8981\u7684\u8bca\u65adreason")
    components: Dict[str, RunDiagnosticComponent] = Field(default_factory=dict, description="\u5173\u952e\u94fe\u8def\u8bca\u65ad\u7ec4\u4ef6")
    copy_text: str = Field(..., description="\u53ef\u590d\u5236\u7684\u8131\u654f\u6392\u969c\u6587\u672c")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "trace_id": "task_abc123",
            "query_id": "task_abc123",
            "stock_code": "600519",
            "status": "degraded",
            "status_label": "\u90e8\u5206\u964d\u7ea7",
            "reason": "realtime quotefailed: timeout",
            "components": {},
            "copy_text": "trace_id: task_abc123\nstock_code: 600519\n...",
        }
    })
