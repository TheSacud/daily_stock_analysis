# -*- coding: utf-8 -*-
"""
\u81ea\u5b9a\u4e49 Webhook \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u53d1\u9001\u81ea\u5b9a\u4e49 Webhook \u6d88\u606f
"""
import logging
import json
import time
from string import Template
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes, slice_at_max_bytes


logger = logging.getLogger(__name__)


class CustomWebhookSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316\u81ea\u5b9a\u4e49 Webhook config

        Args:
            config: config\u5bf9\u8c61
        """
        self._custom_webhook_urls = getattr(config, 'custom_webhook_urls', []) or []
        self._custom_webhook_bearer_token = getattr(config, 'custom_webhook_bearer_token', None)
        self._custom_webhook_body_template = getattr(config, 'custom_webhook_body_template', None)
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    def send_to_custom(self, content: str) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230\u81ea\u5b9a\u4e49 Webhook

        \u652f\u6301\u4efb\u610f\u63a5\u53d7 POST JSON \u7684 Webhook \u7aef\u70b9
        default\u53d1\u9001\u683c\u5f0f: {"text": "\u6d88\u606f\u5185\u5bb9", "content": "\u6d88\u606f\u5185\u5bb9"}

        \u9002\u7528\u4e8e:
        - DingTalk\u673a\u5668\u4eba
        - Discord Webhook
        - Slack Incoming Webhook
        - \u81ea\u5efanotification service
        - other\u652f\u6301 POST JSON \u7684\u670d\u52a1

        Args:
            content: \u6d88\u606f\u5185\u5bb9 (Markdown \u683c\u5f0f)

        Returns:
            \u662f\u5426\u81f3\u5c11\u6709\u4e00\u4e2a Webhook send succeeded
        """
        if not self._custom_webhook_urls:
            logger.warning("not configured\u81ea\u5b9a\u4e49 Webhook; skipping\u63a8\u9001")
            return False

        success_count = 0

        for i, url in enumerate(self._custom_webhook_urls):
            try:
                # \u901a\u7528 JSON \u683c\u5f0f; \u517c\u5bb9\u5927\u591a\u6570 Webhook
                # DingTalk\u683c\u5f0f: {"msgtype": "text", "text": {"content": "xxx"}}
                # Slack \u683c\u5f0f: {"text": "xxx"}
                # Discord \u683c\u5f0f: {"content": "xxx"}

                # DingTalk\u673a\u5668\u4eba\u5bf9 body \u6709\u5b57\u8282\u4e0a\u9650 (\u7ea6 20000 bytes); \u8d85\u957f\u9700\u8981\u5206\u6279\u53d1\u9001
                if self._is_dingtalk_webhook(url):
                    templated_payload = self._build_custom_webhook_template_payload(content)
                    if templated_payload is not None:
                        if self._post_custom_webhook(url, templated_payload, timeout=30):
                            logger.info(f"\u81ea\u5b9a\u4e49 Webhook {i+1} (DingTalk\u6a21\u677f)\u63a8\u9001success")
                            success_count += 1
                        elif self._send_dingtalk_chunked(url, content, max_bytes=20000):
                            logger.info(f"\u81ea\u5b9a\u4e49 Webhook {i+1} (DingTalk\u6a21\u677ffailed; \u56de\u9000\u5206\u6279)\u63a8\u9001success")
                            success_count += 1
                        else:
                            logger.error(f"\u81ea\u5b9a\u4e49 Webhook {i+1} (DingTalk\u6a21\u677f)\u63a8\u9001failed")
                    elif self._send_dingtalk_chunked(url, content, max_bytes=20000):
                        logger.info(f"\u81ea\u5b9a\u4e49 Webhook {i+1} (DingTalk)\u63a8\u9001success")
                        success_count += 1
                    else:
                        logger.error(f"\u81ea\u5b9a\u4e49 Webhook {i+1} (DingTalk)\u63a8\u9001failed")
                    continue

                # other Webhook: \u5355\u6b21\u53d1\u9001
                payload = self._build_custom_webhook_payload(url, content)
                if self._post_custom_webhook(url, payload, timeout=30):
                    logger.info(f"\u81ea\u5b9a\u4e49 Webhook {i+1} \u63a8\u9001success")
                    success_count += 1
                else:
                    logger.error(f"\u81ea\u5b9a\u4e49 Webhook {i+1} \u63a8\u9001failed")

            except Exception as e:
                logger.error(f"\u81ea\u5b9a\u4e49 Webhook {i+1} \u63a8\u9001\u5f02\u5e38: {e}")

        logger.info(f"\u81ea\u5b9a\u4e49 Webhook \u63a8\u9001\u5b8c\u6210: success {success_count}/{len(self._custom_webhook_urls)}")
        return success_count > 0


    def _send_custom_webhook_image(
        self, image_bytes: bytes, fallback_content: str = ""
    ) -> bool:
        """Send image to Custom Webhooks; Discord supports file attachment (Issue #289)."""
        if not self._custom_webhook_urls:
            return False
        success_count = 0
        for i, url in enumerate(self._custom_webhook_urls):
            try:
                if self._is_discord_webhook(url):
                    files = {"file": ("report.png", image_bytes, "image/png")}
                    data = {"content": "📈 \u80a1\u7968\u667a\u80fdanalyzereport"}
                    headers = {"User-Agent": "StockAnalysis/1.0"}
                    if self._custom_webhook_bearer_token:
                        headers["Authorization"] = (
                            f"Bearer {self._custom_webhook_bearer_token}"
                        )
                    response = requests.post(
                        url, data=data, files=files, headers=headers, timeout=30,
                        verify=self._webhook_verify_ssl
                    )
                    if response.status_code in (200, 204):
                        logger.info("\u81ea\u5b9a\u4e49 Webhook %d (Discord \u56fe\u7247)\u63a8\u9001success", i + 1)
                        success_count += 1
                    else:
                        logger.error(
                            "\u81ea\u5b9a\u4e49 Webhook %d (Discord \u56fe\u7247)\u63a8\u9001failed: HTTP %s",
                            i + 1, response.status_code,
                        )
                else:
                    if fallback_content:
                        payload = self._build_custom_webhook_payload(url, fallback_content)
                        if self._post_custom_webhook(url, payload, timeout=30):
                            logger.info(
                                "\u81ea\u5b9a\u4e49 Webhook %d (\u56fe\u7247does not support; \u56de\u9000\u6587\u672c)\u63a8\u9001success", i + 1
                            )
                            success_count += 1
                    else:
                        logger.warning(
                            "\u81ea\u5b9a\u4e49 Webhook %d does not support\u56fe\u7247; \u4e14\u65e0\u56de\u9000\u5185\u5bb9; skipping", i + 1
                        )
            except Exception as e:
                logger.error("\u81ea\u5b9a\u4e49 Webhook %d \u56fe\u7247\u63a8\u9001\u5f02\u5e38: %s", i + 1, e)
        return success_count > 0

    def _post_custom_webhook(self, url: str, payload: dict, timeout: int = 30) -> bool:
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'User-Agent': 'StockAnalysis/1.0',
        }
        # \u652f\u6301 Bearer Token \u8ba4\u8bc1 (#51)
        if self._custom_webhook_bearer_token:
            headers['Authorization'] = f'Bearer {self._custom_webhook_bearer_token}'
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(url, data=body, headers=headers, timeout=timeout, verify=self._webhook_verify_ssl)
        if response.status_code == 200:
            return True
        logger.error(f"\u81ea\u5b9a\u4e49 Webhook \u63a8\u9001failed: HTTP {response.status_code}")
        logger.debug(f"\u54cd\u5e94\u5185\u5bb9: {response.text[:200]}")
        return False

    def test_custom_webhooks(self, content: str, *, timeout_seconds: float = 20.0) -> List[Dict[str, Any]]:
        """Send a test message to each custom webhook and return raw per-URL attempts."""
        attempts: List[Dict[str, Any]] = []
        for index, url in enumerate(self._custom_webhook_urls):
            try:
                payload = self._build_custom_webhook_payload(url, content)
                attempts.append(
                    self._post_custom_webhook_attempt(
                        url=url,
                        payload=payload,
                        timeout_seconds=timeout_seconds,
                        index=index,
                    )
                )
            except Exception as exc:
                attempts.append({
                    "channel": "custom",
                    "success": False,
                    "message": f"\u81ea\u5b9a\u4e49 Webhook {index + 1} \u6d4b\u8bd5\u5f02\u5e38: {exc}",
                    "target": url,
                    "error_code": self._classify_custom_webhook_exception(exc)[0],
                    "stage": "notification_send",
                    "retryable": self._classify_custom_webhook_exception(exc)[1],
                    "latency_ms": None,
                    "http_status": None,
                })
        return attempts

    def _post_custom_webhook_attempt(
        self,
        *,
        url: str,
        payload: dict,
        timeout_seconds: float,
        index: int,
    ) -> Dict[str, Any]:
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'User-Agent': 'StockAnalysis/1.0',
        }
        if self._custom_webhook_bearer_token:
            headers['Authorization'] = f'Bearer {self._custom_webhook_bearer_token}'

        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        started_at = time.perf_counter()
        try:
            response = requests.post(
                url,
                data=body,
                headers=headers,
                timeout=timeout_seconds,
                verify=self._webhook_verify_ssl,
            )
        except Exception as exc:
            error_code, retryable = self._classify_custom_webhook_exception(exc)
            return {
                "channel": "custom",
                "success": False,
                "message": f"\u81ea\u5b9a\u4e49 Webhook {index + 1} \u6d4b\u8bd5failed: {exc}",
                "target": url,
                "error_code": error_code,
                "stage": "notification_send",
                "retryable": retryable,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "http_status": None,
            }

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if response.status_code == 200:
            return {
                "channel": "custom",
                "success": True,
                "message": f"\u81ea\u5b9a\u4e49 Webhook {index + 1} \u6d4b\u8bd5send succeeded",
                "target": url,
                "error_code": None,
                "stage": "notification_send",
                "retryable": False,
                "latency_ms": latency_ms,
                "http_status": response.status_code,
            }

        retryable = response.status_code == 429 or response.status_code >= 500
        return {
            "channel": "custom",
            "success": False,
            "message": f"\u81ea\u5b9a\u4e49 Webhook {index + 1} \u6d4b\u8bd5failed: HTTP {response.status_code}",
            "target": url,
            "error_code": "http_error",
            "stage": "notification_send",
            "retryable": retryable,
            "latency_ms": latency_ms,
            "http_status": response.status_code,
        }

    @staticmethod
    def _classify_custom_webhook_exception(exc: Exception) -> Tuple[str, bool]:
        if isinstance(exc, requests.exceptions.Timeout):
            return "timeout", True
        if isinstance(exc, requests.exceptions.ConnectionError):
            return "network_error", True
        if isinstance(exc, requests.exceptions.RequestException):
            return "network_error", True
        return "unexpected_error", False

    def _build_custom_webhook_payload(self, url: str, content: str) -> dict:
        """
        \u6839\u636e URL \u6784\u5efa\u5bf9\u5e94\u7684 Webhook payload

        \u81ea\u52a8\u8bc6\u522b\u5e38\u89c1\u670d\u52a1\u5e76\u4f7f\u7528\u5bf9\u5e94\u683c\u5f0f
        """
        templated_payload = self._build_custom_webhook_template_payload(content)
        if templated_payload is not None:
            return templated_payload

        url_lower = url.lower()

        # DingTalk\u673a\u5668\u4eba
        if 'dingtalk' in url_lower or 'oapi.dingtalk.com' in url_lower:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "title": "\u80a1\u7968analyzereport",
                    "text": content
                }
            }

        # Discord Webhook
        if 'discord.com/api/webhooks' in url_lower or 'discordapp.com/api/webhooks' in url_lower:
            # Discord limit 2000 \u5b57\u7b26
            truncated = content[:1900] + "..." if len(content) > 1900 else content
            return {
                "content": truncated
            }

        # Slack Incoming Webhook
        if 'hooks.slack.com' in url_lower:
            return {
                "text": content,
                "mrkdwn": True
            }

        # Bark (iOS \u63a8\u9001)
        if 'api.day.app' in url_lower:
            return {
                "title": "\u80a1\u7968analyzereport",
                "body": content[:4000],  # Bark limit
                "group": "stock"
            }

        # \u901a\u7528\u683c\u5f0f (\u517c\u5bb9\u5927\u591a\u6570\u670d\u52a1)
        return {
            "text": content,
            "content": content,
            "message": content,
            "body": content
        }

    def _build_custom_webhook_template_payload(self, content: str) -> Optional[dict]:
        """Build payload from CUSTOM_WEBHOOK_BODY_TEMPLATE when configured."""
        template = (self._custom_webhook_body_template or "").strip()
        if not template:
            return None

        title = "\u80a1\u7968analyzereport"
        variables = {
            "title": title,
            "title_json": json.dumps(title, ensure_ascii=False),
            "content": content,
            "content_json": json.dumps(content, ensure_ascii=False),
        }
        rendered = Template(template).safe_substitute(variables)
        try:
            payload: Any = json.loads(rendered)
        except json.JSONDecodeError as exc:
            logger.error(
                "CUSTOM_WEBHOOK_BODY_TEMPLATE \u4e0d\u662f\u6709\u6548 JSON; \u5df2\u56de\u9000\u4e3adefault Webhook payload: %s",
                exc,
            )
            return None
        if not isinstance(payload, dict):
            logger.error(
                "CUSTOM_WEBHOOK_BODY_TEMPLATE \u5fc5\u987b\u6e32\u67d3\u4e3a JSON object; \u5df2\u56de\u9000\u4e3adefault Webhook payload"
            )
            return None
        return payload

    def _send_dingtalk_chunked(self, url: str, content: str, max_bytes: int = 20000) -> bool:
        import time as _time

        # \u4e3a payload \u5f00\u9500\u9884\u7559\u7a7a\u95f4; \u907f\u514d body \u8d85\u9650
        budget = max(1000, max_bytes - 1500)
        chunks = chunk_content_by_max_bytes(content, budget)
        if not chunks:
            return False

        total = len(chunks)
        ok = 0

        for idx, chunk in enumerate(chunks):
            marker = f"\n\n📄 *({idx+1}/{total})*" if total > 1 else ""
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "\u80a1\u7968analyzereport",
                    "text": chunk + marker,
                },
            }

            # \u5982\u679c\u4ecd\u8d85\u9650 (\u6781\u7aef\u60c5\u51b5\u4e0b); \u518d\u6309\u5b57\u8282\u786c\u622a\u65ad\u4e00\u6b21
            body_bytes = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
            if body_bytes > max_bytes:
                hard_budget = max(200, budget - (body_bytes - max_bytes) - 200)
                payload["markdown"]["text"], _ = slice_at_max_bytes(payload["markdown"]["text"], hard_budget)

            if self._post_custom_webhook(url, payload, timeout=30):
                ok += 1
            else:
                logger.error(f"DingTalk\u5206\u6279send failed: \u7b2c {idx+1}/{total} \u6279")

            if idx < total - 1:
                _time.sleep(1)

        return ok == total


    @staticmethod
    def _is_dingtalk_webhook(url: str) -> bool:
        url_lower = (url or "").lower()
        return 'dingtalk' in url_lower or 'oapi.dingtalk.com' in url_lower

    @staticmethod
    def _is_discord_webhook(url: str) -> bool:
        url_lower = (url or "").lower()
        return (
            'discord.com/api/webhooks' in url_lower
            or 'discordapp.com/api/webhooks' in url_lower
        )
