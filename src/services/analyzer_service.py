# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis system - analyze\u670d\u52a1\u5c42
===================================

\u804c\u8d23:
1. \u5c01\u88c5\u6838\u5fc3analyze\u903b\u8f91; \u652f\u6301\u591a\u8c03\u7528\u65b9 (CLI、WebUI、Bot)
2. \u63d0\u4f9b\u6e05\u6670\u7684API\u63a5\u53e3; \u4e0d\u4f9d\u8d56\u4e8ecommand\u884cparameter
3. \u652f\u6301\u4f9d\u8d56\u6ce8\u5165; \u4fbf\u4e8e\u6d4b\u8bd5\u548c\u6269\u5c55
4. \u7edf\u4e00\u7ba1\u7406analysis flow\u548cconfig
"""

import uuid
from typing import List, Optional

from src.analyzer import AnalysisResult
from src.core.market_review import run_market_review
from src.core.pipeline import StockAnalysisPipeline
from src.config import Config, get_config
from src.enums import ReportType
from src.notification import NotificationService


def analyze_stock(
    stock_code: str,
    config: Config = None,
    full_report: bool = False,
    notifier: Optional[NotificationService] = None,
) -> Optional[AnalysisResult]:
    """
    analyze\u5355stocks

    Args:
        stock_code: stock code
        config: config\u5bf9\u8c61 (optional; default\u4f7f\u7528\u5355\u4f8b)
        full_report: \u662f\u5426\u751f\u6210\u5b8c\u6574report
        notifier: notification service (optional)

    Returns:
        analysis result\u5bf9\u8c61
    """
    if config is None:
        config = get_config()

    # \u521b\u5efaanalyze\u6d41\u6c34\u7ebf
    pipeline = StockAnalysisPipeline(
        config=config,
        query_id=uuid.uuid4().hex,
        query_source="cli"
    )

    # \u4f7f\u7528notification service (\u5982\u679c\u63d0\u4f9b)
    if notifier:
        pipeline.notifier = notifier

    # \u6839\u636efull_reportparameter\u8bbe\u7f6ereport type
    report_type = ReportType.FULL if full_report else ReportType.SIMPLE

    # \u8fd0\u884c\u5355stocksanalyze
    result = pipeline.process_single_stock(
        code=stock_code,
        skip_analysis=False,
        single_stock_notify=notifier is not None,
        report_type=report_type,
    )

    return result


def analyze_stocks(
    stock_codes: List[str],
    config: Config = None,
    full_report: bool = False,
    notifier: Optional[NotificationService] = None,
) -> List[AnalysisResult]:
    """
    analyze\u591astocks

    Args:
        stock_codes: stock code\u5217\u8868
        config: config\u5bf9\u8c61 (optional; default\u4f7f\u7528\u5355\u4f8b)
        full_report: \u662f\u5426\u751f\u6210\u5b8c\u6574report
        notifier: notification service (optional)

    Returns:
        analysis result\u5217\u8868
    """
    if config is None:
        config = get_config()

    results = []
    for stock_code in stock_codes:
        result = analyze_stock(stock_code, config, full_report, notifier)
        if result:
            results.append(result)

    return results


def perform_market_review(
    config: Config = None,
    notifier: Optional[NotificationService] = None,
) -> Optional[str]:
    """
    \u6267\u884cmarket review

    Args:
        config: config\u5bf9\u8c61 (optional; default\u4f7f\u7528\u5355\u4f8b)
        notifier: notification service (optional)

    Returns:
        \u590d\u76d8report\u5185\u5bb9
    """
    if config is None:
        config = get_config()

    # \u521b\u5efaanalyze\u6d41\u6c34\u7ebf\u4ee5\u83b7\u53d6analyzer\u548csearch_service
    pipeline = StockAnalysisPipeline(
        config=config,
        query_id=uuid.uuid4().hex,
        query_source="cli",
    )

    # \u4f7f\u7528\u63d0\u4f9b\u7684notification serviceor\u521b\u5efa\u65b0\u7684
    review_notifier = notifier or pipeline.notifier

    # \u8c03\u7528market review\u51fd\u6570
    return run_market_review(
        notifier=review_notifier,
        analyzer=pipeline.analyzer,
        search_service=pipeline.search_service,
        config=config,
        trigger_source="service",
    )
