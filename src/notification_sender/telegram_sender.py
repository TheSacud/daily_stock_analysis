# -*- coding: utf-8 -*-
"""
Telegram \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 Telegram Bot API \u53d1\u9001 \u6587\u672c\u6d88\u606f
2. \u901a\u8fc7 Telegram Bot API \u53d1\u9001 \u56fe\u7247\u6d88\u606f
"""
import logging
from typing import Optional
import requests
import time
import re

from src.config import Config


logger = logging.getLogger(__name__)


class TelegramSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 Telegram config

        Args:
            config: config\u5bf9\u8c61
        """
        self._telegram_config = {
            'bot_token': getattr(config, 'telegram_bot_token', None),
            'chat_id': getattr(config, 'telegram_chat_id', None),
            'message_thread_id': getattr(config, 'telegram_message_thread_id', None),
        }

    def _is_telegram_configured(self) -> bool:
        """\u68c0check Telegram config\u662f\u5426\u5b8c\u6574"""
        return bool(self._telegram_config['bot_token'] and self._telegram_config['chat_id'])

    def send_to_telegram(
        self,
        content: str,
        *,
        chat_id: Optional[str] = None,
        message_thread_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 Telegram \u673a\u5668\u4eba

        Telegram Bot API \u683c\u5f0f:
        POST https://api.telegram.org/bot<token>/sendMessage
        {
            "chat_id": "xxx",
            "text": "\u6d88\u606f\u5185\u5bb9",
            "parse_mode": "Markdown"
        }

        Args:
            content: \u6d88\u606f\u5185\u5bb9 (Markdown \u683c\u5f0f)

        Returns:
            \u662f\u5426send succeeded
        """
        target_chat_id = chat_id if chat_id is not None else self._telegram_config.get("chat_id")
        target_message_thread_id = (
            message_thread_id
            if message_thread_id is not None
            else self._telegram_config.get("message_thread_id")
        )

        if not (self._telegram_config["bot_token"] and target_chat_id):
            logger.warning("Telegram config\u4e0d\u5b8c\u6574; skipping\u63a8\u9001")
            return False

        bot_token = self._telegram_config['bot_token']
        chat_id = target_chat_id
        message_thread_id = target_message_thread_id

        try:
            # Telegram API \u7aef\u70b9
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            # Telegram \u6d88\u606f\u6700\u5927\u957f\u5ea6 4096 \u5b57\u7b26
            max_length = 4096

            if len(content) <= max_length:
                # \u5355\u6761\u6d88\u606f\u53d1\u9001
                return self._send_telegram_message(api_url, chat_id, content, message_thread_id, timeout_seconds=timeout_seconds)
            else:
                # \u5206\u6bb5\u53d1\u9001\u957f\u6d88\u606f
                return self._send_telegram_chunked(api_url, chat_id, content, max_length, message_thread_id, timeout_seconds=timeout_seconds)

        except Exception as e:
            logger.error(f"\u53d1\u9001 Telegram \u6d88\u606ffailed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _send_telegram_message(
        self,
        api_url: str,
        chat_id: str,
        text: str,
        message_thread_id: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """Send a single Telegram message with exponential backoff retry (Fixes #287)"""
        # Convert Markdown to Telegram-compatible format
        telegram_text = self._convert_to_telegram_markdown(text)

        payload = {
            "chat_id": chat_id,
            "text": telegram_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }

        if message_thread_id:
            payload['message_thread_id'] = message_thread_id

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(api_url, json=payload, timeout=timeout_seconds or 10)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_retries:
                    delay = 2 ** attempt  # 2s, 4s
                    logger.warning(f"Telegram request failed (attempt {attempt}/{max_retries}): {e}, "
                                   f"retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Telegram request failed after {max_retries} attempts: {e}")
                    return False

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    error_desc = result.get('description', 'unknown error')
                    logger.error(f"Telegram \u8fd4\u56deerror: {error_desc}")

                    # If Markdown parsing failed, fall back to plain text
                    if self._should_fallback_to_plain_text(error_desc=error_desc):
                        if self._send_plain_text_fallback(api_url, payload, text, timeout_seconds=timeout_seconds):
                            return True

                    return False
            elif response.status_code == 429:
                # Rate limited — respect Retry-After header
                retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                if attempt < max_retries:
                    logger.warning(f"Telegram rate limited, retrying in {retry_after}s "
                                   f"(attempt {attempt}/{max_retries})...")
                    time.sleep(retry_after)
                    continue
                else:
                    logger.error(f"Telegram rate limited after {max_retries} attempts")
                    return False
            else:
                if attempt < max_retries and response.status_code >= 500:
                    delay = 2 ** attempt
                    logger.warning(f"Telegram server error HTTP {response.status_code} "
                                   f"(attempt {attempt}/{max_retries}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                if self._should_fallback_to_plain_text(response_text=response.text):
                    if self._send_plain_text_fallback(api_url, payload, text, timeout_seconds=timeout_seconds):
                        return True
                logger.error(f"Telegram requestfailed: HTTP {response.status_code}")
                logger.error(f"\u54cd\u5e94\u5185\u5bb9: {response.text}")
                return False

        return False

    @staticmethod
    def _should_fallback_to_plain_text(error_desc: str = "", response_text: str = "") -> bool:
        """Detect Telegram Markdown parsing failures that should retry as plain text."""
        haystack = f"{error_desc}\n{response_text}".lower()
        markers = (
            "can't parse entities",
            "can't parse entity",
            "can't find end of the entity",
            "parse entities",
            "parse_mode",
            "markdown",
        )
        return any(marker in haystack for marker in markers)

    def _send_plain_text_fallback(
        self,
        api_url: str,
        payload: dict,
        text: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """Retry Telegram send without parse_mode when Markdown parsing fails."""
        logger.info("Telegram Markdown parse failed; \u5c1d\u8bd5\u4f7f\u7528\u7eaf\u6587\u672c\u683c\u5f0f\u91cd\u65b0\u53d1\u9001...")
        plain_payload = dict(payload)
        plain_payload.pop('parse_mode', None)
        plain_payload['text'] = text

        try:
            response = requests.post(api_url, json=plain_payload, timeout=timeout_seconds or 10)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Telegram plain-text fallback failed: {e}")
            return False

        if response.status_code == 200:
            try:
                result = response.json()
            except ValueError:
                logger.error("Telegram \u7eaf\u6587\u672c\u56de\u9000failed: \u54cd\u5e94\u4e0d\u662f\u6709\u6548 JSON")
                logger.error(f"\u54cd\u5e94\u5185\u5bb9: {response.text}")
                return False

            if result.get('ok'):
                logger.info("Telegram message sent successfully (\u7eaf\u6587\u672c)")
                return True

            logger.error("Telegram \u7eaf\u6587\u672c\u56de\u9000failed: Telegram API \u8fd4\u56de ok=false")
            logger.error(f"\u54cd\u5e94\u5185\u5bb9: {response.text}")
            return False

        logger.error(f"Telegram \u7eaf\u6587\u672c\u56de\u9000failed: HTTP {response.status_code}")
        logger.error(f"\u54cd\u5e94\u5185\u5bb9: {response.text}")
        return False

    def _send_telegram_chunked(
        self,
        api_url: str,
        chat_id: str,
        content: str,
        max_length: int,
        message_thread_id: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """\u5206\u6bb5\u53d1\u9001\u957f Telegram \u6d88\u606f"""
        # \u6309\u6bb5\u843d\u5206\u5272
        sections = content.split("\n---\n")

        current_chunk = []
        current_length = 0
        all_success = True
        chunk_index = 1

        for section in sections:
            section_length = len(section) + 5  # +5 for "\n---\n"

            if current_length + section_length > max_length:
                # \u53d1\u9001\u5f53\u524dchunks
                if current_chunk:
                    chunk_content = "\n---\n".join(current_chunk)
                    logger.info(f"\u53d1\u9001 Telegram \u6d88\u606fchunks {chunk_index}...")
                    if not self._send_telegram_message(api_url, chat_id, chunk_content, message_thread_id, timeout_seconds=timeout_seconds):
                        all_success = False
                    chunk_index += 1

                # \u91cd\u7f6e
                current_chunk = [section]
                current_length = section_length
            else:
                current_chunk.append(section)
                current_length += section_length

        # \u53d1\u9001\u6700\u540e\u4e00chunks
        if current_chunk:
            chunk_content = "\n---\n".join(current_chunk)
            logger.info(f"\u53d1\u9001 Telegram \u6d88\u606fchunks {chunk_index}...")
            if not self._send_telegram_message(api_url, chat_id, chunk_content, message_thread_id, timeout_seconds=timeout_seconds):
                all_success = False

        return all_success

    def _send_telegram_photo(self, image_bytes: bytes) -> bool:
        """Send image via Telegram sendPhoto API (Issue #289)."""
        if not self._is_telegram_configured():
            return False
        bot_token = self._telegram_config['bot_token']
        chat_id = self._telegram_config['chat_id']
        message_thread_id = self._telegram_config.get('message_thread_id')
        api_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        try:
            data = {"chat_id": chat_id}
            if message_thread_id:
                data['message_thread_id'] = message_thread_id
            files = {"photo": ("report.png", image_bytes, "image/png")}
            response = requests.post(api_url, data=data, files=files, timeout=30)
            if response.status_code == 200 and response.json().get('ok'):
                logger.info("Telegram \u56fe\u7247send succeeded")
                return True
            logger.error("Telegram \u56fe\u7247send failed: %s", response.text[:200])
            return False
        except Exception as e:
            logger.error("Telegram \u56fe\u7247\u53d1\u9001\u5f02\u5e38: %s", e)
            return False

    def _convert_to_telegram_markdown(self, text: str) -> str:
        """
        \u5c06\u6807\u51c6 Markdown \u8f6c\u6362\u4e3a Telegram \u652f\u6301\u7684\u683c\u5f0f

        Telegram Markdown limit:
        - does not support # \u6807\u9898
        - \u4f7f\u7528 *bold* \u800c\u975e **bold**
        - \u4f7f\u7528 _italic_
        """
        result = text

        # \u79fb\u9664 # \u6807\u9898\u6807\u8bb0 (Telegram does not support)
        result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)

        # \u8f6c\u6362 **bold** \u4e3a *bold*
        result = re.sub(r'\*\*(.+?)\*\*', r'*\1*', result)

        # Escape special characters for Telegram Markdown, but preserve link syntax [text](url)
        # Step 1: temporarily protect markdown links
        import uuid as _uuid
        _link_placeholder = f"__LINK_{_uuid.uuid4().hex[:8]}__"
        _links = []
        def _save_link(m):
            _links.append(m.group(0))
            return f"{_link_placeholder}{len(_links) - 1}"
        result = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _save_link, result)

        # Step 2: escape remaining special chars
        for char in ['[', ']', '(', ')']:
            result = result.replace(char, f'\\{char}')

        # Step 3: restore links
        for i, link in enumerate(_links):
            result = result.replace(f"{_link_placeholder}{i}", link)

        return result
