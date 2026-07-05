# -*- coding: utf-8 -*-
"""
===================================
\u5065\u5eb7\u68c0check\u63a5\u53e3
===================================

\u804c\u8d23:
1. \u63d0\u4f9b /api/v1/health \u5065\u5eb7\u68c0check\u63a5\u53e3
2. \u7528\u4e8e\u8d1f\u8f7d\u5747\u8861\u5668\u548c\u76d1\u63a7\u7cfb\u7edf
"""

from datetime import datetime

from fastapi import APIRouter

from api.v1.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    \u5065\u5eb7\u68c0check\u63a5\u53e3

    \u7528\u4e8e\u8d1f\u8f7d\u5747\u8861\u5668or\u76d1\u63a7\u7cfb\u7edf\u68c0check\u670d\u52a1status

    Returns:
        HealthResponse: \u5305\u542b\u670d\u52a1status\u548c\u65f6\u95f4\u6233
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat()
    )
