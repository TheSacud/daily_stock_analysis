# -*- coding: utf-8 -*-
"""
===================================
\u670d\u52a1\u5c42\u6a21chunks\u521d\u59cb\u5316
===================================

\u804c\u8d23:
1. \u58f0\u660e\u53ef\u5bfc\u51fa\u7684\u670d\u52a1\u7c7b (\u5ef6\u8fdf\u5bfc\u5165; \u907f\u514dstarted\u65f6\u62c9\u5165 LLM \u7b49\u91cd\u4f9d\u8d56)

\u4f7f\u7528\u65b9\u5f0f:
    \u76f4\u63a5\u4ece\u5b50\u6a21chunks\u5bfc\u5165; \u4f8b\u5982:
    from src.services.history_service import HistoryService
"""


def __getattr__(name: str):
    """\u5ef6\u8fdf\u5bfc\u5165: \u4ec5\u5728\u901a\u8fc7 src.services.X \u8bbfask\u65f6\u624dload\u5bf9\u5e94\u5b50\u6a21chunks."""
    _lazy_map = {
        "AnalysisService": "src.services.analysis_service",
        "BacktestService": "src.services.backtest_service",
        "HistoryService": "src.services.history_service",
        "StockService": "src.services.stock_service",
        "TaskService": "src.services.task_service",
        "get_task_service": "src.services.task_service",
    }
    if name in _lazy_map:
        import importlib
        module = importlib.import_module(_lazy_map[name])
        return getattr(module, name)
    raise AttributeError(f"module 'src.services' has no attribute {name!r}")


__all__ = [
    "AnalysisService",
    "BacktestService",
    "HistoryService",
    "StockService",
    "TaskService",
    "get_task_service",
]
