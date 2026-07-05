# -*- coding: utf-8 -*-
"""
Discord \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 webhook or Discord bot API \u53d1\u9001 Discord \u6d88\u606f
"""
import logging
import time
from typing import Optional

import requests

from src.config import Config
from src.formatters import MIN_MAX_WORDS, chunk_content_by_max_words


logger = logging.getLogger(__name__)


DISCORD_MAX_CONTENT_LENGTH = 2000
DISCORD_MAX_RETRIES = 3
DISCORD_CHUNK_SLEEP_SECONDS = 1


class DiscordSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 Discord config

        Args:
            config: config\u5bf9\u8c61
        """
        self._discord_config = {
            'bot_token': getattr(config, 'discord_bot_token', None),
            'channel_id': getattr(config, 'discord_main_channel_id', None),
            'webhook_url': getattr(config, 'discord_webhook_url', None),
        }
        self._discord_max_words = self._normalize_max_words(
            getattr(config, 'discord_max_words', DISCORD_MAX_CONTENT_LENGTH)
        )
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    @staticmethod
    def _normalize_max_words(value) -> int:
        try:
            configured = int(value)
        except (TypeError, ValueError):
            configured = DISCORD_MAX_CONTENT_LENGTH
        return max(MIN_MAX_WORDS, min(configured, DISCORD_MAX_CONTENT_LENGTH))

    def _is_discord_configured(self) -> bool:
        """\u68c0check Discord config\u662f\u5426\u5b8c\u6574 (\u652f\u6301 Bot or Webhook)"""
        # \u53ea\u8981config\u4e86 Webhook or\u5b8c\u6574\u7684 Bot Token+Channel; \u5373\u89c6\u4e3a\u53ef\u7528
        bot_ok = bool(self._discord_config['bot_token'] and self._discord_config['channel_id'])
        webhook_ok = bool(self._discord_config['webhook_url'])
        return bot_ok or webhook_ok

    def send_to_discord(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 Discord (\u652f\u6301 Webhook \u548c Bot API)

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        # \u5206\u5272\u5185\u5bb9; \u907f\u514d\u5355\u6761\u6d88\u606f\u8d85\u8fc7 Discord limit
        chunks = self._split_discord_content(content)

        # \u4f18\u5148\u4f7f\u7528 Webhook (config\u7b80\u5355; \u6743\u9650Low)
        if self._discord_config['webhook_url']:
            return self._send_discord_chunks(
                chunks,
                self._send_discord_webhook,
                "Webhook",
                timeout_seconds=timeout_seconds,
            )

        # \u5176\u6b21\u4f7f\u7528 Bot API (\u6743\u9650High; \u9700\u8981 channel_id)
        if self._discord_config['bot_token'] and self._discord_config['channel_id']:
            return self._send_discord_chunks(
                chunks,
                self._send_discord_bot,
                "Bot",
                timeout_seconds=timeout_seconds,
            )

        logger.warning("Discord config\u4e0d\u5b8c\u6574; skipping\u63a8\u9001")
        return False

    def _split_discord_content(self, content: str) -> list[str]:
        """\u6309 Discord content \u4e0a\u9650\u62c6\u5206\u6d88\u606f."""
        try:
            chunks = chunk_content_by_max_words(content, self._discord_max_words)
            if len(chunks) > 1:
                chunks = chunk_content_by_max_words(
                    content,
                    self._discord_max_words,
                    add_page_marker=True,
                )
            return chunks
        except ValueError as e:
            logger.error("\u5206\u5272 Discord \u6d88\u606ffailed: %s", e)
            return chunk_content_by_max_words(
                content,
                DISCORD_MAX_CONTENT_LENGTH,
                add_page_marker=True,
            )

    def _send_discord_chunks(
        self,
        chunks: list[str],
        send_once,
        channel_name: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """\u9010\u7247\u53d1\u9001 Discord \u6d88\u606f；failed\u7247\u4e0d\u5e94\u963b\u65ad\u540e\u7eed\u7247\u5c1d\u8bd5."""
        total_chunks = len(chunks)
        success_count = 0

        if total_chunks > 1:
            logger.info("Discord %s \u5206\u6279\u53d1\u9001: \u5171 %d \u6279", channel_name, total_chunks)

        for i, chunk in enumerate(chunks):
            if send_once(chunk, timeout_seconds=timeout_seconds):
                success_count += 1
                if total_chunks > 1:
                    logger.info("Discord %s \u7b2c %d/%d \u6279send succeeded", channel_name, i + 1, total_chunks)
            else:
                logger.error("Discord %s \u7b2c %d/%d \u6279send failed", channel_name, i + 1, total_chunks)

            if i < total_chunks - 1:
                time.sleep(DISCORD_CHUNK_SLEEP_SECONDS)

        return success_count == total_chunks


    def _send_discord_webhook(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u4f7f\u7528 Webhook \u53d1\u9001\u6d88\u606f\u5230 Discord

        Discord Webhook \u652f\u6301 Markdown \u683c\u5f0f

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        payload = {
            'content': content,
            'username': 'A-shareanalyze\u673a\u5668\u4eba',
            'avatar_url': 'https://picsum.photos/200'
        }

        return self._post_discord_message(
            self._discord_config['webhook_url'],
            payload,
            success_statuses=(200, 204),
            verify=self._webhook_verify_ssl,
            timeout_seconds=timeout_seconds,
            channel_name="Webhook",
        )

    def _send_discord_bot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u4f7f\u7528 Bot API \u53d1\u9001\u6d88\u606f\u5230 Discord

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        headers = {
            'Authorization': f'Bot {self._discord_config["bot_token"]}',
            'Content-Type': 'application/json'
        }
        payload = {'content': content}
        url = f'https://discord.com/api/v10/channels/{self._discord_config["channel_id"]}/messages'

        return self._post_discord_message(
            url,
            payload,
            headers=headers,
            success_statuses=(200,),
            timeout_seconds=timeout_seconds,
            channel_name="Bot",
        )

    def _post_discord_message(
        self,
        url: str,
        payload: dict,
        *,
        success_statuses: tuple[int, ...],
        headers: Optional[dict] = None,
        verify: Optional[bool] = None,
        timeout_seconds: Optional[float] = None,
        channel_name: str,
    ) -> bool:
        """\u53d1\u9001\u5355\u6761 Discord \u6d88\u606f; \u5e76\u590d\u7528 Telegram \u7684\u6709\u9650\u91cd\u8bd5\u601d\u8def\u5904\u7406 429/5xx."""
        request_kwargs = {
            'json': payload,
            'timeout': timeout_seconds or 10,
        }
        if headers:
            request_kwargs['headers'] = headers
        if verify is not None:
            request_kwargs['verify'] = verify

        for attempt in range(1, DISCORD_MAX_RETRIES + 1):
            try:
                response = requests.post(url, **request_kwargs)
            except requests.exceptions.RequestException as e:
                if attempt < DISCORD_MAX_RETRIES:
                    delay = 2 ** attempt
                    logger.warning(
                        "Discord %s request\u5f02\u5e38 (%d/%d): %s; %s \u79d2\u540e\u91cd\u8bd5",
                        channel_name,
                        attempt,
                        DISCORD_MAX_RETRIES,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                logger.error("Discord %s request\u91cd\u8bd5\u540e\u4ecdfailed: %s", channel_name, e)
                return False

            if response.status_code in success_statuses:
                logger.info("Discord %s message sent successfully", channel_name)
                return True

            if response.status_code == 429 and attempt < DISCORD_MAX_RETRIES:
                retry_after = self._get_retry_after_seconds(response, attempt)
                logger.warning(
                    "Discord %s \u89e6\u53d1\u9650\u6d41; %s \u79d2\u540e\u91cd\u8bd5 (%d/%d)",
                    channel_name,
                    retry_after,
                    attempt,
                    DISCORD_MAX_RETRIES,
                )
                time.sleep(retry_after)
                continue

            if response.status_code >= 500 and attempt < DISCORD_MAX_RETRIES:
                delay = 2 ** attempt
                logger.warning(
                    "Discord %s \u670d\u52a1\u7aeferror HTTP %s (%d/%d); %s \u79d2\u540e\u91cd\u8bd5",
                    channel_name,
                    response.status_code,
                    attempt,
                    DISCORD_MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                continue

            logger.error(
                "Discord %s send failed: %s %s",
                channel_name,
                response.status_code,
                response.text,
            )
            return False

        return False

    @staticmethod
    def _get_retry_after_seconds(response, attempt: int) -> float:
        try:
            retry_after = response.json().get('retry_after')
            if retry_after is not None:
                return max(0.0, float(retry_after))
        except (AttributeError, TypeError, ValueError):
            pass

        try:
            retry_after = response.headers.get('Retry-After')
            if retry_after is not None:
                return max(0.0, float(retry_after))
        except AttributeError:
            pass

        return float(2 ** attempt)
