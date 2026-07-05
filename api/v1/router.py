# -*- coding: utf-8 -*-
"""
===================================
API v1 \u8def\u7531\u805a\u5408
===================================

\u804c\u8d23:
1. \u805a\u5408 v1 \u7248\u672c\u7684\u6240\u6709 endpoint \u8def\u7531
2. \u7edf\u4e00\u6dfb\u52a0 /api/v1 prefix
"""

from fastapi import APIRouter

from api.v1.endpoints import (
    agent,
    alerts,
    alphasift,
    analysis,
    auth,
    backtest,
    decision_signals,
    health,
    history,
    intelligence,
    portfolio,
    stocks,
    system_config,
    usage,
)

# \u521b\u5efa v1 \u7248\u672c\u4e3b\u8def\u7531.
# /api/v1 prefix\u5728 api.app \u6302\u8f7d; \u907f\u514d\u65b0\u7248 FastAPI \u8bef\u5224\u5b50\u8def\u7531 "" \u4e3a empty path.
router = APIRouter()

router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"]
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"]
)

router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"]
)

router.include_router(
    history.router,
    prefix="/history",
    tags=["History"]
)

router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["Stocks"]
)

router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtest"]
)

router.include_router(
    system_config.router,
    prefix="/system",
    tags=["SystemConfig"]
)

router.include_router(
    usage.router,
    prefix="/usage",
    tags=["Usage"]
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"]
)

router.include_router(
    decision_signals.router,
    prefix="/decision-signals",
    tags=["DecisionSignals"]
)

router.include_router(
    alphasift.router,
    prefix="/alphasift",
    tags=["AlphaSift"]
)

router.include_router(
    intelligence.router,
    prefix="/intelligence",
    tags=["Intelligence"]
)

router.include_router(
    health.router,
    tags=["Health"]
)
