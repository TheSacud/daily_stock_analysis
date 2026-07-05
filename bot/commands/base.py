# -*- coding: utf-8 -*-
"""
===================================
command\u57fa\u7c7b
===================================

\u5b9a\u4e49command\u5904\u7406\u5668\u7684\u62bd\u8c61\u57fa\u7c7b; \u6240\u6709command\u90fd\u5fc5\u987b\u7ee7\u627f\u6b64\u7c7b.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional

from bot.models import BotMessage, BotResponse


class BotCommand(ABC):
    """
    command\u5904\u7406\u5668\u62bd\u8c61\u57fa\u7c7b

    \u6240\u6709command\u90fd\u5fc5\u987b\u7ee7\u627f\u6b64\u7c7b\u5e76\u5b9e\u73b0\u62bd\u8c61\u65b9\u6cd5.

    \u4f7f\u7528\u793a\u4f8b:
        class MyCommand(BotCommand):
            @property
            def name(self) -> str:
                return "mycommand"

            @property
            def aliases(self) -> List[str]:
                return ["mc", "my-command"]

            @property
            def description(self) -> str:
                return "\u8fd9\u662fmy-command"

            @property
            def usage(self) -> str:
                return "/mycommand [parameter]"

            def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
                return BotResponse.text_response("commandexecuted successfully")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        commandname (\u4e0d\u542bprefix)

        \u4f8b\u5982 "analyze"; user\u8f93\u5165 "/analyze" \u89e6\u53d1
        """
        pass

    @property
    @abstractmethod
    def aliases(self) -> List[str]:
        """
        commandalias\u5217\u8868

        \u4f8b\u5982 ["a", "analyze"]; user\u8f93\u5165 "/a" or "analyze" \u4e5f\u80fd\u89e6\u53d1
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """command\u63cf\u8ff0 (\u7528\u4e8ehelpinfo)"""
        pass

    @property
    @abstractmethod
    def usage(self) -> str:
        """
        \u4f7f\u7528\u8bf4\u660e (\u7528\u4e8ehelpinfo)

        \u4f8b\u5982 "/analyze <stock code>"
        """
        pass

    @property
    def hidden(self) -> bool:
        """
        \u662f\u5426\u5728help\u5217\u8868Medium\u9690\u85cf

        default False; \u8bbe\u4e3a True \u5219\u4e0d\u663e\u793a\u5728 /help \u5217\u8868Medium
        """
        return False

    @property
    def admin_only(self) -> bool:
        """
        \u662f\u5426\u4ec5\u7ba1\u7406\u5458\u53ef\u7528

        default False; \u8bbe\u4e3a True \u5219\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650
        """
        return False

    @abstractmethod
    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """
        \u6267\u884ccommand

        Args:
            message: \u539f\u59cb\u6d88\u606f\u5bf9\u8c61
            args: commandparameter\u5217\u8868 (\u5df2\u5206\u5272)

        Returns:
            BotResponse \u54cd\u5e94\u5bf9\u8c61
        """
        pass

    async def execute_async(self, message: BotMessage, args: List[str]) -> BotResponse:
        """\u5f02\u6b65\u6267\u884ccommand.

        default\u5c06\u540c\u6b65 `execute()` \u4e0b\u6c89\u5230\u7ebf\u7a0b\u6c60; \u907f\u514d\u5728\u5f02\u6b65\u5206\u53d1\u94fe\u8defMedium\u963b\u585e\u4e8b\u4ef6\u5faa\u73af.
        """
        return await asyncio.to_thread(self.execute, message, args)

    def validate_args(self, args: List[str]) -> Optional[str]:
        """
        \u9a8c\u8bc1parameter

        \u5b50\u7c7b\u53ef\u91cd\u5199\u6b64\u65b9\u6cd5\u8fdb\u884cparameter\u6821\u9a8c.

        Args:
            args: commandparameter\u5217\u8868

        Returns:
            \u5982\u679cparameter\u6709\u6548\u8fd4\u56de None; \u5426\u5219\u8fd4\u56deerrorinfo
        """
        return None

    def get_help_text(self) -> str:
        """\u83b7\u53d6help\u6587\u672c"""
        return f"**{self.name}** - {self.description}\nUsage: `{self.usage}`"
