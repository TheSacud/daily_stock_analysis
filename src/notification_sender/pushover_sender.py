# -*- coding: utf-8 -*-
"""
Pushover \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 Pushover API \u53d1\u9001 Pushover \u6d88\u606f
"""
import logging
from typing import Optional
from datetime import datetime
import requests

from src.config import Config
from src.formatters import markdown_to_plain_text


logger = logging.getLogger(__name__)


class PushoverSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 Pushover config

        Args:
            config: config\u5bf9\u8c61
        """
        self._pushover_config = {
            'user_key': getattr(config, 'pushover_user_key', None),
            'api_token': getattr(config, 'pushover_api_token', None),
        }

    def _is_pushover_configured(self) -> bool:
        """\u68c0check Pushover config\u662f\u5426\u5b8c\u6574"""
        return bool(self._pushover_config['user_key'] and self._pushover_config['api_token'])

    def send_to_pushover(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 Pushover

        Pushover API \u683c\u5f0f:
        POST https://api.pushover.net/1/messages.json
        {
            "token": "\u5e94\u7528 API Token",
            "user": "user Key",
            "message": "\u6d88\u606f\u5185\u5bb9",
            "title": "\u6807\u9898 (optional)"
        }

        Pushover \u7279\u70b9:
        - \u652f\u6301 iOS/Android/\u684c\u9762\u591a\u5e73\u53f0\u63a8\u9001
        - \u6d88\u606flimit 1024 \u5b57\u7b26
        - \u652f\u6301\u4f18\u5148\u7ea7\u8bbe\u7f6e
        - \u652f\u6301 HTML \u683c\u5f0f

        Args:
            content: \u6d88\u606f\u5185\u5bb9 (Markdown \u683c\u5f0f; \u4f1a\u8f6c\u4e3a\u7eaf\u6587\u672c)
            title: \u6d88\u606f\u6807\u9898 (optional; default\u4e3a"\u80a1\u7968analyzereport")

        Returns:
            \u662f\u5426send succeeded
        """
        if not self._is_pushover_configured():
            logger.warning("Pushover config\u4e0d\u5b8c\u6574; skipping\u63a8\u9001")
            return False

        user_key = self._pushover_config['user_key']
        api_token = self._pushover_config['api_token']

        # Pushover API \u7aef\u70b9
        api_url = "https://api.pushover.net/1/messages.json"

        # \u5904\u7406\u6d88\u606f\u6807\u9898
        if title is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            title = f"📈 \u80a1\u7968analyzereport - {date_str}"

        # Pushover \u6d88\u606flimit 1024 \u5b57\u7b26
        max_length = 1024

        # \u8f6c\u6362 Markdown \u4e3a\u7eaf\u6587\u672c (Pushover \u652f\u6301 HTML; \u4f46\u7eaf\u6587\u672c\u66f4\u901a\u7528)
        plain_content = markdown_to_plain_text(content)

        if len(plain_content) <= max_length:
            # \u5355\u6761\u6d88\u606f\u53d1\u9001
            return self._send_pushover_message(api_url, user_key, api_token, plain_content, title, timeout_seconds=timeout_seconds)
        else:
            # \u5206\u6bb5\u53d1\u9001\u957f\u6d88\u606f
            return self._send_pushover_chunked(
                api_url,
                user_key,
                api_token,
                plain_content,
                title,
                max_length,
                timeout_seconds=timeout_seconds,
            )

    def _send_pushover_message(
        self,
        api_url: str,
        user_key: str,
        api_token: str,
        message: str,
        title: str,
        priority: int = 0,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u53d1\u9001\u5355\u6761 Pushover \u6d88\u606f

        Args:
            api_url: Pushover API \u7aef\u70b9
            user_key: user Key
            api_token: \u5e94\u7528 API Token
            message: \u6d88\u606f\u5185\u5bb9
            title: \u6d88\u606f\u6807\u9898
            priority: \u4f18\u5148\u7ea7 (-2 ~ 2; default 0)
        """
        try:
            payload = {
                "token": api_token,
                "user": user_key,
                "message": message,
                "title": title,
                "priority": priority,
            }

            response = requests.post(api_url, data=payload, timeout=timeout_seconds or 30)

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 1:
                    logger.info("Pushover message sent successfully")
                    return True
                else:
                    errors = result.get('errors', ['unknown error'])
                    logger.error(f"Pushover \u8fd4\u56deerror: {errors}")
                    return False
            else:
                logger.error(f"Pushover requestfailed: HTTP {response.status_code}")
                logger.debug(f"\u54cd\u5e94\u5185\u5bb9: {response.text}")
                return False

        except Exception as e:
            logger.error(f"\u53d1\u9001 Pushover \u6d88\u606ffailed: {e}")
            return False

    def _send_pushover_chunked(
        self,
        api_url: str,
        user_key: str,
        api_token: str,
        content: str,
        title: str,
        max_length: int,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u5206\u6bb5\u53d1\u9001\u957f Pushover \u6d88\u606f

        \u6309\u6bb5\u843d\u5206\u5272; \u786e\u4fdd\u6bcf\u6bb5\u4e0d\u8d85\u8fc7\u6700\u5927\u957f\u5ea6
        """
        import time

        # \u6309\u6bb5\u843d (\u5206\u9694\u7ebfor\u53cc\u6362\u884c)\u5206\u5272
        if "────────" in content:
            sections = content.split("────────")
            separator = "────────"
        else:
            sections = content.split("\n\n")
            separator = "\n\n"

        chunks = []
        current_chunk = []
        current_length = 0

        for section in sections:
            # \u8ba1\u7b97\u6dfb\u52a0\u8fd9\u4e2a section \u540e\u7684\u5b9e\u9645\u957f\u5ea6
            # join() \u53ea\u5728\u5143\u7d20\u4e4b\u95f4\u653e\u7f6e\u5206\u9694\u7b26; \u4e0d\u662f\u6bcf\u4e2a\u5143\u7d20\u540e\u9762
            # \u6240\u4ee5: \u7b2c\u4e00\u4e2a\u5143\u7d20\u4e0d\u9700\u8981\u5206\u9694\u7b26; \u540e\u7eed\u5143\u7d20\u9700\u8981\u4e00\u4e2a\u5206\u9694\u7b26\u8fde\u63a5
            if current_chunk:
                # \u5df2\u6709\u5143\u7d20; \u6dfb\u52a0\u65b0\u5143\u7d20\u9700\u8981: \u5f53\u524d\u957f\u5ea6 + \u5206\u9694\u7b26 + \u65b0 section
                new_length = current_length + len(separator) + len(section)
            else:
                # \u7b2c\u4e00\u4e2a\u5143\u7d20; \u4e0d\u9700\u8981\u5206\u9694\u7b26
                new_length = len(section)

            if new_length > max_length:
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                current_chunk = [section]
                current_length = len(section)
            else:
                current_chunk.append(section)
                current_length = new_length

        if current_chunk:
            chunks.append(separator.join(current_chunk))

        total_chunks = len(chunks)
        success_count = 0

        logger.info(f"Pushover \u5206\u6279\u53d1\u9001: \u5171 {total_chunks} \u6279")

        for i, chunk in enumerate(chunks):
            # \u6dfb\u52a0\u5206\u9875\u6807\u8bb0\u5230\u6807\u9898
            chunk_title = f"{title} ({i+1}/{total_chunks})" if total_chunks > 1 else title

            if self._send_pushover_message(
                api_url,
                user_key,
                api_token,
                chunk,
                chunk_title,
                timeout_seconds=timeout_seconds,
            ):
                success_count += 1
                logger.info(f"Pushover \u7b2c {i+1}/{total_chunks} \u6279send succeeded")
            else:
                logger.error(f"Pushover \u7b2c {i+1}/{total_chunks} \u6279send failed")

            # \u6279\u6b21\u95f4\u9694; \u907f\u514d\u89e6\u53d1\u9891\u7387limit
            if i < total_chunks - 1:
                time.sleep(1)

        return success_count == total_chunks
