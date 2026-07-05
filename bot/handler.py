# -*- coding: utf-8 -*-
"""
===================================
Bot Webhook \u5904\u7406\u5668
===================================

\u5904\u7406\u5404\u5e73\u53f0\u7684 Webhook \u56de\u8c03; \u5206\u53d1\u5230command\u5904\u7406\u5668.
"""

import asyncio
import json
import logging
import threading
from typing import Dict, Optional, TYPE_CHECKING

from bot.models import WebhookResponse
from bot.dispatcher import get_dispatcher
from bot.platforms import ALL_PLATFORMS

if TYPE_CHECKING:
    from bot.platforms.base import BotPlatform  # noqa: F401

logger = logging.getLogger(__name__)

# \u5e73\u53f0\u5b9e\u4f8bcache
_platform_instances: Dict[str, 'BotPlatform'] = {}


def get_platform(platform_name: str) -> Optional['BotPlatform']:
    """
    \u83b7\u53d6\u5e73\u53f0\u9002\u914d\u5668\u5b9e\u4f8b

    \u4f7f\u7528cache\u907f\u514d\u91cd\u590d\u521b\u5efa.

    Args:
        platform_name: \u5e73\u53f0name

    Returns:
        \u5e73\u53f0\u9002\u914d\u5668\u5b9e\u4f8b; or None
    """
    if platform_name not in _platform_instances:
        platform_class = ALL_PLATFORMS.get(platform_name)
        if platform_class:
            _platform_instances[platform_name] = platform_class()
        else:
            logger.warning(f"[BotHandler] unknown platform: {platform_name}")
            return None

    return _platform_instances[platform_name]


def handle_webhook(
    platform_name: str,
    headers: Dict[str, str],
    body: bytes,
    query_params: Optional[Dict[str, list]] = None
) -> WebhookResponse:
    """
    \u5904\u7406 Webhook request

    \u8fd9\u662f\u6240\u6709\u5e73\u53f0 Webhook \u7684\u7edf\u4e00\u5165\u53e3.

    Args:
        platform_name: \u5e73\u53f0name (feishu, dingtalk, wecom, telegram)
        headers: HTTP request\u5934
        body: request\u4f53\u539f\u59cb\u5b57\u8282
        query_params: URL queryparameter (\u7528\u4e8e\u67d0\u4e9b\u5e73\u53f0\u7684\u9a8c\u8bc1)

    Returns:
        WebhookResponse \u54cd\u5e94\u5bf9\u8c61
    """
    logger.info(f"[BotHandler] received {platform_name} Webhook request")

    # \u68c0check\u673a\u5668\u4eba\u529f\u80fd\u662f\u5426\u542f\u7528
    from src.config import get_config
    config = get_config()

    if not getattr(config, 'bot_enabled', True):
        logger.info("[BotHandler] bot feature is disabled")
        return WebhookResponse.success()

    # \u83b7\u53d6\u5e73\u53f0\u9002\u914d\u5668
    platform = get_platform(platform_name)
    if not platform:
        return WebhookResponse.error(f"Unknown platform: {platform_name}", 400)

    # \u89e3\u6790 JSON \u6570\u636e
    try:
        data = json.loads(body.decode('utf-8')) if body else {}
    except json.JSONDecodeError as e:
        logger.error(f"[BotHandler] JSON parse failed: {e}")
        return WebhookResponse.error("Invalid JSON", 400)

    logger.debug(f"[BotHandler] request\u6570\u636e: {json.dumps(data, ensure_ascii=False)[:500]}")

    # \u5904\u7406 Webhook
    message, immediate_response = platform.handle_webhook(headers, body, data)

    # \u5982\u679c\u662f\u9a8c\u8bc1/error\u54cd\u5e94\u4e14\u6ca1\u6709\u6d88\u606f\u9700\u8981\u5904\u7406; \u76f4\u63a5\u8fd4\u56de
    if immediate_response and not message:
        logger.info("[BotHandler] returned verification response")
        return immediate_response

    # \u5ef6\u8fdf\u54cd\u5e94 (\u5982 Discord type 5): \u7acb\u5373\u8fd4\u56de ACK; processing command in background
    if immediate_response and message:
        logger.info("[BotHandler] returned delayed ACK; processing command in background")

        def _deferred_dispatch() -> None:
            try:
                dispatcher = get_dispatcher()
                response = dispatcher.dispatch(message)
                if response.text:
                    platform.send_followup(response, message)
            except Exception as exc:
                logger.error("[BotHandler] delayed command processing failed: %s", exc)

        threading.Thread(target=_deferred_dispatch, daemon=True).start()
        return immediate_response

    # \u5982\u679c\u6ca1\u6709\u6d88\u606f\u9700\u8981\u5904\u7406; \u8fd4\u56de\u7a7a\u54cd\u5e94
    if not message:
        logger.debug("[BotHandler] message does not need handling")
        return WebhookResponse.success()

    logger.info(f"[BotHandler] parsed message: user={message.user_name}, content={message.content[:50]}")

    # \u5206\u53d1\u5230command\u5904\u7406\u5668
    dispatcher = get_dispatcher()
    response = dispatcher.dispatch(message)

    # \u683c\u5f0f\u5316\u54cd\u5e94
    if response.text:
        webhook_response = platform.format_response(response, message)
        return webhook_response

    return WebhookResponse.success()


async def handle_webhook_async(
    platform_name: str,
    headers: Dict[str, str],
    body: bytes,
    query_params: Optional[Dict[str, list]] = None
) -> WebhookResponse:
    """Async version of :func:`handle_webhook`.

    Preferred when called from an async context (e.g. FastAPI endpoint)
    to avoid blocking the event loop.
    """
    logger.info(f"[BotHandler] received {platform_name} Webhook request (async)")

    from src.config import get_config
    config = get_config()

    if not getattr(config, 'bot_enabled', True):
        logger.info("[BotHandler] bot feature is disabled")
        return WebhookResponse.success()

    platform = get_platform(platform_name)
    if not platform:
        return WebhookResponse.error(f"Unknown platform: {platform_name}", 400)

    try:
        data = json.loads(body.decode('utf-8')) if body else {}
    except json.JSONDecodeError as e:
        logger.error(f"[BotHandler] JSON parse failed: {e}")
        return WebhookResponse.error("Invalid JSON", 400)

    logger.debug(f"[BotHandler] request\u6570\u636e: {json.dumps(data, ensure_ascii=False)[:500]}")

    message, immediate_response = platform.handle_webhook(headers, body, data)

    if immediate_response and not message:
        logger.info("[BotHandler] returned verification response")
        return immediate_response

    if immediate_response and message:
        logger.info("[BotHandler] returned delayed ACK; processing command in background (async)")

        async def _deferred_dispatch() -> None:
            try:
                dispatcher = get_dispatcher()
                response = await dispatcher.dispatch_async(message)
                if response.text:
                    await asyncio.to_thread(platform.send_followup, response, message)
            except Exception as exc:
                logger.error("[BotHandler] delayed command processing failed: %s", exc)

        asyncio.ensure_future(_deferred_dispatch())
        return immediate_response

    if not message:
        logger.debug("[BotHandler] message does not need handling")
        return WebhookResponse.success()

    logger.info(f"[BotHandler] parsed message: user={message.user_name}, content={message.content[:50]}")

    dispatcher = get_dispatcher()
    response = await dispatcher.dispatch_async(message)

    if response.text:
        webhook_response = platform.format_response(response, message)
        return webhook_response

    return WebhookResponse.success()


def handle_feishu_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """\u5904\u7406Feishu Webhook"""
    return handle_webhook('feishu', headers, body)


def handle_dingtalk_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """\u5904\u7406DingTalk Webhook"""
    return handle_webhook('dingtalk', headers, body)


def handle_wecom_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """\u5904\u7406WeCom Webhook"""
    return handle_webhook('wecom', headers, body)


def handle_telegram_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """\u5904\u7406 Telegram Webhook"""
    return handle_webhook('telegram', headers, body)
