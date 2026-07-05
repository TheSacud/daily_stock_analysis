# -*- coding: utf-8 -*-
"""
===================================
\u80a1\u7968\u6570\u636e\u76f8\u5173\u6a21\u578b
===================================

\u804c\u8d23:
1. \u5b9a\u4e49\u80a1\u7968realtime quote\u6a21\u578b
2. \u5b9a\u4e49history K \u7ebf\u6570\u636e\u6a21\u578b
"""

from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class StockQuote(BaseModel):
    """\u80a1\u7968realtime quote"""

    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    current_price: float = Field(..., description="\u5f53\u524dprice")
    change: Optional[float] = Field(None, description="change\u989d")
    change_percent: Optional[float] = Field(None, description="change\u5e45 (%)")
    open: Optional[float] = Field(None, description="\u5f00\u76d8\u4ef7")
    high: Optional[float] = Field(None, description="\u6700High\u4ef7")
    low: Optional[float] = Field(None, description="\u6700Low\u4ef7")
    prev_close: Optional[float] = Field(None, description="\u6628\u6536\u4ef7")
    volume: Optional[float] = Field(None, description="volume (\u80a1)")
    amount: Optional[float] = Field(None, description="amount (\u5143)")
    update_time: Optional[str] = Field(None, description="\u66f4\u65b0\u65f6\u95f4")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "current_price": 1800.00,
            "change": 15.00,
            "change_percent": 0.84,
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "prev_close": 1785.00,
            "volume": 10000000,
            "amount": 18000000000,
            "update_time": "2024-01-01T15:00:00"
        }
    })


class KLineData(BaseModel):
    """K \u7ebf\u6570\u636e\u70b9"""

    date: str = Field(..., description="date")
    open: float = Field(..., description="\u5f00\u76d8\u4ef7")
    high: float = Field(..., description="\u6700High\u4ef7")
    low: float = Field(..., description="\u6700Low\u4ef7")
    close: float = Field(..., description="\u6536\u76d8\u4ef7")
    volume: Optional[float] = Field(None, description="volume")
    amount: Optional[float] = Field(None, description="amount")
    change_percent: Optional[float] = Field(None, description="change\u5e45 (%)")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2024-01-01",
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "close": 1800.00,
            "volume": 10000000,
            "amount": 18000000000,
            "change_percent": 0.84
        }
    })


class ExtractItem(BaseModel):
    """\u5355\u6761\u63d0\u53d6result (code、name、\u7f6e\u4fe1\u5ea6)"""

    code: Optional[str] = Field(None, description="stock code; None \u8868\u793aparse failed")
    name: Optional[str] = Field(None, description="stock name (\u5982\u6709)")
    confidence: str = Field("medium", description="\u7f6e\u4fe1\u5ea6: high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """\u56fe\u7247stock code\u63d0\u53d6\u54cd\u5e94"""

    codes: List[str] = Field(..., description="\u63d0\u53d6\u7684stock code (\u5df2\u53bb\u91cd; \u5411\u540e\u517c\u5bb9)")
    items: List[ExtractItem] = Field(default_factory=list, description="\u63d0\u53d6result\u660e\u7ec6 (code+name+\u7f6e\u4fe1\u5ea6)")
    raw_text: Optional[str] = Field(None, description="\u539f\u59cb LLM \u54cd\u5e94 (\u8c03\u8bd5\u7528)")


class StockHistoryResponse(BaseModel):
    """\u80a1\u7968history\u884c\u60c5\u54cd\u5e94"""

    stock_code: str = Field(..., description="stock code")
    stock_name: Optional[str] = Field(None, description="stock name")
    period: str = Field(..., description="K \u7ebf\u5468\u671f")
    data: List[KLineData] = Field(default_factory=list, description="K \u7ebf\u6570\u636e\u5217\u8868")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "\u8d35\u5dde\u8305\u53f0",
            "period": "daily",
            "data": []
        }
    })
