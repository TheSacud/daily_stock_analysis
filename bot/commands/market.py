# -*- coding: utf-8 -*-
"""
===================================
market reviewcommand
===================================

\u6267\u884cmarket reviewanalyze; \u751f\u6210market\u6982\u89c8report.
"""

import logging
import threading
from typing import Any, List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class MarketCommand(BotCommand):
    """
    market reviewcommand

    \u6267\u884cmarket reviewanalyze; \u5305\u62ec:
    - \u4e3b\u8981index\u8868\u73b0
    - sector\u70ed\u70b9
    - market\u60c5\u7eea
    - \u540e\u5e02\u5c55\u671b

    Usage:
        /market - \u6267\u884cmarket review
    """

    @property
    def name(self) -> str:
        return "market"

    @property
    def aliases(self) -> List[str]:
        return ["m", "\u5927\u76d8", "\u590d\u76d8", "\u884c\u60c5"]

    @property
    def description(self) -> str:
        return "market reviewanalyze"

    @property
    def usage(self) -> str:
        return "/market"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """\u6267\u884cmarket reviewcommand"""
        config = self._get_config()
        lock_token = self._try_acquire_market_review_lock(config)
        if lock_token is None:
            return BotResponse.markdown_response("⚠️ market reviewis already running; please try again later.")

        thread = threading.Thread(
            target=self._run_market_review,
            args=(message, config, lock_token),
            daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            logger.error(
                "[MarketCommand] market review\u540e\u53f0\u7ebf\u7a0bstartedfailed: %s",
                exc,
            )
            self._release_market_review_lock(lock_token)
            return BotResponse.error_response(
                "market reviewstartedfailed; \u5df2\u91ca\u653e\u8fd0\u884c\u9501；\u8bf7\u7a0d\u540e\u91cd\u8bd5"
            )

        return BotResponse.markdown_response(
            "✅ **market reviewtask\u5df2started**\n\n"
            "\u6b63\u5728analyze: \n"
            "• \u4e3b\u8981index\u8868\u73b0\n"
            "• sector\u70ed\u70b9analyze\n"
            "• market\u60c5\u7eea\u5224\u65ad\n"
            "• \u540e\u5e02\u5c55\u671b\n\n"
            "analysis completed\u540e\u5c06\u81ea\u52a8\u63a8\u9001result."
        )

    def _get_config(self):
        from src.config import get_config
        return get_config()

    def _try_acquire_market_review_lock(self, config):
        from src.core.market_review_lock import try_acquire_market_review_lock
        return try_acquire_market_review_lock(config)

    def _release_market_review_lock(self, lock_token: Optional[Any]) -> None:
        from src.core.market_review_lock import release_market_review_lock
        release_market_review_lock(lock_token)

    def _compute_market_review_override_region(self, config) -> Optional[str]:
        if not getattr(config, "trading_day_check_enabled", True):
            return None

        try:
            from src.core.trading_calendar import (
                get_open_markets_today,
                compute_effective_region,
            )

            open_markets = get_open_markets_today()
            return compute_effective_region(
                getattr(config, "market_review_region", "cn") or "cn",
                open_markets,
            )
        except Exception as exc:
            logger.warning("\u4ea4\u6613\u65e5\u8fc7\u6ee4failed; \u6309config\u7ee7\u7eed\u6267\u884cmarket review: %s", exc)
            return None

    def _run_market_review(
        self,
        message: BotMessage,
        config,
        lock_token: Optional[Any],
    ) -> None:
        """\u540e\u53f0\u6267\u884cmarket review"""
        try:
            override_region = self._compute_market_review_override_region(config)
            if override_region == "":
                from src.notification import NotificationService
                notifier = NotificationService(source_message=message)
                logger.info("[MarketCommand] \u4eca\u65e5\u76f8\u5173market\u4f11\u5e02; skippingmarket review")
                if notifier.is_available():
                    notifier.send(
                        "🎯 market review\n\n\u4eca\u65e5\u76f8\u5173market\u4f11\u5e02; \u5df2skippingmarket review.",
                        email_send_to_all=True,
                        route_type="report",
                    )
                return

            from src.core.market_review_runtime import build_market_review_runtime
            from src.core.market_review import run_market_review

            notifier, analyzer, search_service = build_market_review_runtime(
                config,
                source_message=message,
            )
            review_report = run_market_review(
                notifier=notifier,
                analyzer=analyzer,
                search_service=search_service,
                send_notification=True,
                override_region=override_region,
                trigger_source="bot",
            )
            if review_report:
                logger.info("[MarketCommand] market review\u5b8c\u6210\u5e76\u5df2\u63a8\u9001")
            else:
                logger.warning("[MarketCommand] market reviewreturned empty result")
        except Exception as e:
            logger.error("[MarketCommand] market reviewfailed: %s", e)
            logger.exception(e)
        finally:
            self._release_market_review_lock(lock_token)
