# -*- coding: utf-8 -*-
"""
===================================
helpcommand
===================================

\u663e\u793a\u53ef\u7528command\u5217\u8868\u548c\u4f7f\u7528\u8bf4\u660e.
"""

from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse


class HelpCommand(BotCommand):
    """
    helpcommand

    \u663e\u793a\u6240\u6709\u53ef\u7528command\u7684\u5217\u8868\u548c\u4f7f\u7528\u8bf4\u660e.
    \u4e5f\u53ef\u4ee5check\u770b\u7279\u5b9acommand\u7684\u8be6\u7ec6help.

    Usage:
        /help         - \u663e\u793a\u6240\u6709command
        /help analyze - \u663e\u793a analyze command\u7684\u8be6\u7ec6help
    """

    @property
    def name(self) -> str:
        return "help"

    @property
    def aliases(self) -> List[str]:
        return ["h", "help", "?"]

    @property
    def description(self) -> str:
        return "\u663e\u793ahelpinfo"

    @property
    def usage(self) -> str:
        return "/help [command\u540d]"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """\u6267\u884chelpcommand"""
        # \u5ef6\u8fdf\u5bfc\u5165\u907f\u514d\u5faa\u73af\u4f9d\u8d56
        from bot.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()

        # \u5982\u679c\u6307\u5b9a\u4e86command\u540d; \u663e\u793a\u8be5command\u7684\u8be6\u7ec6help
        if args:
            cmd_name = args[0]
            command = dispatcher.get_command(cmd_name)

            if command is None:
                return BotResponse.error_response(f"unknowncommand: {cmd_name}")

            # \u6784\u5efa\u8be6\u7ec6help
            help_text = self._format_command_help(command, dispatcher.command_prefix)
            return BotResponse.markdown_response(help_text)

        # \u663e\u793a\u6240\u6709command\u5217\u8868
        commands = dispatcher.list_commands(include_hidden=False)
        prefix = dispatcher.command_prefix

        help_text = self._format_help_list(commands, prefix)
        return BotResponse.markdown_response(help_text)

    def _format_help_list(self, commands: List[BotCommand], prefix: str) -> str:
        """\u683c\u5f0f\u5316command\u5217\u8868"""
        lines = [
            "📚 **\u80a1\u7968analyze\u52a9\u624b - commandhelp**",
            "",
            "\u53ef\u7528command: ",
            "",
        ]

        for cmd in commands:
            # command\u540d\u548calias
            aliases_str = ""
            if cmd.aliases:
                # \u8fc7\u6ee4\u6389Medium\u6587alias; \u53ea\u663e\u793a\u82f1\u6587alias
                en_aliases = [a for a in cmd.aliases if a.isascii()]
                if en_aliases:
                    aliases_str = f" ({', '.join(prefix + a for a in en_aliases[:2])})"

            lines.append(f"• {prefix}{cmd.name}{aliases_str} - {cmd.description}")
            lines.append("")

        lines.extend([
            "",
            "---",
            f"💡 \u8f93\u5165 {prefix}help <command\u540d> check\u770b\u8be6\u7ec6Usage",
            "",
            "**\u793a\u4f8b: **",
            "",
            f"• {prefix}analyze 301023 - \u5955\u5e06\u4f20\u52a8",
            "",
            f"• {prefix}market - check\u770bmarket review",
            "",
            f"• {prefix}batch - batchanalyzewatchlist",
        ])

        return "\n".join(lines)

    def _format_command_help(self, command: BotCommand, prefix: str) -> str:
        """\u683c\u5f0f\u5316\u5355\u4e2acommand\u7684\u8be6\u7ec6help"""
        lines = [
            f"📖 **{prefix}{command.name}** - {command.description}",
            "",
            f"**Usage: ** `{command.usage}`",
            "",
        ]

        # alias
        if command.aliases:
            aliases = [f"`{prefix}{a}`" if a.isascii() else f"`{a}`" for a in command.aliases]
            lines.append(f"**alias: ** {', '.join(aliases)}")
            lines.append("")

        # \u6743\u9650
        if command.admin_only:
            lines.append("⚠️ **\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650**")
            lines.append("")

        return "\n".join(lines)
