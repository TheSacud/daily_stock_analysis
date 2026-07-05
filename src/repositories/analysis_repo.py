# -*- coding: utf-8 -*-
"""
===================================
analyzehistory\u6570\u636e\u8bbfask\u5c42
===================================

\u804c\u8d23:
1. \u5c01\u88c5analyzehistory\u6570\u636edatalibrary\u64cd\u4f5c
2. \u63d0\u4f9b CRUD \u63a5\u53e3
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from src.storage import DatabaseManager, AnalysisHistory

logger = logging.getLogger(__name__)


class AnalysisRepository:
    """
    analyzehistory\u6570\u636e\u8bbfask\u5c42

    \u5c01\u88c5 AnalysisHistory \u8868datalibrary\u64cd\u4f5c
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        \u521d\u59cb\u5316\u6570\u636e\u8bbfask\u5c42

        Args:
            db_manager: \u6570\u636elibrary\u7ba1\u7406\u5668 (optional; default\u4f7f\u7528\u5355\u4f8b)
        """
        self.db = db_manager or DatabaseManager.get_instance()

    def get_by_query_id(self, query_id: str) -> Optional[AnalysisHistory]:
        """
        \u6839\u636e query_id \u83b7\u53d6analyze\u8bb0\u5f55

        Args:
            query_id: query ID

        Returns:
            AnalysisHistory \u5bf9\u8c61; does not exist\u8fd4\u56de None
        """
        try:
            records = self.db.get_analysis_history(query_id=query_id, limit=1)
            return records[0] if records else None
        except Exception as e:
            logger.error(f"queryanalyze\u8bb0\u5f55failed: {e}")
            return None

    def get_list(
        self,
        code: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[AnalysisHistory]:
        """
        \u83b7\u53d6analyze\u8bb0\u5f55\u5217\u8868

        Args:
            code: stock code\u7b5b\u9009
            days: \u65f6\u95f4\u8303\u56f4 (\u5929)
            limit: \u8fd4\u56decountlimit

        Returns:
            AnalysisHistory \u5bf9\u8c61\u5217\u8868
        """
        try:
            return self.db.get_analysis_history(
                code=code,
                days=days,
                limit=limit
            )
        except Exception as e:
            logger.error(f"\u83b7\u53d6analyze\u5217\u8868failed: {e}")
            return []

    def save(
        self,
        result: Any,
        query_id: str,
        report_type: str,
        news_content: Optional[str] = None,
        context_snapshot: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        \u4fdd\u5b58analysis result

        Args:
            result: analysis result\u5bf9\u8c61
            query_id: query ID
            report_type: report type
            news_content: news\u5185\u5bb9
            context_snapshot: \u4e0a\u4e0b\u6587\u5feb\u7167

        Returns:
            \u65b0\u4fdd\u5b58\u7684 AnalysisHistory.id；save failed\u8fd4\u56de 0.
        """
        try:
            return self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type=report_type,
                news_content=news_content,
                context_snapshot=context_snapshot
            )
        except Exception as e:
            logger.error(f"\u4fdd\u5b58analysis resultfailed: {e}")
            return 0

    def count_by_code(self, code: str, days: int = 30) -> int:
        """
        \u7edf\u8ba1\u6307\u5b9a\u80a1\u7968\u7684analyze\u8bb0\u5f55\u6570

        Args:
            code: stock code
            days: \u65f6\u95f4\u8303\u56f4 (\u5929)

        Returns:
            \u8bb0\u5f55count
        """
        try:
            records = self.db.get_analysis_history(code=code, days=days, limit=1000)
            return len(records)
        except Exception as e:
            logger.error(f"\u7edf\u8ba1analyze\u8bb0\u5f55failed: {e}")
            return 0
