# -*- coding: utf-8 -*-
"""
===================================
\u673a\u5668\u4eba\u6d88\u606f\u6a21\u578b
===================================

\u5b9a\u4e49\u7edf\u4e00\u7684\u6d88\u606f\u548c\u54cd\u5e94\u6a21\u578b; \u5c4f\u853d\u5404\u5e73\u53f0\u5dee\u5f02.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class ChatType(str, Enum):
    """conversation\u7c7b\u578b"""
    GROUP = "group"      # \u7fa4\u804a
    PRIVATE = "private"  # \u79c1\u804a
    UNKNOWN = "unknown"  # unknown


class Platform(str, Enum):
    """\u5e73\u53f0\u7c7b\u578b"""
    FEISHU = "feishu"        # Feishu
    DINGTALK = "dingtalk"    # DingTalk
    WECOM = "wecom"          # WeCom
    TELEGRAM = "telegram"    # Telegram
    UNKNOWN = "unknown"      # unknown


@dataclass
class BotMessage:
    """
    \u7edf\u4e00\u7684\u673a\u5668\u4eba\u6d88\u606f\u6a21\u578b

    \u5c06\u5404\u5e73\u53f0\u7684\u6d88\u606f\u683c\u5f0f\u7edf\u4e00\u4e3a\u6b64\u6a21\u578b; \u4fbf\u4e8ecommand\u5904\u7406\u5668\u5904\u7406.

    Attributes:
        platform: \u5e73\u53f0\u6807\u8bc6
        message_id: \u6d88\u606f ID (\u5e73\u53f0\u539f\u59cb ID)
        user_id: \u53d1\u9001\u8005 ID
        user_name: \u53d1\u9001\u8005name
        chat_id: conversation ID (\u7fa4\u804a ID or\u79c1\u804a ID)
        chat_type: conversation\u7c7b\u578b
        content: \u6d88\u606f\u6587\u672c\u5185\u5bb9 (\u5df2\u53bb\u9664 @\u673a\u5668\u4eba \u90e8\u5206)
        raw_content: \u539f\u59cb\u6d88\u606f\u5185\u5bb9
        mentioned: \u662f\u5426 @\u4e86\u673a\u5668\u4eba
        mentions: @\u7684user\u5217\u8868
        timestamp: \u6d88\u606f\u65f6\u95f4\u6233
        raw_data: \u539f\u59cbrequest\u6570\u636e (\u5e73\u53f0\u7279\u5b9a; \u7528\u4e8e\u8c03\u8bd5)
    """
    platform: str
    message_id: str
    user_id: str
    user_name: str
    chat_id: str
    chat_type: ChatType
    content: str
    raw_content: str = ""
    mentioned: bool = False
    mentions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def get_command_and_args(self, prefix: str = "/") -> tuple:
        """
        \u89e3\u6790command\u548cparameter

        Args:
            prefix: commandprefix; default "/"

        Returns:
            (command, args) \u5143\u7ec4; \u5982 ("analyze", ["600519"])
            \u5982\u679c\u4e0d\u662fcommand; \u8fd4\u56de (None, [])
        """
        text = self.content.strip()

        # \u68c0check\u662f\u5426\u4ee5commandprefix\u5f00\u5934
        if not text.startswith(prefix):
            # \u5c1d\u8bd5\u5339\u914dMedium\u6587command (\u65e0prefix)
            chinese_commands = {
                'analyze': 'analyze',
                '\u5927\u76d8': 'market',
                'batch': 'batch',
                'help': 'help',
                'status': 'status',
            }
            for cn_cmd, en_cmd in chinese_commands.items():
                if text.startswith(cn_cmd):
                    args = text[len(cn_cmd):].strip().split()
                    return en_cmd, args
            return None, []

        # \u53bb\u9664prefix
        text = text[len(prefix):]

        # \u5206\u5272command\u548cparameter
        parts = text.split()
        if not parts:
            return None, []

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        return command, args

    def is_command(self, prefix: str = "/") -> bool:
        """\u68c0check\u6d88\u606f\u662f\u5426\u662fcommand"""
        cmd, _ = self.get_command_and_args(prefix)
        return cmd is not None


@dataclass
class BotResponse:
    """
    \u7edf\u4e00\u7684\u673a\u5668\u4eba\u54cd\u5e94\u6a21\u578b

    command\u5904\u7406\u5668\u8fd4\u56de\u6b64\u6a21\u578b; \u7531\u5e73\u53f0\u9002\u914d\u5668\u8f6c\u6362\u4e3a\u5e73\u53f0\u7279\u5b9a\u683c\u5f0f.

    Attributes:
        text: \u56de\u590d\u6587\u672c
        markdown: \u662f\u5426\u4e3a Markdown \u683c\u5f0f
        at_user: \u662f\u5426 @\u53d1\u9001\u8005
        reply_to_message: \u662f\u5426\u56de\u590d\u539f\u6d88\u606f
        extra: \u989d\u5916\u6570\u636e (\u5e73\u53f0\u7279\u5b9a)
    """
    text: str
    markdown: bool = False
    at_user: bool = True
    reply_to_message: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def text_response(cls, text: str, at_user: bool = True) -> 'BotResponse':
        """\u521b\u5efa\u7eaf\u6587\u672c\u54cd\u5e94"""
        return cls(text=text, markdown=False, at_user=at_user)

    @classmethod
    def markdown_response(cls, text: str, at_user: bool = True) -> 'BotResponse':
        """\u521b\u5efa Markdown \u54cd\u5e94"""
        return cls(text=text, markdown=True, at_user=at_user)

    @classmethod
    def error_response(cls, message: str) -> 'BotResponse':
        """\u521b\u5efaerror\u54cd\u5e94"""
        return cls(text=f"❌ error: {message}", markdown=False, at_user=True)


@dataclass
class WebhookResponse:
    """
    Webhook \u54cd\u5e94\u6a21\u578b

    \u5e73\u53f0\u9002\u914d\u5668\u8fd4\u56de\u6b64\u6a21\u578b; \u5305\u542b HTTP \u54cd\u5e94\u5185\u5bb9.

    Attributes:
        status_code: HTTP status\u7801
        body: \u54cd\u5e94\u4f53 (\u5b57\u5178; \u5c06\u88ab JSON \u5e8f\u5217\u5316)
        headers: \u989d\u5916\u7684\u54cd\u5e94\u5934
    """
    status_code: int = 200
    body: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def success(cls, body: Optional[Dict] = None) -> 'WebhookResponse':
        """create succeeded\u54cd\u5e94"""
        return cls(status_code=200, body=body or {})

    @classmethod
    def challenge(cls, challenge: str) -> 'WebhookResponse':
        """\u521b\u5efa\u9a8c\u8bc1\u54cd\u5e94 (\u7528\u4e8e\u5e73\u53f0 URL \u9a8c\u8bc1)"""
        return cls(status_code=200, body={"challenge": challenge})

    @classmethod
    def error(cls, message: str, status_code: int = 400) -> 'WebhookResponse':
        """\u521b\u5efaerror\u54cd\u5e94"""
        return cls(status_code=status_code, body={"error": message})
