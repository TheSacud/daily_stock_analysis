# -*- coding: utf-8 -*-
"""
===================================
\u901a\u7528\u54cd\u5e94\u6a21\u578b
===================================

\u804c\u8d23:
1. \u5b9a\u4e49\u901a\u7528\u7684\u54cd\u5e94\u6a21\u578b (HealthResponse, ErrorResponse \u7b49)
2. \u63d0\u4f9b\u7edf\u4e00\u7684\u54cd\u5e94\u683c\u5f0f
"""

from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field


class RootResponse(BaseModel):
    """API \u6839\u8def\u7531\u54cd\u5e94"""

    message: str = Field(..., description="API run status\u6d88\u606f", json_schema_extra={"example": "Daily Stock Analysis API is running"})
    version: Optional[str] = Field(None, description="API \u7248\u672c", json_schema_extra={"example": "1.0.0"})

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "message": "Daily Stock Analysis API is running",
            "version": "1.0.0"
        }
    })


class HealthResponse(BaseModel):
    """\u5065\u5eb7\u68c0check\u54cd\u5e94"""

    status: str = Field(..., description="\u670d\u52a1status", json_schema_extra={"example": "ok"})
    timestamp: Optional[str] = Field(None, description="\u65f6\u95f4\u6233")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "ok",
            "timestamp": "2024-01-01T12:00:00"
        }
    })


class ErrorResponse(BaseModel):
    """error\u54cd\u5e94"""

    error: str = Field(..., description="error\u7c7b\u578b", json_schema_extra={"example": "validation_error"})
    message: str = Field(..., description="error\u8be6\u60c5", json_schema_extra={"example": "requestinvalid parameters"})
    detail: Optional[Any] = Field(None, description="\u9644\u52a0errorinfo")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "not_found",
            "message": "\u8d44\u6e90does not exist",
            "detail": None
        }
    })


class SuccessResponse(BaseModel):
    """\u901a\u7528success\u54cd\u5e94"""

    success: bool = Field(True, description="\u662f\u5426success")
    message: Optional[str] = Field(None, description="success\u6d88\u606f")
    data: Optional[Any] = Field(None, description="\u54cd\u5e94\u6570\u636e")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "\u64cd\u4f5csuccess",
            "data": None
        }
    })
