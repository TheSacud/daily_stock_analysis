# -*- coding: utf-8 -*-
"""
===================================
\u679a\u4e3e\u7c7b\u578b\u5b9a\u4e49
===================================

\u96c6Medium\u7ba1\u7406\u7cfb\u7edfMedium\u4f7f\u7528\u7684\u679a\u4e3e\u7c7b\u578b; \u63d0\u4f9b\u7c7b\u578b\u5b89\u5168\u548ccode\u53ef\u8bfb.
"""

from enum import Enum


class ReportType(str, Enum):
    """
    report type\u679a\u4e3e

    \u7528\u4e8e API \u89e6\u53d1analyze\u65f6\u9009\u62e9\u63a8\u9001\u7684report\u683c\u5f0f.
    \u7ee7\u627f str \u4f7f\u5176\u53ef\u4ee5\u76f4\u63a5\u4e0e\u5b57\u7b26\u4e32\u6bd4\u8f83\u548c\u5e8f\u5217\u5316.
    """
    SIMPLE = "simple"  # \u7cbe\u7b80report: \u4f7f\u7528 generate_single_stock_report
    FULL = "full"      # \u5b8c\u6574report: \u4f7f\u7528 generate_dashboard_report
    BRIEF = "brief"    # \u7b80\u6d01mode: 3-5 \u53e5\u8bdd\u6982\u62ec; \u9002\u5408\u79fb\u52a8\u7aef/\u63a8\u9001

    @classmethod
    def from_str(cls, value: str) -> "ReportType":
        """
        \u4ece\u5b57\u7b26\u4e32\u5b89\u5168\u5730\u8f6c\u6362\u4e3a\u679a\u4e3e\u503c

        Args:
            value: \u5b57\u7b26\u4e32\u503c

        Returns:
            \u5bf9\u5e94\u7684\u679a\u4e3e\u503c; \u65e0\u6548\u8f93\u5165\u8fd4\u56dedefault\u503c SIMPLE
        """
        try:
            normalized = value.lower().strip()
            if normalized == "detailed":
                normalized = cls.FULL.value
            return cls(normalized)
        except (ValueError, AttributeError):
            return cls.SIMPLE

    @property
    def display_name(self) -> str:
        """\u83b7\u53d6\u7528\u4e8e\u663e\u793a\u7684name"""
        return {
            ReportType.SIMPLE: "\u7cbe\u7b80report",
            ReportType.FULL: "\u5b8c\u6574report",
            ReportType.BRIEF: "\u7b80\u6d01report",
        }.get(self, "\u7cbe\u7b80report")
