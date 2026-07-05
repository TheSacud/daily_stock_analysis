# -*- coding: utf-8 -*-
"""
===================================
\u80a1\u7968analyzecommand
===================================

analyze specified stocks; \u8c03\u7528 AI \u751f\u6210analyzereport.
"""

import re
import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from src.services.stock_code_utils import resolve_index_stock_code_for_analysis

logger = logging.getLogger(__name__)


class AnalyzeCommand(BotCommand):
    """
    \u80a1\u7968analyzecommand

    analyze\u6307\u5b9astock code; \u751f\u6210 AI analyzereport\u5e76\u63a8\u9001.

    Usage:
        /analyze 600519       - analyze\u8d35\u5dde\u8305\u53f0 (\u7cbe\u7b80report)
        /analyze 600519 full  - analyze\u5e76\u751f\u6210\u5b8c\u6574report
    """

    @property
    def name(self) -> str:
        return "analyze"

    @property
    def aliases(self) -> List[str]:
        return ["a", "analyze", "check"]

    @property
    def description(self) -> str:
        return "analyze specified stocks"

    @property
    def usage(self) -> str:
        return "/analyze <stock code> [full]"

    def validate_args(self, args: List[str]) -> Optional[str]:
        """\u9a8c\u8bc1parameter"""
        if not args:
            return "enter a stock code"

        code = args[0].upper()

        # \u9a8c\u8bc1stock code\u683c\u5f0f
        # A-share: 6 digits
        # HK stock: HK+5 digits
        # US stock: 1-5\u4e2a\u5927\u5199\u5b57\u6bcd+.+2\u4e2a\u540e\u7f00\u5b57\u6bcd
        is_a_stock = re.match(r'^\d{6}$', code)
        is_hk_stock = re.match(r'^HK\d{5}$', code)
        is_us_stock = re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code)

        if not (is_a_stock or is_hk_stock or is_us_stock):
            return f"invalid stock code: {code} (A-share6 digits / HK stockHK+5 digits / US stock1-5 letters)"

        return None

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """\u6267\u884canalyzecommand"""
        code = resolve_index_stock_code_for_analysis(args[0])

        # \u68c0check\u662f\u5426\u9700\u8981\u5b8c\u6574report (default\u7cbe\u7b80; \u4f20 full/\u5b8c\u6574/\u8be6\u7ec6 \u5207\u6362)
        report_type = "simple"
        if len(args) > 1 and args[1].lower() in ["full", "\u5b8c\u6574", "\u8be6\u7ec6"]:
            report_type = "full"
        logger.info(f"[AnalyzeCommand] analyze stock: {code}, report type: {report_type}")

        try:
            # \u8c03\u7528analyze\u670d\u52a1
            from src.services.task_service import get_task_service
            from src.enums import ReportType

            service = get_task_service()

            # \u63d0\u4ea4\u5f02\u6b65analysis task
            result = service.submit_analysis(
                code=code,
                report_type=ReportType.from_str(report_type),
                source_message=message
            )

            if result.get("success"):
                task_id = result.get("task_id", "")
                return BotResponse.markdown_response(
                    f"✅ **analysis task\u5df2\u63d0\u4ea4**\n\n"
                    f"• stock code: `{code}`\n"
                    f"• report type: {ReportType.from_str(report_type).display_name}\n"
                    f"• task ID: `{task_id[:20]}...`\n\n"
                    f"analysis completed\u540e\u5c06\u81ea\u52a8\u63a8\u9001result."
                )
            else:
                error = result.get("error", "unknown error")
                return BotResponse.error_response(f"failed to submit analysis task: {error}")

        except Exception as e:
            logger.error(f"[AnalyzeCommand] execution failed: {e}")
            return BotResponse.error_response(f"analyzefailed: {str(e)[:100]}")
