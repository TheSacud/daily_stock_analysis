# -*- coding: utf-8 -*-
"""
===================================
DingTalk\u5e73\u53f0\u9002\u914d\u5668
===================================

\u5904\u7406DingTalk\u673a\u5668\u4eba\u7684 Webhook \u56de\u8c03.

DingTalk\u673a\u5668\u4ebadocs:
https://open.dingtalk.com/document/robots/robot-overview
"""

import hashlib
import hmac
import base64
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import quote_plus

from bot.platforms.base import BotPlatform
from bot.models import BotMessage, BotResponse, WebhookResponse, ChatType

logger = logging.getLogger(__name__)


class DingtalkPlatform(BotPlatform):
    """
    DingTalk\u5e73\u53f0\u9002\u914d\u5668

    \u652f\u6301:
    - \u4f01\u4e1a\u5185\u90e8\u673a\u5668\u4eba\u56de\u8c03
    - \u7fa4\u673a\u5668\u4eba Outgoing \u56de\u8c03
    - \u6d88\u606f\u7b7e\u540d\u9a8c\u8bc1

    config\u8981\u6c42:
    - DINGTALK_APP_KEY: \u5e94\u7528 AppKey
    - DINGTALK_APP_SECRET: \u5e94\u7528 AppSecret (\u7528\u4e8e\u7b7e\u540d\u9a8c\u8bc1)
    """

    def __init__(self):
        from src.config import get_config
        config = get_config()

        self._app_key = getattr(config, 'dingtalk_app_key', None)
        self._app_secret = getattr(config, 'dingtalk_app_secret', None)

    @property
    def platform_name(self) -> str:
        return "dingtalk"

    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        \u9a8c\u8bc1DingTalkrequest\u7b7e\u540d

        DingTalk\u7b7e\u540d\u7b97\u6cd5:
        1. \u83b7\u53d6 timestamp \u548c sign
        2. \u8ba1\u7b97: base64(hmac_sha256(timestamp + "\n" + app_secret))
        3. \u6bd4\u5bf9\u7b7e\u540d
        """
        if not self._app_secret:
            logger.warning("[DingTalk] app_secret not configured; skipping signature verification")
            return True

        timestamp = headers.get('timestamp', '')
        sign = headers.get('sign', '')

        if not timestamp or not sign:
            logger.warning("[DingTalk] \u7f3a\u5c11\u7b7e\u540dparameter")
            return True  # \u53ef\u80fd\u662f\u4e0d\u9700\u8981\u7b7e\u540d\u7684request

        # \u9a8c\u8bc1\u65f6\u95f4\u6233 (1\u5c0f\u65f6\u5185\u6709\u6548)
        try:
            request_time = int(timestamp)
            current_time = int(time.time() * 1000)
            if abs(current_time - request_time) > 3600 * 1000:
                logger.warning("[DingTalk] timestamp expired")
                return False
        except ValueError:
            logger.warning("[DingTalk] invalid timestamp")
            return False

        # \u8ba1\u7b97\u7b7e\u540d
        string_to_sign = f"{timestamp}\n{self._app_secret}"
        hmac_code = hmac.new(
            self._app_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode('utf-8')

        if sign != expected_sign:
            logger.warning(f"[DingTalk] signature verification failed")
            return False

        return True

    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:
        """DingTalk\u4e0d\u9700\u8981 URL \u9a8c\u8bc1"""
        return None

    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:
        """
        \u89e3\u6790DingTalk\u6d88\u606f

        DingTalk Outgoing \u673a\u5668\u4eba\u6d88\u606f\u683c\u5f0f:
        {
            "msgtype": "text",
            "text": {
                "content": "@\u673a\u5668\u4eba /analyze 600519"
            },
            "msgId": "xxx",
            "createAt": "1234567890",
            "conversationType": "2",  # 1=\u5355\u804a, 2=\u7fa4\u804a
            "conversationId": "xxx",
            "conversationTitle": "\u7fa4\u540d",
            "senderId": "xxx",
            "senderNick": "user\u6635\u79f0",
            "senderCorpId": "xxx",
            "senderStaffId": "xxx",
            "chatbotUserId": "xxx",
            "atUsers": [{"dingtalkId": "xxx", "staffId": "xxx"}],
            "isAdmin": false,
            "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=xxx",
            "sessionWebhookExpiredTime": 1234567890
        }
        """
        # \u68c0check\u6d88\u606f\u7c7b\u578b
        msg_type = data.get('msgtype', '')
        if msg_type != 'text':
            logger.debug(f"[DingTalk] ignored non-text message: {msg_type}")
            return None

        # \u83b7\u53d6\u6d88\u606f\u5185\u5bb9
        text_content = data.get('text', {})
        raw_content = text_content.get('content', '')

        # \u63d0\u53d6command (\u53bb\u9664 @\u673a\u5668\u4eba)
        content = self._extract_command(raw_content)

        # \u68c0check\u662f\u5426 @\u4e86\u673a\u5668\u4eba
        at_users = data.get('atUsers', [])
        mentioned = len(at_users) > 0

        # conversation\u7c7b\u578b
        conversation_type = data.get('conversationType', '')
        if conversation_type == '1':
            chat_type = ChatType.PRIVATE
        elif conversation_type == '2':
            chat_type = ChatType.GROUP
        else:
            chat_type = ChatType.UNKNOWN

        # \u521b\u5efa\u65f6\u95f4
        create_at = data.get('createAt', '')
        try:
            timestamp = datetime.fromtimestamp(int(create_at) / 1000)
        except (ValueError, TypeError):
            timestamp = datetime.now()

        # \u4fdd\u5b58 session webhook \u7528\u4e8e\u56de\u590d
        session_webhook = data.get('sessionWebhook', '')

        return BotMessage(
            platform=self.platform_name,
            message_id=data.get('msgId', ''),
            user_id=data.get('senderId', ''),
            user_name=data.get('senderNick', ''),
            chat_id=data.get('conversationId', ''),
            chat_type=chat_type,
            content=content,
            raw_content=raw_content,
            mentioned=mentioned,
            mentions=[u.get('dingtalkId', '') for u in at_users],
            timestamp=timestamp,
            raw_data={
                **data,
                '_session_webhook': session_webhook,
            },
        )

    def _extract_command(self, text: str) -> str:
        """
        \u63d0\u53d6command\u5185\u5bb9 (\u53bb\u9664 @\u673a\u5668\u4eba)

        DingTalk\u7684 @user \u683c\u5f0f\u901a\u5e38\u662f @\u6635\u79f0 \u540e\u8ddf\u7a7a\u683c
        """
        # \u7b80\u5355\u5904\u7406: \u79fb\u9664\u5f00\u5934\u7684 @xxx \u90e8\u5206
        import re
        # \u5339\u914d\u5f00\u5934\u7684 @xxx (Medium\u82f1\u6587\u90fd\u53ef\u80fd)
        text = re.sub(r'^@[\S]+\s*', '', text.strip())
        return text.strip()

    def format_response(
        self,
        response: BotResponse,
        message: BotMessage
    ) -> WebhookResponse:
        """
        \u683c\u5f0f\u5316DingTalk\u54cd\u5e94

        DingTalk Outgoing \u673a\u5668\u4eba\u53ef\u4ee5\u76f4\u63a5\u5728\u54cd\u5e94Medium\u8fd4\u56de\u6d88\u606f.
        \u4e5f\u53ef\u4ee5\u4f7f\u7528 sessionWebhook \u5f02\u6b65\u53d1\u9001.

        \u54cd\u5e94\u683c\u5f0f:
        {
            "msgtype": "text" | "markdown",
            "text": {"content": "xxx"},
            "markdown": {"title": "xxx", "text": "xxx"},
            "at": {"atUserIds": ["xxx"], "isAtAll": false}
        }
        """
        if not response.text:
            return WebhookResponse.success()

        # \u6784\u5efa\u54cd\u5e94
        if response.markdown:
            body = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "\u80a1\u7968analyze\u52a9\u624b",
                    "text": response.text,
                }
            }
        else:
            body = {
                "msgtype": "text",
                "text": {
                    "content": response.text,
                }
            }

        # @\u53d1\u9001\u8005
        if response.at_user and message.user_id:
            body["at"] = {
                "atUserIds": [message.user_id],
                "isAtAll": False,
            }

        return WebhookResponse.success(body)

    def send_by_session_webhook(
        self,
        session_webhook: str,
        response: BotResponse,
        message: BotMessage
    ) -> bool:
        """
        \u901a\u8fc7 sessionWebhook \u53d1\u9001\u6d88\u606f

        \u9002\u7528\u4e8e\u9700\u8981\u5f02\u6b65\u53d1\u9001or\u591a\u6761\u6d88\u606f\u7684\u573a\u666f.

        Args:
            session_webhook: DingTalk\u63d0\u4f9b\u7684conversation Webhook URL
            response: \u54cd\u5e94\u5bf9\u8c61
            message: \u539f\u59cb\u6d88\u606f\u5bf9\u8c61

        Returns:
            \u662f\u5426send succeeded
        """
        if not session_webhook:
            logger.warning("[DingTalk] no available sessionWebhook")
            return False

        import requests

        try:
            # \u6784\u5efa\u6d88\u606f
            if response.markdown:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": "\u80a1\u7968analyze\u52a9\u624b",
                        "text": response.text,
                    }
                }
            else:
                payload = {
                    "msgtype": "text",
                    "text": {
                        "content": response.text,
                    }
                }

            # @\u53d1\u9001\u8005
            if response.at_user and message.user_id:
                payload["at"] = {
                    "atUserIds": [message.user_id],
                    "isAtAll": False,
                }

            # \u53d1\u9001request
            resp = requests.post(
                session_webhook,
                json=payload,
                timeout=10
            )

            if resp.status_code == 200:
                result = resp.json()
                if result.get('errcode') == 0:
                    logger.info("[DingTalk] sessionWebhook send succeeded")
                    return True
                else:
                    logger.error(f"[DingTalk] sessionWebhook send failed: {result}")
                    return False
            else:
                logger.error(f"[DingTalk] sessionWebhook requestfailed: {resp.status_code}")
                return False

        except Exception as e:
            logger.error(f"[DingTalk] sessionWebhook send exception: {e}")
            return False
