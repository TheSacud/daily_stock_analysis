# -*- coding: utf-8 -*-
"""
===================================
\u80a1\u7968\u6570\u636e\u8bbfask\u5c42
===================================

\u804c\u8d23:
1. \u5c01\u88c5\u80a1\u7968\u6570\u636edatalibrary\u64cd\u4f5c
2. \u63d0\u4f9bdaily data\u6570\u636equery\u63a5\u53e3
"""

import logging
from datetime import date
from typing import Optional, List, Dict, Any

import pandas as pd
from sqlalchemy import and_, desc, select

from src.storage import DatabaseManager, StockDaily

logger = logging.getLogger(__name__)


class StockRepository:
    """
    \u80a1\u7968\u6570\u636e\u8bbfask\u5c42

    \u5c01\u88c5 StockDaily \u8868datalibrary\u64cd\u4f5c
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        \u521d\u59cb\u5316\u6570\u636e\u8bbfask\u5c42

        Args:
            db_manager: \u6570\u636elibrary\u7ba1\u7406\u5668 (optional; default\u4f7f\u7528\u5355\u4f8b)
        """
        self.db = db_manager or DatabaseManager.get_instance()

    def get_latest(self, code: str, days: int = 2) -> List[StockDaily]:
        """
        \u83b7\u53d6\u6700\u8fd1 N \u5929data

        Args:
            code: stock code
            days: \u83b7\u53d6\u5929\u6570

        Returns:
            StockDaily \u5bf9\u8c61\u5217\u8868 (\u6309date\u964d\u5e8f)
        """
        try:
            return self.db.get_latest_data(code, days)
        except Exception as e:
            logger.error(f"\u83b7\u53d6\u6700\u65b0\u6570\u636efailed: {e}")
            return []

    def get_range(
        self,
        code: str,
        start_date: date,
        end_date: date
    ) -> List[StockDaily]:
        """
        \u83b7\u53d6\u6307\u5b9adate\u8303\u56f4data

        Args:
            code: stock code
            start_date: \u5f00\u59cbdate
            end_date: \u7ed3\u675fdate

        Returns:
            StockDaily \u5bf9\u8c61\u5217\u8868
        """
        try:
            return self.db.get_data_range(code, start_date, end_date)
        except Exception as e:
            logger.error(f"\u83b7\u53d6date\u8303\u56f4\u6570\u636efailed: {e}")
            return []

    def save_dataframe(
        self,
        df: pd.DataFrame,
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        \u4fdd\u5b58 DataFrame \u5230\u6570\u636elibrary

        Args:
            df: \u5305\u542bdaily data\u6570\u636e\u7684 DataFrame
            code: stock code
            data_source: \u6570\u636esource

        Returns:
            \u4fdd\u5b58\u7684\u8bb0\u5f55\u6570
        """
        try:
            return self.db.save_daily_data(df, code, data_source)
        except Exception as e:
            logger.error(f"\u4fdd\u5b58daily data\u6570\u636efailed: {e}")
            return 0

    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        \u68c0check\u662f\u5426\u6709\u6307\u5b9adatedata

        Args:
            code: stock code
            target_date: \u76ee\u6807date (default\u4eca\u5929)

        Returns:
            \u662f\u5426\u5b58\u5728\u6570\u636e
        """
        try:
            return self.db.has_today_data(code, target_date)
        except Exception as e:
            logger.error(f"\u68c0check\u6570\u636e\u5b58\u5728failed: {e}")
            return False

    def get_analysis_context(
        self,
        code: str,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        \u83b7\u53d6analyze\u4e0a\u4e0b\u6587

        Args:
            code: stock code
            target_date: \u76ee\u6807date

        Returns:
            analyze\u4e0a\u4e0b\u6587\u5b57\u5178
        """
        try:
            return self.db.get_analysis_context(code, target_date)
        except Exception as e:
            logger.error(f"\u83b7\u53d6analyze\u4e0a\u4e0b\u6587failed: {e}")
            return None

    def get_start_daily(self, *, code: str, analysis_date: date) -> Optional[StockDaily]:
        """Return StockDaily for analysis_date (preferred) or nearest previous date."""
        with self.db.get_session() as session:
            row = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date <= analysis_date))
                .order_by(desc(StockDaily.date))
                .limit(1)
            ).scalar_one_or_none()
            return row

    def get_daily_on_date(self, *, code: str, target_date: date) -> Optional[StockDaily]:
        """Return StockDaily for the exact target_date without trading-day fallback."""
        with self.db.get_session() as session:
            row = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date == target_date))
                .limit(1)
            ).scalar_one_or_none()
            return row

    def get_forward_bars(self, *, code: str, analysis_date: date, eval_window_days: int) -> List[StockDaily]:
        """Return forward daily bars after analysis_date, up to eval_window_days."""
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date > analysis_date))
                .order_by(StockDaily.date)
                .limit(eval_window_days)
            ).scalars().all()
            return list(rows)
