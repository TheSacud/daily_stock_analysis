# -*- coding: utf-8 -*-
"""
===================================
\u80a1\u7968\u6570\u636e\u670d\u52a1\u5c42
===================================

\u804c\u8d23:
1. \u5c01\u88c5\u80a1\u7968\u6570\u636e\u83b7\u53d6\u903b\u8f91
2. \u63d0\u4f9brealtime quote\u548chistory\u6570\u636e\u63a5\u53e3
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from src.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class StockService:
    """
    \u80a1\u7968\u6570\u636e\u670d\u52a1

    \u5c01\u88c5\u80a1\u7968\u6570\u636e\u83b7\u53d6\u7684\u4e1a\u52a1\u903b\u8f91
    """

    def __init__(self):
        """\u521d\u59cb\u5316\u80a1\u7968\u6570\u636e\u670d\u52a1"""
        self.repo = StockRepository()

    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        \u83b7\u53d6\u80a1\u7968realtime quote

        Args:
            stock_code: stock code

        Returns:
            realtime quote\u6570\u636e\u5b57\u5178
        """
        try:
            # \u8c03\u7528\u6570\u636e\u83b7\u53d6\u5668\u83b7\u53d6realtime quote
            from data_provider.base import DataFetcherManager

            manager = DataFetcherManager()
            quote = manager.get_realtime_quote(stock_code)

            if quote is None:
                logger.warning(f"\u83b7\u53d6 {stock_code} realtime quotefailed")
                return None

            # UnifiedRealtimeQuote \u662f dataclass; \u4f7f\u7528 getattr \u5b89\u5168\u8bbfask\u5b57\u6bb5
            # \u5b57\u6bb5\u6620\u5c04: UnifiedRealtimeQuote -> API \u54cd\u5e94
            # - code -> stock_code
            # - name -> stock_name
            # - price -> current_price
            # - change_amount -> change
            # - change_pct -> change_percent
            # - open_price -> open
            # - high -> high
            # - low -> low
            # - pre_close -> prev_close
            # - volume -> volume
            # - amount -> amount
            return {
                "stock_code": getattr(quote, "code", stock_code),
                "stock_name": getattr(quote, "name", None),
                "current_price": getattr(quote, "price", 0.0) or 0.0,
                "change": getattr(quote, "change_amount", None),
                "change_percent": getattr(quote, "change_pct", None),
                "open": getattr(quote, "open_price", None),
                "high": getattr(quote, "high", None),
                "low": getattr(quote, "low", None),
                "prev_close": getattr(quote, "pre_close", None),
                "volume": getattr(quote, "volume", None),
                "amount": getattr(quote, "amount", None),
                "update_time": datetime.now().isoformat(),
            }

        except ImportError:
            logger.warning("DataFetcherManager \u672a\u627e\u5230; \u4f7f\u7528\u5360characters\u6570\u636e")
            return self._get_placeholder_quote(stock_code)
        except Exception as e:
            logger.error(f"\u83b7\u53d6realtime quotefailed: {e}", exc_info=True)
            return None

    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30
    ) -> Dict[str, Any]:
        """
        \u83b7\u53d6\u80a1\u7968history\u884c\u60c5

        Args:
            stock_code: stock code
            period: K \u7ebf\u5468\u671f (daily/weekly/monthly)
            days: \u83b7\u53d6\u5929\u6570

        Returns:
            history\u884c\u60c5\u6570\u636e\u5b57\u5178

        Raises:
            ValueError: \u5f53 period \u4e0d\u662f daily \u65f6\u629b\u51fa (weekly/monthly \u6682\u672a\u5b9e\u73b0)
        """
        # \u9a8c\u8bc1 period parameter; \u53ea\u652f\u6301 daily
        if period != "daily":
            raise ValueError(
                f"\u6682does not support '{period}' \u5468\u671f; \u76ee\u524d\u4ec5\u652f\u6301 'daily'."
                "weekly/monthly \u805a\u5408\u529f\u80fd\u5c06\u5728\u540e\u7eed\u7248\u672c\u5b9e\u73b0."
            )

        try:
            # \u8c03\u7528\u6570\u636e\u83b7\u53d6\u5668\u83b7\u53d6history\u6570\u636e
            from data_provider.base import DataFetcherManager

            manager = DataFetcherManager()
            df, source = manager.get_daily_data(stock_code, days=days)

            if df is None or df.empty:
                logger.warning(f"\u83b7\u53d6 {stock_code} history\u6570\u636efailed")
                return {"stock_code": stock_code, "period": period, "data": []}

            # \u83b7\u53d6stock name
            stock_name = manager.get_stock_name(stock_code)

            # \u8f6c\u6362\u4e3a\u54cd\u5e94\u683c\u5f0f
            data = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)

                data.append({
                    "date": date_str,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)) if row.get("volume") else None,
                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,
                    "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,
                })

            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "data": data,
            }

        except ImportError:
            logger.warning("DataFetcherManager \u672a\u627e\u5230; returned empty data")
            return {"stock_code": stock_code, "period": period, "data": []}
        except Exception as e:
            logger.error(f"\u83b7\u53d6history\u6570\u636efailed: {e}", exc_info=True)
            return {"stock_code": stock_code, "period": period, "data": []}

    def _get_placeholder_quote(self, stock_code: str) -> Dict[str, Any]:
        """
        \u83b7\u53d6\u5360characters\u884c\u60c5\u6570\u636e (\u7528\u4e8e\u6d4b\u8bd5)

        Args:
            stock_code: stock code

        Returns:
            \u5360characters\u884c\u60c5\u6570\u636e
        """
        return {
            "stock_code": stock_code,
            "stock_name": f"\u80a1\u7968{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": datetime.now().isoformat(),
        }
