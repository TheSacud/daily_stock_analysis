# -*- coding: utf-8 -*-
"""
===================================
batchanalyzecommand
===================================

batchanalyzewatchlist\u5217\u8868Medium\u7684\u6240\u6709\u80a1\u7968.
"""

import logging
import threading
import uuid
from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class BatchCommand(BotCommand):
    """
    batchanalyzecommand

    batchanalyzeconfigMedium\u7684watchlist\u5217\u8868; \u751f\u6210\u6c47\u603breport.

    Usage:
        /batch      - analyze\u6240\u6709watchlist
        /batch 3    - \u53eaanalyze\u524d3\u53ea
    """

    @property
    def name(self) -> str:
        return "batch"

    @property
    def aliases(self) -> List[str]:
        return ["b", "batch", "all"]

    @property
    def description(self) -> str:
        return "batchanalyzewatchlist"

    @property
    def usage(self) -> str:
        return "/batch [count]"

    @property
    def admin_only(self) -> bool:
        """batchanalyze\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650 (\u9632\u6b62\u6ee5\u7528)"""
        return False  # can be set to True when needed

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """\u6267\u884cbatchanalyzecommand"""
        from src.config import get_config

        config = get_config()
        config.refresh_stock_list()

        stock_list = config.stock_list

        if not stock_list:
            return BotResponse.error_response(
                "watchlist\u5217\u8868\u4e3a\u7a7a; \u8bf7\u5148config STOCK_LIST"
            )

        # \u89e3\u6790countparameter
        limit = None
        if args:
            try:
                limit = int(args[0])
                if limit <= 0:
                    return BotResponse.error_response("count must be greater than 0")
            except ValueError:
                return BotResponse.error_response(f"invalid count: {args[0]}")

        # limitanalyzecount
        if limit:
            stock_list = stock_list[:limit]

        logger.info(f"[BatchCommand] \u5f00\u59cbbatchanalyze {len(stock_list)} stocks")

        # \u5728\u540e\u53f0\u7ebf\u7a0bMedium\u6267\u884canalyze
        thread = threading.Thread(
            target=self._run_batch_analysis,
            args=(stock_list, message),
            daemon=True
        )
        thread.start()

        return BotResponse.markdown_response(
            f"✅ **batchanalysis task\u5df2started**\n\n"
            f"• analyzecount: {len(stock_list)} \u53ea\n"
            f"• \u80a1\u7968\u5217\u8868: {', '.join(stock_list[:5])}"
            f"{'...' if len(stock_list) > 5 else ''}\n\n"
            f"analysis completed\u540e\u5c06\u81ea\u52a8\u63a8\u9001\u6c47\u603breport."
        )

    def _run_batch_analysis(self, stock_list: List[str], message: BotMessage) -> None:
        """\u540e\u53f0\u6267\u884cbatchanalyze"""
        try:
            from src.config import get_config
            from main import StockAnalysisPipeline

            config = get_config()

            # \u521b\u5efaanalyze\u7ba1\u9053
            pipeline = StockAnalysisPipeline(
                config=config,
                source_message=message,
                query_id=uuid.uuid4().hex,
                query_source="bot"
            )

            # \u6267\u884canalyze (\u4f1a\u81ea\u52a8\u63a8\u9001\u6c47\u603breport)
            results = pipeline.run(
                stock_codes=stock_list,
                dry_run=False,
                send_notification=True
            )

            logger.info(f"[BatchCommand] batchanalysis completed; success {len(results)} \u53ea")

        except Exception as e:
            logger.error(f"[BatchCommand] batchanalyzefailed: {e}")
            logger.exception(e)
