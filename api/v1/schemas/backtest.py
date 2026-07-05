# -*- coding: utf-8 -*-
"""Backtest API schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from api.v1.schemas.market_phase import MarketPhaseSummary
from src.schemas.decision_action import DecisionAction


class BacktestRunRequest(BaseModel):
    code: Optional[str] = Field(None, description="\u4ec5backtest\u6307\u5b9a\u80a1\u7968")
    force: bool = Field(False, description="\u5f3a\u5236\u91cd\u65b0\u8ba1\u7b97")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="\u8bc4\u4f30\u7a97\u53e3 (\u4ea4\u6613\u65e5\u6570)")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="analyze\u8bb0\u5f55\u6700\u5c0f\u5929\u9f84 (0=\u4e0d\u9650)")
    analysis_date_from: Optional[date] = Field(None, description="analyzedate\u8d77\u59cb (\u542b)")
    analysis_date_to: Optional[date] = Field(None, description="analyzedate\u7ed3\u675f (\u542b)")
    limit: int = Field(200, ge=1, le=2000, description="\u6700\u591a\u5904\u7406\u7684analyze\u8bb0\u5f55\u6570")


class BacktestRunResponse(BaseModel):
    processed: int = Field(..., description="\u5019\u9009\u8bb0\u5f55\u6570")
    saved: int = Field(..., description="\u5199\u5165backtestresult\u6570")
    completed: int = Field(..., description="\u5b8c\u6210backtest\u6570")
    insufficient: int = Field(..., description="\u6570\u636e\u4e0d\u8db3\u6570")
    errors: int = Field(..., description="error\u6570")
    applied_eval_window_days: Optional[int] = Field(
        ...,
        description="\u5b9e\u9645\u751f\u6548\u7684\u8bc4\u4f30\u7a97\u53e3 (\u4ea4\u6613\u65e5\u6570)",
    )
    message: Optional[str] = Field(None, description="\u7a7aresultor\u964d\u7ea7\u65f6\u7684\u8bca\u65ad\u8bf4\u660e")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="backtest\u7b5b\u9009\u4e0e\u8bca\u65adinfo")


class BacktestResultItem(BaseModel):
    analysis_history_id: int
    code: str
    stock_name: Optional[str] = None
    analysis_date: Optional[str] = None
    eval_window_days: int
    engine_version: str
    eval_status: str
    evaluated_at: Optional[str] = None
    operation_advice: Optional[str] = None
    action: Optional[DecisionAction] = None
    action_label: Optional[str] = None
    trend_prediction: Optional[str] = None
    market_phase: Optional[str] = None
    market_phase_summary: Optional[MarketPhaseSummary] = None
    position_recommendation: Optional[str] = None
    start_price: Optional[float] = None
    end_close: Optional[float] = None
    max_high: Optional[float] = None
    min_low: Optional[float] = None
    stock_return_pct: Optional[float] = None
    actual_return_pct: Optional[float] = None
    actual_movement: Optional[str] = None
    direction_expected: Optional[str] = None
    direction_correct: Optional[bool] = None
    outcome: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    hit_stop_loss: Optional[bool] = None
    hit_take_profit: Optional[bool] = None
    first_hit: Optional[str] = None
    first_hit_date: Optional[str] = None
    first_hit_trading_days: Optional[int] = None
    simulated_entry_price: Optional[float] = None
    simulated_exit_price: Optional[float] = None
    simulated_exit_reason: Optional[str] = None
    simulated_return_pct: Optional[float] = None


class BacktestResultsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BacktestResultItem] = Field(default_factory=list)


class PerformanceMetrics(BaseModel):
    scope: str
    code: Optional[str] = None
    eval_window_days: int
    engine_version: str
    computed_at: Optional[str] = None

    total_evaluations: int
    completed_count: int
    insufficient_count: int
    long_count: int
    cash_count: int
    win_count: int
    loss_count: int
    neutral_count: int

    direction_accuracy_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    neutral_rate_pct: Optional[float] = None
    avg_stock_return_pct: Optional[float] = None
    avg_simulated_return_pct: Optional[float] = None

    stop_loss_trigger_rate: Optional[float] = None
    take_profit_trigger_rate: Optional[float] = None
    ambiguous_rate: Optional[float] = None
    avg_days_to_first_hit: Optional[float] = None

    advice_breakdown: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
