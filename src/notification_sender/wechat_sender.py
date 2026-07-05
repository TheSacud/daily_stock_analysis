# -*- coding: utf-8 -*-
"""
Wechat \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7WeCom Webhook \u53d1\u9001\u6587\u672c\u6d88\u606f
2. \u901a\u8fc7WeCom Webhook \u53d1\u9001\u56fe\u7247\u6d88\u606f
"""
import logging
import base64
import hashlib
import requests
import time
from typing import Optional

from src.config import Config
from src.formatters import chunk_content_by_max_bytes


logger = logging.getLogger(__name__)


# WeChat Work image msgtype limit ~2MB (base64 payload)
WECHAT_IMAGE_MAX_BYTES = 2 * 1024 * 1024

class WechatSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316WeComconfig

        Args:
            config: config\u5bf9\u8c61
        """
        self._wechat_url = config.wechat_webhook_url
        self._wechat_max_bytes = getattr(config, 'wechat_max_bytes', 4000)
        self._wechat_msg_type = getattr(config, 'wechat_msg_type', 'markdown')
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    def send_to_wechat(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        \u63a8\u9001\u6d88\u606f\u5230WeCom\u673a\u5668\u4eba

        WeCom Webhook \u6d88\u606f\u683c\u5f0f:
        \u652f\u6301 markdown \u7c7b\u578b\u4ee5\u53ca text \u7c7b\u578b, markdown \u7c7b\u578b\u5728\u5fae\u4fe1Medium\u65e0\u6cd5\u5c55\u793a; \u53ef\u4ee5\u4f7f\u7528 text \u7c7b\u578b,
        markdown \u7c7b\u578b\u4f1a\u89e3\u6790 markdown \u683c\u5f0f,text \u7c7b\u578b\u4f1a\u76f4\u63a5\u53d1\u9001\u7eaf\u6587\u672c.

        markdown \u7c7b\u578b\u793a\u4f8b:
        {
            "msgtype": "markdown",
            "markdown": {
                "content": "## \u6807\u9898\n\n\u5185\u5bb9"
            }
        }

        text \u7c7b\u578b\u793a\u4f8b:
        {
            "msgtype": "text",
            "text": {
                "content": "\u5185\u5bb9"
            }
        }

        \u6ce8\u610f: WeCom Markdown limit 4096 \u5b57\u8282 (\u975e\u5b57\u7b26), Text \u7c7b\u578blimit 2048 \u5b57\u8282; \u8d85\u957f\u5185\u5bb9\u4f1a\u81ea\u52a8\u5206\u6279\u53d1\u9001
        \u53ef\u901a\u8fc7\u73af\u5883\u53d8\u91cf WECHAT_MAX_BYTES \u8c03\u6574limit\u503c

        Args:
            content: Markdown \u683c\u5f0f\u7684\u6d88\u606f\u5185\u5bb9

        Returns:
            \u662f\u5426send succeeded
        """
        if not self._wechat_url:
            logger.warning("WeCom Webhook not configured; skipping\u63a8\u9001")
            return False

        # \u6839\u636e\u6d88\u606f\u7c7b\u578b\u52a8\u6001limit\u4e0a\u9650; \u907f\u514d text \u7c7b\u578b\u8d85\u8fc7WeCom 2048 \u5b57\u8282limit
        if self._wechat_msg_type == 'text':
            max_bytes = min(self._wechat_max_bytes, 2000)  # \u9884\u7559\u4e00\u5b9a\u5b57\u8282\u7ed9\u7cfb\u7edf/\u5206\u9875\u6807\u8bb0
        else:
            max_bytes = self._wechat_max_bytes  # markdown default 4000 \u5b57\u8282

        # \u68c0check\u5b57\u8282\u957f\u5ea6; \u8d85\u957f\u5219\u5206\u6279\u53d1\u9001
        content_bytes = len(content.encode('utf-8'))
        if content_bytes > max_bytes:
            logger.info(f"\u6d88\u606f\u5185\u5bb9\u8d85\u957f({content_bytes}\u5b57\u8282/{len(content)}\u5b57\u7b26); \u5c06\u5206\u6279\u53d1\u9001")
            return self._send_wechat_chunked(content, max_bytes)

        try:
            return self._send_wechat_message(content, timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.error(f"\u53d1\u9001WeCom\u6d88\u606ffailed: {e}")
            return False

    def _send_wechat_image(self, image_bytes: bytes) -> bool:
        """Send image via WeChat Work webhook msgtype image (Issue #289)."""
        if not self._wechat_url:
            return False
        if len(image_bytes) > WECHAT_IMAGE_MAX_BYTES:
            logger.warning(
                "WeCom\u56fe\u7247\u8d85\u9650 (%d > %d bytes); \u62d2\u7edd\u53d1\u9001; \u8c03\u7528\u65b9\u5e94 fallback \u4e3a\u6587\u672c",
                len(image_bytes), WECHAT_IMAGE_MAX_BYTES,
            )
            return False
        try:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            md5_hash = hashlib.md5(image_bytes).hexdigest()
            payload = {
                "msgtype": "image",
                "image": {"base64": b64, "md5": md5_hash},
            }
            response = requests.post(
                self._wechat_url, json=payload, timeout=30, verify=self._webhook_verify_ssl
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    logger.info("WeCom\u56fe\u7247send succeeded")
                    return True
                logger.error("WeCom\u56fe\u7247send failed: %s", result.get("errmsg", ""))
            else:
                logger.error("WeComrequestfailed: HTTP %s", response.status_code)
            return False
        except Exception as e:
            logger.error("WeCom\u56fe\u7247\u53d1\u9001\u5f02\u5e38: %s", e)
            return False

    def _send_wechat_message(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """\u53d1\u9001WeCom\u6d88\u606f"""
        payload = self._gen_wechat_payload(content)

        response = requests.post(
            self._wechat_url,
            json=payload,
            timeout=timeout_seconds or 10,
            verify=self._webhook_verify_ssl
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("WeCommessage sent successfully")
                return True
            else:
                logger.error(f"WeCom\u8fd4\u56deerror: {result}")
                return False
        else:
            logger.error(f"WeComrequestfailed: {response.status_code}")
            return False

    def _send_wechat_chunked(self, content: str, max_bytes: int) -> bool:
        """
        \u5206\u6279\u53d1\u9001\u957f\u6d88\u606f\u5230WeCom

        \u6309\u80a1\u7968analyzechunks (\u4ee5 --- or ### \u5206\u9694)\u667a\u80fd\u5206\u5272; \u786e\u4fdd\u6bcf\u6279\u4e0d\u8d85\u8fc7limit

        Args:
            content: \u5b8c\u6574\u6d88\u606f\u5185\u5bb9
            max_bytes: \u5355\u6761\u6d88\u606f\u6700\u5927\u5b57\u8282\u6570

        Returns:
            \u662f\u5426allsend succeeded
        """
        chunks = chunk_content_by_max_bytes(content, max_bytes, add_page_marker=True)
        total_chunks = len(chunks)
        success_count = 0
        for i, chunk in enumerate(chunks):
            if self._send_wechat_message(chunk):
                success_count += 1
            else:
                logger.error(f"WeCom\u7b2c {i+1}/{total_chunks} \u6279send failed")
            if i < total_chunks - 1:
                time.sleep(1)
        return success_count == len(chunks)

    def _gen_wechat_payload(self, content: str) -> dict:
        """\u751f\u6210WeCom\u6d88\u606f payload"""
        if self._wechat_msg_type == 'text':
            return {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
        else:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
