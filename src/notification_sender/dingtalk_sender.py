# -*- coding: utf-8 -*-
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import logging
from typing import Optional

from src.config import Config
from src.formatters import chunk_content_by_max_bytes  # <-- \u5f15\u5165\u9879\u76ee\u5185\u7f6e\u7684\u5207\u7247\u5668

logger = logging.getLogger(__name__)

class DingtalkSender:
    def __init__(self, config: Config):
        self.webhook_url = config.dingtalk_webhook_url
        self.secret = config.dingtalk_secret

    def send_to_dingtalk(self, content: str, title: str = "", timeout_seconds: int = 10) -> bool:
        """\u53d1\u9001 Markdown \u6d88\u606f\u5230DingTalk\u7fa4 (Send DingTalk Markdown message)"""
        if not self.webhook_url:
            return False

        # 1. \u7b7e\u540d\u903b\u8f91 (Security Signature)
        if self.secret:
            timestamp = str(round(time.time() * 1000))
            secret_enc = self.secret.encode('utf-8')
            string_to_sign = f'{timestamp}\n{self.secret}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

            if "?" in self.webhook_url:
                url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            else:
                url = f"{self.webhook_url}?timestamp={timestamp}&sign={sign}"
        else:
            url = self.webhook_url

        # 2. limit\u6807\u9898\u957f\u5ea6; \u9632\u6b62\u6781\u7aef\u957f\u6807\u9898\u5403\u6389\u8fc7\u591a JSON \u5b57\u8282\u9884\u7b97
        safe_title = (title[:100] + "...") if title and len(title) > 100 else title

        # 3. \u5207\u7247\u903b\u8f91 (Chunking for DingTalk's 20,000 byte limit)
        # \u9884\u7559 1000 bytes \u7684\u5b89\u5168\u9884\u7b97; \u7528\u4e8e JSON \u7ed3\u6784、\u6807\u9898\u548c\u5206\u9875\u540e\u7f00\u7684\u989d\u5916\u5f00\u9500
        safe_max_bytes = 19000
        chunks = chunk_content_by_max_bytes(content, max_bytes=safe_max_bytes)
        all_success = True

        for index, chunk in enumerate(chunks):
            text = f"### {safe_title}\n\n{chunk}" if index == 0 and safe_title else chunk

            display_title = safe_title or "\u901a\u77e5 (Notification)"
            if len(chunks) > 1:
                display_title = f"{display_title} ({index + 1}/{len(chunks)})"

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": display_title,
                    "text": text
                }
            }
            headers = {'Content-Type': 'application/json'}

            # 4. \u53d1\u9001request
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
                response.raise_for_status()

                result = response.json()
                if result.get("errcode") == 0:
                    logger.info(f"DingTalk\u6d88\u606f\u5206\u6bb5 {index + 1} send succeeded (Chunk {index + 1} sent successfully)")
                else:
                    logger.error(f"DingTalk\u6d88\u606f\u5206\u6bb5 {index + 1} send failed (DingTalk API error): {result}")
                    all_success = False
            except Exception as e:
                logger.error(f"\u53d1\u9001DingTalk\u6d88\u606f\u5f02\u5e38 (Failed to send DingTalk notification chunk {index + 1}): {e}")
                all_success = False

            if len(chunks) > 1 and index < len(chunks) - 1:
                time.sleep(0.5)

        return all_success