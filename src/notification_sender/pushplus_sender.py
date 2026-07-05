# -*- coding: utf-8 -*-
"""
PushPlus \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 PushPlus API \u53d1\u9001 PushPlus \u6d88\u606f
"""
import logging
import time
from typing import Optional
from datetime import datetime
import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes


logger = logging.getLogger(__name__)


class PushplusSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 PushPlus config

        Args:
            config: config\u5bf9\u8c61
        """
        self._pushplus_token = getattr(config, 'pushplus_token', None)
        self._pushplus_topic = getattr(config, 'pushplus_topic', None)
        self._pushplus_max_bytes = getattr(config, 'pushplus_max_bytes', 20000)

    def send_to_pushplus(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 PushPlus

        PushPlus API \u683c\u5f0f:
        POST http://www.pushplus.plus/send
        {
            "token": "user\u4ee4\u724c",
            "title": "\u6d88\u606f\u6807\u9898",
            "content": "\u6d88\u606f\u5185\u5bb9",
            "template": "html/txt/json/markdown"
        }

        PushPlus \u7279\u70b9:
        - \u56fd\u5185\u63a8\u9001\u670d\u52a1; \u514d\u8d39\u989d\u5ea6\u5145\u8db3
        - \u652f\u6301\u5fae\u4fe1\u516c\u4f17\u53f7\u63a8\u9001
        - \u652f\u6301\u591a\u79cd\u6d88\u606f\u683c\u5f0f

        Args:
            content: \u6d88\u606f\u5185\u5bb9 (Markdown \u683c\u5f0f)
            title: \u6d88\u606f\u6807\u9898 (optional)

        Returns:
            \u662f\u5426send succeeded
        """
        if not self._pushplus_token:
            logger.warning("PushPlus Token not configured; skipping\u63a8\u9001")
            return False

        api_url = "http://www.pushplus.plus/send"

        if title is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            title = f"📈 \u80a1\u7968analyzereport - {date_str}"

        try:
            content_bytes = len(content.encode('utf-8'))
            if content_bytes > self._pushplus_max_bytes:
                logger.info(
                    "PushPlus \u6d88\u606f\u5185\u5bb9\u8d85\u957f(%s\u5b57\u8282/%s\u5b57\u7b26); \u5c06\u5206\u6279\u53d1\u9001",
                    content_bytes,
                    len(content),
                )
                return self._send_pushplus_chunked(
                    api_url,
                    content,
                    title,
                    self._pushplus_max_bytes,
                )

            return self._send_pushplus_message(api_url, content, title, timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.error(f"\u53d1\u9001 PushPlus \u6d88\u606ffailed: {e}")
            return False

    def _send_pushplus_message(
        self,
        api_url: str,
        content: str,
        title: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        payload = {
            "token": self._pushplus_token,
            "title": title,
            "content": content,
            "template": "markdown",
        }

        if self._pushplus_topic:
            payload["topic"] = self._pushplus_topic

        response = requests.post(api_url, json=payload, timeout=timeout_seconds or 10)

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                logger.info("PushPlus message sent successfully")
                return True

            error_msg = result.get('msg', 'unknown error')
            logger.error(f"PushPlus \u8fd4\u56deerror: {error_msg}")
            return False

        logger.error(f"PushPlus requestfailed: HTTP {response.status_code}")
        return False

    def _send_pushplus_chunked(self, api_url: str, content: str, title: str, max_bytes: int) -> bool:
        """\u5206\u6279\u53d1\u9001\u957f PushPlus \u6d88\u606f; \u7ed9 JSON payload \u9884\u7559\u7a7a\u95f4."""
        budget = max(1000, max_bytes - 1500)
        chunks = chunk_content_by_max_bytes(content, budget, add_page_marker=True)
        total_chunks = len(chunks)
        success_count = 0

        logger.info(f"PushPlus \u5206\u6279\u53d1\u9001: \u5171 {total_chunks} \u6279")

        for i, chunk in enumerate(chunks):
            chunk_title = f"{title} ({i+1}/{total_chunks})" if total_chunks > 1 else title
            if self._send_pushplus_message(api_url, chunk, chunk_title):
                success_count += 1
                logger.info(f"PushPlus \u7b2c {i+1}/{total_chunks} \u6279send succeeded")
            else:
                logger.error(f"PushPlus \u7b2c {i+1}/{total_chunks} \u6279send failed")

            if i < total_chunks - 1:
                time.sleep(1)

        return success_count == total_chunks
