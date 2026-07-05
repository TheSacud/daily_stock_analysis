# -*- coding: utf-8 -*-
"""
AstrBot \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 Astrbot API \u53d1\u9001 AstrBot \u6d88\u606f
"""
import logging
import json
import hmac
import hashlib
from typing import Optional

import requests

from src.config import Config
from src.formatters import markdown_to_html_document


logger = logging.getLogger(__name__)


class AstrbotSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 AstrBot config

        Args:
            config: config\u5bf9\u8c61
        """
        self._astrbot_config = {
            'astrbot_url': getattr(config, 'astrbot_url', None),
            'astrbot_token': getattr(config, 'astrbot_token', None),
        }
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    def _is_astrbot_configured(self) -> bool:
        """\u68c0check AstrBot config\u662f\u5426\u5b8c\u6574 (\u652f\u6301 Bot or Webhook)"""
        # \u53ea\u8981config\u4e86 URL; \u5373\u89c6\u4e3a\u53ef\u7528
        url_ok = bool(self._astrbot_config['astrbot_url'])
        return url_ok

    def send_to_astrbot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 AstrBot (\u901a\u8fc7\u9002\u914d\u5668\u652f\u6301)

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        if self._astrbot_config['astrbot_url']:
            return self._send_astrbot(content, timeout_seconds=timeout_seconds)

        logger.warning("AstrBot config\u4e0d\u5b8c\u6574; skipping\u63a8\u9001")
        return False


    def _send_astrbot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        import time
        """
        \u4f7f\u7528 Bot API \u53d1\u9001\u6d88\u606f\u5230 AstrBot

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """

        html_content = markdown_to_html_document(content)

        try:
            payload = {
                'content': html_content
            }
            signature =  ""
            timestamp = str(int(time.time()))
            if self._astrbot_config['astrbot_token']:
                """\u8ba1\u7b97request\u7b7e\u540d"""
                payload_json = json.dumps(payload, sort_keys=True)
                sign_data = f"{timestamp}.{payload_json}".encode('utf-8')
                key = self._astrbot_config['astrbot_token']
                signature = hmac.new(
                    key.encode('utf-8'),
                    sign_data,
                    hashlib.sha256
                ).hexdigest()
            url = self._astrbot_config['astrbot_url']
            response = requests.post(
                url, json=payload, timeout=timeout_seconds or 10,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": signature,
                    "X-Timestamp": timestamp
                },
                verify=self._webhook_verify_ssl
            )

            if response.status_code == 200:
                logger.info("AstrBot message sent successfully")
                return True
            else:
                logger.error(f"AstrBot send failed: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"AstrBot \u53d1\u9001\u5f02\u5e38: {e}")
            return False
