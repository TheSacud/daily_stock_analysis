# -*- coding: utf-8 -*-
"""
===================================
\u673a\u5668\u4ebacommand\u89e6\u53d1\u7cfb\u7edf
===================================

\u901a\u8fc7 @\u673a\u5668\u4eba or\u53d1\u9001command\u89e6\u53d1\u80a1\u7968analyze\u7b49\u529f\u80fd.
\u652f\u6301Feishu、DingTalk、WeCom、Telegram \u7b49\u591a\u5e73\u53f0.

\u6a21chunks\u7ed3\u6784:
- models.py: \u7edf\u4e00\u7684\u6d88\u606f/\u54cd\u5e94\u6a21\u578b
- dispatcher.py: command\u5206\u53d1\u5668
- commands/: command\u5904\u7406\u5668
- platforms/: \u5e73\u53f0\u9002\u914d\u5668
- handler.py: Webhook \u5904\u7406\u5668

\u4f7f\u7528\u65b9\u5f0f:
1. config\u73af\u5883\u53d8\u91cf (\u5404\u5e73\u53f0\u7684 Token \u7b49)
2. started WebUI \u670d\u52a1
3. \u5728\u5404\u5e73\u53f0config Webhook URL:
   - Feishu: http://your-server/bot/feishu
   - DingTalk: http://your-server/bot/dingtalk
   - WeCom: http://your-server/bot/wecom
   - Telegram: http://your-server/bot/telegram

\u652f\u6301\u7684command:
- /analyze <stock code>  - analyze specified stocks
- /market             - market review
- /batch              - batchanalyzewatchlist
- /help               - \u663e\u793ahelp
- /status             - \u7cfb\u7edfstatus
"""

from bot.models import BotMessage, BotResponse, ChatType, WebhookResponse
from bot.dispatcher import CommandDispatcher, get_dispatcher

__all__ = [
    'BotMessage',
    'BotResponse',
    'ChatType',
    'WebhookResponse',
    'CommandDispatcher',
    'get_dispatcher',
]
