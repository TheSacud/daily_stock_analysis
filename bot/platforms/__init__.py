# -*- coding: utf-8 -*-
"""
===================================
\u5e73\u53f0\u9002\u914d\u5668\u6a21chunks
===================================

\u5305\u542b\u5404\u5e73\u53f0\u7684 Webhook \u5904\u7406\u548c\u6d88\u606f\u89e3\u6790\u903b\u8f91.

\u652f\u6301\u4e24\u79cd\u63a5\u5165mode:
1. Webhook mode: \u9700\u8981\u516c\u7f51 IP; config\u56de\u8c03 URL
2. Stream mode: \u65e0\u9700\u516c\u7f51 IP; \u901a\u8fc7 WebSocket \u957f\u8fde\u63a5 (DingTalk、Feishu\u652f\u6301)
"""

from bot.platforms.base import BotPlatform
from bot.platforms.dingtalk import DingtalkPlatform

# \u6240\u6709\u53ef\u7528\u5e73\u53f0 (Webhook mode)
ALL_PLATFORMS = {
    'dingtalk': DingtalkPlatform,
}

# DingTalk Stream mode (optional)
try:
    from bot.platforms.dingtalk_stream import (
        DingtalkStreamClient,
        DingtalkStreamHandler,
        get_dingtalk_stream_client,
        start_dingtalk_stream_background,
        DINGTALK_STREAM_AVAILABLE,
    )
except ImportError:
    DINGTALK_STREAM_AVAILABLE = False
    DingtalkStreamClient = None
    DingtalkStreamHandler = None
    get_dingtalk_stream_client = lambda: None
    start_dingtalk_stream_background = lambda: False

# Feishu Stream mode (optional)
try:
    from bot.platforms.feishu_stream import (
        FeishuStreamClient,
        FeishuStreamHandler,
        FeishuReplyClient,
        get_feishu_stream_client,
        start_feishu_stream_background,
        FEISHU_SDK_AVAILABLE,
    )
except ImportError:
    FEISHU_SDK_AVAILABLE = False
    FeishuStreamClient = None
    FeishuStreamHandler = None
    FeishuReplyClient = None
    get_feishu_stream_client = lambda: None
    start_feishu_stream_background = lambda: False

__all__ = [
    'BotPlatform',
    'DingtalkPlatform',
    'ALL_PLATFORMS',
    # DingTalk Stream mode
    'DingtalkStreamClient',
    'DingtalkStreamHandler',
    'get_dingtalk_stream_client',
    'start_dingtalk_stream_background',
    'DINGTALK_STREAM_AVAILABLE',
    # Feishu Stream mode
    'FeishuStreamClient',
    'FeishuStreamHandler',
    'FeishuReplyClient',
    'get_feishu_stream_client',
    'start_feishu_stream_background',
    'FEISHU_SDK_AVAILABLE',
]
