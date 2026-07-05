# -*- coding: utf-8 -*-
"""
===================================
\u5e73\u53f0\u9002\u914d\u5668\u57fa\u7c7b
===================================

\u5b9a\u4e49\u5e73\u53f0\u9002\u914d\u5668\u7684\u62bd\u8c61\u57fa\u7c7b; \u5404\u5e73\u53f0\u5fc5\u987b\u7ee7\u627f\u6b64\u7c7b.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

from bot.models import BotMessage, BotResponse, WebhookResponse


class BotPlatform(ABC):
    """
    \u5e73\u53f0\u9002\u914d\u5668\u62bd\u8c61\u57fa\u7c7b

    \u8d1f\u8d23:
    1. \u9a8c\u8bc1 Webhook request\u7b7e\u540d
    2. \u89e3\u6790\u5e73\u53f0\u6d88\u606f\u4e3a\u7edf\u4e00\u683c\u5f0f
    3. \u5c06\u54cd\u5e94\u8f6c\u6362\u4e3a\u5e73\u53f0\u683c\u5f0f

    \u4f7f\u7528\u793a\u4f8b:
        class MyPlatform(BotPlatform):
            @property
            def platform_name(self) -> str:
                return "myplatform"

            def verify_request(self, headers, body) -> bool:
                # \u9a8c\u8bc1\u7b7e\u540d\u903b\u8f91
                return True

            def parse_message(self, data) -> Optional[BotMessage]:
                # \u89e3\u6790\u6d88\u606f\u903b\u8f91
                return BotMessage(...)

            def format_response(self, response, message) -> WebhookResponse:
                # \u683c\u5f0f\u5316\u54cd\u5e94\u903b\u8f91
                return WebhookResponse.success({"text": response.text})
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        \u5e73\u53f0\u6807\u8bc6name

        \u7528\u4e8e\u8def\u7531\u5339\u914d\u548clog\u6807\u8bc6; \u5982 "feishu", "dingtalk"
        """
        pass

    @abstractmethod
    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        \u9a8c\u8bc1request\u7b7e\u540d

        \u5404\u5e73\u53f0\u6709\u4e0d\u540c\u7684\u7b7e\u540d\u9a8c\u8bc1\u673a\u5236; \u9700\u8981\u5355\u72ec\u5b9e\u73b0.

        Args:
            headers: HTTP request\u5934
            body: request\u4f53\u539f\u59cb\u5b57\u8282

        Returns:
            \u7b7e\u540d\u662f\u5426\u6709\u6548
        """
        pass

    @abstractmethod
    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:
        """
        \u89e3\u6790\u5e73\u53f0\u6d88\u606f\u4e3a\u7edf\u4e00\u683c\u5f0f

        \u5c06\u5e73\u53f0\u7279\u5b9a\u7684\u6d88\u606f\u683c\u5f0f\u8f6c\u6362\u4e3a BotMessage.
        \u5982\u679c\u4e0d\u662f\u9700\u8981\u5904\u7406\u7684\u6d88\u606f\u7c7b\u578b (\u5982\u4e8b\u4ef6\u56de\u8c03); \u8fd4\u56de None.

        Args:
            data: \u89e3\u6790\u540e\u7684 JSON \u6570\u636e

        Returns:
            BotMessage \u5bf9\u8c61; or None (\u4e0d\u9700\u8981\u5904\u7406)
        """
        pass

    @abstractmethod
    def format_response(
        self,
        response: BotResponse,
        message: BotMessage
    ) -> WebhookResponse:
        """
        \u5c06\u7edf\u4e00\u54cd\u5e94\u8f6c\u6362\u4e3a\u5e73\u53f0\u683c\u5f0f

        Args:
            response: \u7edf\u4e00\u54cd\u5e94\u5bf9\u8c61
            message: \u539f\u59cb\u6d88\u606f\u5bf9\u8c61 (\u7528\u4e8e\u83b7\u53d6\u56de\u590d\u76ee\u6807\u7b49info)

        Returns:
            WebhookResponse \u5bf9\u8c61
        """
        pass

    def send_followup(
        self,
        response: 'BotResponse',
        message: 'BotMessage',
    ) -> bool:
        """Send a follow-up message after a deferred webhook response.

        Override in platforms that return a deferred acknowledgement
        (e.g. Discord type 5) so the final command result can be delivered
        asynchronously.  The default implementation is a no-op.

        Returns:
            ``True`` if the follow-up was sent successfully.
        """
        return False

    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:
        """
        \u5904\u7406\u5e73\u53f0\u9a8c\u8bc1request

        \u90e8\u5206\u5e73\u53f0\u5728config Webhook \u65f6\u4f1a\u53d1\u9001\u9a8c\u8bc1request; \u9700\u8981\u8fd4\u56de\u7279\u5b9a\u54cd\u5e94.
        \u5b50\u7c7b\u53ef\u91cd\u5199\u6b64\u65b9\u6cd5.

        Args:
            data: request\u6570\u636e

        Returns:
            \u9a8c\u8bc1\u54cd\u5e94; or None (\u4e0d\u662f\u9a8c\u8bc1request)
        """
        return None

    def handle_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
        data: Dict[str, Any]
    ) -> Tuple[Optional[BotMessage], Optional[WebhookResponse]]:
        """
        \u5904\u7406 Webhook request

        \u8fd9\u662f\u4e3b\u5165\u53e3\u65b9\u6cd5; \u534f\u8c03\u9a8c\u8bc1、\u89e3\u6790\u7b49\u6d41\u7a0b.

        Args:
            headers: HTTP request\u5934
            body: request\u4f53\u539f\u59cb\u5b57\u8282
            data: \u89e3\u6790\u540e\u7684 JSON \u6570\u636e

        Returns:
            (BotMessage, WebhookResponse) \u5143\u7ec4
            - \u5982\u679c\u662f\u9a8c\u8bc1request: (None, challenge_response)
            - \u5982\u679c\u662f\u666e\u901a\u6d88\u606f: (message, None) - \u54cd\u5e94\u5c06\u5728command\u5904\u7406\u540e\u751f\u6210
            - \u5982\u679c\u9a8c\u8bc1failedor\u65e0\u9700\u5904\u7406: (None, error_response or None)
        """
        # 1. \u68c0check\u662f\u5426\u662f\u9a8c\u8bc1request
        challenge_response = self.handle_challenge(data)
        if challenge_response:
            return None, challenge_response

        # 2. \u9a8c\u8bc1request\u7b7e\u540d
        if not self.verify_request(headers, body):
            return None, WebhookResponse.error("Invalid signature", 403)

        # 3. \u89e3\u6790\u6d88\u606f
        message = self.parse_message(data)

        return message, None
