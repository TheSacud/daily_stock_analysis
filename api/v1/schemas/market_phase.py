# -*- coding: utf-8 -*-
"""Market phase summary schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarketPhaseValue = Literal[
    "premarket",
    "intraday",
    "lunch_break",
    "closing_auction",
    "postmarket",
    "non_trading",
    "unknown",
]


class MarketPhaseSummary(BaseModel):
    """Low-sensitivity market phase metadata exposed on report meta."""

    market: Optional[str] = Field(None, description="market\u533a\u57df")
    phase: MarketPhaseValue = Field(..., description="market\u9636\u6bb5")
    market_local_time: Optional[str] = Field(None, description="market\u672c\u5730\u65f6\u95f4")
    session_date: Optional[str] = Field(None, description="market\u672c\u5730date")
    effective_daily_bar_date: Optional[str] = Field(None, description="\u6700\u65b0\u53ef\u590d\u7528\u5b8c\u6574daily datadate")
    is_trading_day: Optional[bool] = Field(None, description="\u662f\u5426\u4ea4\u6613\u65e5")
    is_market_open_now: Optional[bool] = Field(None, description="\u5f53\u524d\u662f\u5426\u5f00\u5e02")
    is_partial_bar: Optional[bool] = Field(None, description="\u6700\u65b0daily data\u662f\u5426\u53ef\u80fd\u672a\u5b8c\u6210")
    minutes_to_open: Optional[int] = Field(None, description="\u8ddd\u79bb\u5f00\u76d8\u5206\u949f\u6570")
    minutes_to_close: Optional[int] = Field(None, description="\u8ddd\u79bb\u6536\u76d8\u5206\u949f\u6570")
    trigger_source: Optional[str] = Field(None, description="\u89e6\u53d1source")
    analysis_intent: Optional[str] = Field(None, description="analyze\u610f\u56fe")
    warnings: List[str] = Field(default_factory=list, description="\u9636\u6bb5\u63a8\u65ad\u964d\u7ea7\u544a\u8b66\u7801")
