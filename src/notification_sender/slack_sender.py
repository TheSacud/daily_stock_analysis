# -*- coding: utf-8 -*-
"""
Slack \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 Slack Bot API or Incoming Webhook \u53d1\u9001 Slack \u6d88\u606f
    (\u540c\u65f6config\u65f6\u4f18\u5148\u4f7f\u7528 Bot API; \u786e\u4fdd\u6587\u672c\u4e0e\u56fe\u7247\u53d1\u9001\u5230\u540c\u4e00\u9891\u9053)
"""
import logging
import json
from typing import Optional

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes

logger = logging.getLogger(__name__)

# Slack Block Kit Medium\u5355\u4e2a section block \u7684 text \u5b57\u6bb5\u4e0a\u9650\u4e3a 3000 \u5b57\u7b26
_BLOCK_TEXT_LIMIT = 3000
# Slack chat.postMessage / Webhook \u7684 text \u5b57\u6bb5\u4e0a\u9650\u7ea6 40000 \u5b57\u7b26; \u4fdd\u5b88\u53d6 39000
_TEXT_LIMIT = 39000


class SlackSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 Slack config

        Args:
            config: config\u5bf9\u8c61
        """
        self._slack_webhook_url = getattr(config, 'slack_webhook_url', None)
        self._slack_bot_token = getattr(config, 'slack_bot_token', None)
        self._slack_channel_id = getattr(config, 'slack_channel_id', None)
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    @property
    def _use_bot(self) -> bool:
        """Bot config\u5b8c\u6574\u65f6\u4f18\u5148\u8d70 Bot API; \u4fdd\u8bc1\u6587\u672c\u548c\u56fe\u7247\u4f7f\u7528\u540c\u4e00\u4f20\u8f93\u901a\u9053."""
        return bool(self._slack_bot_token and self._slack_channel_id)

    def _is_slack_configured(self) -> bool:
        """\u68c0check Slack config\u662f\u5426\u5b8c\u6574 (\u652f\u6301 Webhook or Bot API)"""
        return self._use_bot or bool(self._slack_webhook_url)

    def send_to_slack(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230 Slack (\u652f\u6301 Webhook \u548c Bot API)

        \u4f20\u8f93\u4f18\u5148\u7ea7\u4e0e _send_slack_image() \u4fdd\u6301\u4e00\u81f4: Bot > Webhook;
        \u907f\u514d\u6587\u672c\u8d70 Webhook、\u56fe\u7247\u8d70 Bot \u5bfc\u81f4\u6d88\u606f\u843d\u5165\u4e0d\u540c\u9891\u9053.

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        # \u6309\u5b57\u8282\u5206chunks; \u907f\u514d\u5355\u6761\u6d88\u606f\u8d85\u9650
        try:
            chunks = chunk_content_by_max_bytes(content, _TEXT_LIMIT, add_page_marker=True)
        except Exception as e:
            logger.error(f"\u5206\u5272 Slack \u6d88\u606ffailed: {e}, trying whole-message send.")
            chunks = [content]

        # \u4f18\u5148\u4f7f\u7528 Bot API (\u4e0e _send_slack_image \u4fdd\u6301\u4e00\u81f4)
        if self._use_bot:
            return all(self._send_slack_bot(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)

        # \u5176\u6b21\u4f7f\u7528 Webhook
        if self._slack_webhook_url:
            return all(self._send_slack_webhook(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)

        logger.warning("Slack config\u4e0d\u5b8c\u6574; skipping\u63a8\u9001")
        return False

    def _build_blocks(self, content: str) -> list:
        """
        \u5c06\u5185\u5bb9\u6784\u5efa\u4e3a Slack Block Kit \u683c\u5f0f

        \u5982\u679c\u5185\u5bb9\u8d85\u8fc7\u5355\u4e2a section block limit; \u4f1a\u81ea\u52a8\u62c6\u5206\u4e3a\u591a\u4e2a block.
        """
        blocks = []
        # \u6309 block text \u4e0a\u9650\u62c6\u5206
        pos = 0
        while pos < len(content):
            segment = content[pos:pos + _BLOCK_TEXT_LIMIT]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": segment
                }
            })
            pos += _BLOCK_TEXT_LIMIT
        return blocks

    def _send_slack_webhook(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u4f7f\u7528 Incoming Webhook \u53d1\u9001\u6d88\u606f\u5230 Slack

        Args:
            content: \u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        try:
            payload = {
                "text": content,
                "blocks": self._build_blocks(content),
            }
            response = requests.post(
                self._slack_webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=timeout_seconds or 15,
                verify=self._webhook_verify_ssl,
            )
            if response.status_code == 200 and response.text == "ok":
                logger.info("Slack Webhook message sent successfully")
                return True
            logger.error(f"Slack Webhook send failed: HTTP {response.status_code} {response.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"Slack Webhook \u53d1\u9001\u5f02\u5e38: {e}")
            return False

    def _send_slack_bot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u4f7f\u7528 Bot API (chat.postMessage) \u53d1\u9001\u6d88\u606f\u5230 Slack

        Args:
            content: \u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        try:
            headers = {
                'Authorization': f'Bearer {self._slack_bot_token}',
                'Content-Type': 'application/json; charset=utf-8',
            }
            payload = {
                "channel": self._slack_channel_id,
                "text": content,
                "blocks": self._build_blocks(content),
            }
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                timeout=timeout_seconds or 15,
            )
            result = response.json()
            if result.get("ok"):
                logger.info("Slack Bot message sent successfully")
                return True
            logger.error(f"Slack Bot send failed: {result.get('error', 'unknown')}")
            return False
        except Exception as e:
            logger.error(f"Slack Bot \u53d1\u9001\u5f02\u5e38: {e}")
            return False

    def _send_slack_image(self, image_bytes: bytes, fallback_content: str = "") -> bool:
        """
        \u53d1\u9001\u56fe\u7247\u5230 Slack

        Bot mode\u4e0b\u4f7f\u7528 files.getUploadURLExternal + files.completeUploadExternal
        (Slack \u65b0\u7248\u6587\u4ef6\u4e0a\u4f20 API)；Webhook mode\u4e0b\u56de\u9000\u4e3a\u6587\u672c.

        Args:
            image_bytes: PNG \u56fe\u7247\u5b57\u8282
            fallback_content: \u56fe\u7247send failed\u65f6\u7684\u56de\u9000\u6587\u672c

        Returns:
            \u662f\u5426send succeeded
        """
        # Bot mode: \u4f7f\u7528\u65b0\u7248\u6587\u4ef6\u4e0a\u4f20 API
        if self._use_bot:
            headers = {'Authorization': f'Bearer {self._slack_bot_token}'}
            try:
                # Step 1: \u83b7\u53d6\u4e0a\u4f20 URL
                resp1 = requests.post(
                    'https://slack.com/api/files.getUploadURLExternal',
                    headers=headers,
                    data={
                        'filename': 'report.png',
                        'length': len(image_bytes),
                    },
                    timeout=30,
                )
                result1 = resp1.json()
                if not result1.get("ok"):
                    logger.error("Slack \u83b7\u53d6\u4e0a\u4f20 URL failed: %s", result1.get('error', 'unknown'))
                    raise RuntimeError(result1.get('error', 'unknown'))

                upload_url = result1['upload_url']
                file_id = result1['file_id']

                # Step 2: \u4e0a\u4f20\u6587\u4ef6\u5185\u5bb9 (raw body; \u4e0d\u80fd\u7528 multipart)
                resp2 = requests.post(
                    upload_url,
                    data=image_bytes,
                    headers={'Content-Type': 'application/octet-stream'},
                    timeout=30,
                )
                if resp2.status_code != 200:
                    logger.error("Slack \u6587\u4ef6\u4e0a\u4f20failed: HTTP %s", resp2.status_code)
                    raise RuntimeError(f"HTTP {resp2.status_code}")

                # Step 3: \u5b8c\u6210\u4e0a\u4f20\u5e76\u5206\u4eab\u5230\u9891\u9053
                resp3 = requests.post(
                    'https://slack.com/api/files.completeUploadExternal',
                    headers={**headers, 'Content-Type': 'application/json'},
                    json={
                        'files': [{'id': file_id, 'title': '\u80a1\u7968analyzereport'}],
                        'channel_id': self._slack_channel_id,
                    },
                    timeout=30,
                )
                result3 = resp3.json()
                if result3.get("ok"):
                    logger.info("Slack Bot \u56fe\u7247send succeeded")
                    return True
                logger.error("Slack \u5b8c\u6210\u4e0a\u4f20failed: %s", result3.get('error', 'unknown'))
            except Exception as e:
                logger.error("Slack Bot \u56fe\u7247\u53d1\u9001\u5f02\u5e38: %s", e)

        # Webhook modeor Bot \u4e0a\u4f20failed: \u56de\u9000\u4e3a\u6587\u672c
        if fallback_content:
            logger.info("Slack \u56fe\u7247does not supportorfailed; \u56de\u9000\u4e3a\u6587\u672c\u53d1\u9001")
            return self.send_to_slack(fallback_content)

        logger.warning("Slack \u56fe\u7247send failed; \u4e14\u65e0\u56de\u9000\u5185\u5bb9")
        return False
