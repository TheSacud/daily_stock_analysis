# -*- coding: utf-8 -*-
"""
Server\u91713 \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 Server\u91713 API \u53d1\u9001 Server\u91713 \u6d88\u606f
"""
import logging
from typing import Optional
import requests
from datetime import datetime
import re

from src.config import Config


logger = logging.getLogger(__name__)


class Serverchan3Sender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 Server\u91713 config

        Args:
            config: config\u5bf9\u8c61
        """
        self._serverchan3_sendkey = getattr(config, 'serverchan3_sendkey', None)

    def send_to_serverchan3(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 Server\u91713

        Server\u91713 API \u683c\u5f0f:
        POST https://sctapi.ftqq.com/{sendkey}.send
        or
        POST https://{num}.push.ft07.com/send/{sendkey}.send
        {
            "title": "\u6d88\u606f\u6807\u9898",
            "desp": "\u6d88\u606f\u5185\u5bb9",
            "options": {}
        }

        Server\u91713 \u7279\u70b9:
        - \u56fd\u5185\u63a8\u9001\u670d\u52a1; \u652f\u6301\u591a\u5bb6\u56fd\u4ea7\u7cfb\u7edf\u63a8\u9001\u901a\u9053; \u53ef\u65e0\u540e\u53f0\u63a8\u9001
        - \u7b80\u5355\u6613\u7528\u7684 API \u63a5\u53e3

        Args:
            content: \u6d88\u606f\u5185\u5bb9 (Markdown \u683c\u5f0f)
            title: \u6d88\u606f\u6807\u9898 (optional)

        Returns:
            \u662f\u5426send succeeded
        """
        if not self._serverchan3_sendkey:
            logger.warning("Server\u91713 SendKey not configured; skipping\u63a8\u9001")
            return False

        # \u5904\u7406\u6d88\u606f\u6807\u9898
        if title is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            title = f"📈 \u80a1\u7968analyzereport - {date_str}"

        try:
            # \u6839\u636e sendkey \u683c\u5f0f\u6784\u9020 URL
            sendkey = self._serverchan3_sendkey
            if sendkey.startswith('sctp'):
                match = re.match(r'sctp(\d+)t', sendkey)
                if match:
                    num = match.group(1)
                    url = f"https://{num}.push.ft07.com/send/{sendkey}.send"
                else:
                    logger.error("Invalid sendkey format for sctp")
                    return False
            else:
                url = f"https://sctapi.ftqq.com/{sendkey}.send"

            # \u6784\u5efarequestparameter
            params = {
                'title': title,
                'desp': content,
                'options': {}
            }

            # \u53d1\u9001request
            headers = {
                'Content-Type': 'application/json;charset=utf-8'
            }
            response = requests.post(url, json=params, headers=headers, timeout=timeout_seconds or 10)

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Server\u91713 message sent successfully: {result}")
                return True
            else:
                logger.error(f"Server\u91713 requestfailed: HTTP {response.status_code}")
                logger.error(f"\u54cd\u5e94\u5185\u5bb9: {response.text}")
                return False

        except Exception as e:
            logger.error(f"\u53d1\u9001 Server\u91713 \u6d88\u606ffailed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
