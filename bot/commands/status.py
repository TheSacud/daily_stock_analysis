# -*- coding: utf-8 -*-
"""
===================================
statuscommand
===================================

\u663e\u793a\u7cfb\u7edfrun status\u548cconfiginfo.
"""

import platform
import sys
from datetime import datetime
from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse


class StatusCommand(BotCommand):
    """
    statuscommand

    \u663e\u793a\u7cfb\u7edfrun status; \u5305\u62ec:
    - \u670d\u52a1status
    - configinfo
    - \u53ef\u7528\u529f\u80fd
    """

    @property
    def name(self) -> str:
        return "status"

    @property
    def aliases(self) -> List[str]:
        return ["s", "status", "info"]

    @property
    def description(self) -> str:
        return "show system status"

    @property
    def usage(self) -> str:
        return "/status"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """\u6267\u884cstatuscommand"""
        from src.config import get_config

        config = get_config()

        # \u6536\u96c6statusinfo
        status_info = self._collect_status(config)

        # \u683c\u5f0f\u5316\u8f93\u51fa
        text = self._format_status(status_info, message.platform)

        return BotResponse.markdown_response(text)

    def _collect_status(self, config) -> dict:
        """\u6536\u96c6\u7cfb\u7edfstatusinfo"""
        from src.config import _uses_direct_env_provider, get_configured_llm_models

        status = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.system(),
            "stock_count": len(config.stock_list),
            "stock_list": config.stock_list[:5],  # \u53ea\u663e\u793a\u524d5\u4e2a
        }

        # AI configstatus
        llm_channels = getattr(config, "llm_channels", []) or []
        llm_model_list = getattr(config, "llm_model_list", []) or []
        llm_model = (getattr(config, "litellm_model", "") or "").strip()
        agent_model = (getattr(config, "agent_litellm_model", "") or "").strip()
        status["ai_primary_model"] = llm_model
        status["ai_agent_model"] = agent_model or ("\u7ee7\u627f\u4e3b\u6a21\u578b" if llm_model else "")
        status["ai_channels"] = [
            str(channel.get("name") or "").strip()
            for channel in llm_channels
            if str(channel.get("name") or "").strip()
        ]
        status["ai_yaml"] = (
            getattr(config, "llm_models_source", "") == "litellm_config"
            and bool(llm_model_list)
        )
        status["ai_legacy_keys"] = {
            "Gemini": bool(getattr(config, "gemini_api_keys", [])),
            "OpenAI": bool(getattr(config, "openai_api_keys", [])),
            "Anthropic": bool(getattr(config, "anthropic_api_keys", [])),
            "DeepSeek": bool(getattr(config, "deepseek_api_keys", [])),
        }
        has_direct_env_model = bool(llm_model) and _uses_direct_env_provider(llm_model)
        available_router_model_set = set(get_configured_llm_models(llm_model_list))
        primary_model_reachable = not (
            available_router_model_set
            and llm_model
            and not _uses_direct_env_provider(llm_model)
            and llm_model not in available_router_model_set
        )
        status["ai_available"] = bool(
            llm_model
            and (has_direct_env_model or (llm_model_list and primary_model_reachable))
        )

        # search\u670d\u52a1status
        status["search_bocha"] = len(config.bocha_api_keys) > 0
        status["search_tavily"] = len(config.tavily_api_keys) > 0
        status["search_brave"] = len(config.brave_api_keys) > 0
        status["search_serpapi"] = len(config.serpapi_keys) > 0
        status["search_minimax"] = len(config.minimax_api_keys) > 0
        status["search_searxng"] = config.has_searxng_enabled()

        # notification channelstatus
        status["notify_wechat"] = bool(config.wechat_webhook_url)
        status["notify_feishu"] = bool(config.feishu_webhook_url)
        status["notify_telegram"] = bool(config.telegram_bot_token and config.telegram_chat_id)
        status["notify_email"] = bool(config.email_sender and config.email_password)
        status["notify_custom"] = bool(getattr(config, "custom_webhook_urls", []))
        status["notify_discord"] = bool(
            getattr(config, "discord_webhook_url", None)
            or (
                getattr(config, "discord_bot_token", None)
                and getattr(config, "discord_main_channel_id", None)
            )
        )
        status["notify_slack"] = bool(
            getattr(config, "slack_webhook_url", None)
            or (
                getattr(config, "slack_bot_token", None)
                and getattr(config, "slack_channel_id", None)
            )
        )
        status["notify_push"] = bool(
            getattr(config, "pushplus_token", None)
            or (
                getattr(config, "pushover_user_key", None)
                and getattr(config, "pushover_api_token", None)
            )
            or getattr(config, "serverchan3_sendkey", None)
        )

        return status

    def _format_status(self, status: dict, platform: str) -> str:
        """\u683c\u5f0f\u5316statusinfo"""
        # status\u56fe\u6807
        def icon(enabled: bool) -> str:
            return "✅" if enabled else "❌"

        lines = [
            "📊 **\u80a1\u7968analyze\u52a9\u624b - \u7cfb\u7edfstatus**",
            "",
            f"🕐 \u65f6\u95f4: {status['timestamp']}",
            f"🐍 Python: {status['python_version']}",
            f"💻 \u5e73\u53f0: {status['platform']}",
            "",
            "---",
            "",
            "**📈 watchlistconfig**",
            f"• \u80a1\u7968count: {status['stock_count']} \u53ea",
        ]

        if status['stock_list']:
            stocks_preview = ", ".join(status['stock_list'])
            if status['stock_count'] > 5:
                stocks_preview += f" ... \u7b49 {status['stock_count']} \u53ea"
            lines.append(f"• \u80a1\u7968\u5217\u8868: {stocks_preview}")

        lines.extend([
            "",
            "**🤖 AI analyze\u670d\u52a1**",
            f"• \u4e3b\u6a21\u578b: {status['ai_primary_model'] or 'not configured'}",
            f"• Agent \u6a21\u578b: {status['ai_agent_model'] or 'not configured'}",
            f"• LLM \u6e20\u9053: {', '.join(status['ai_channels']) if status['ai_channels'] else 'not configured'}",
            f"• LiteLLM YAML: {icon(status['ai_yaml'])}",
            "• Legacy Key: "
            + ", ".join(
                f"{name}{icon(enabled)}"
                for name, enabled in status["ai_legacy_keys"].items()
            ),
            "",
            "**🔍 search\u670d\u52a1**",
            f"• Bocha: {icon(status['search_bocha'])}",
            f"• Tavily: {icon(status['search_tavily'])}",
            f"• Brave: {icon(status['search_brave'])}",
            f"• SerpAPI: {icon(status['search_serpapi'])}",
            f"• MiniMax: {icon(status['search_minimax'])}",
            f"• SearXNG: {icon(status['search_searxng'])}",
            "",
            "**📢 notification channel**",
            f"• WeCom: {icon(status['notify_wechat'])}",
            f"• Feishu: {icon(status['notify_feishu'])}",
            f"• Telegram: {icon(status['notify_telegram'])}",
            f"• Email: {icon(status['notify_email'])}",
            f"• \u81ea\u5b9a\u4e49 Webhook: {icon(status['notify_custom'])}",
            f"• Discord: {icon(status['notify_discord'])}",
            f"• Slack: {icon(status['notify_slack'])}",
            f"• PushPlus/Pushover/Server\u91713: {icon(status['notify_push'])}",
        ])

        # AI \u670d\u52a1\u603b\u4f53status
        if status["ai_available"]:
            lines.extend([
                "",
                "---",
                "✅ **\u7cfb\u7edf\u5c31\u7eea; \u53ef\u4ee5\u5f00\u59cbanalyze！**",
            ])
        else:
            lines.extend([
                "",
                "---",
                "⚠️ **AI \u670d\u52a1not configured; analyze\u529f\u80fdunavailable**",
                "\u8bf7config LITELLM_MODEL、LLM_CHANNELS、LITELLM_CONFIG or\u4efb\u4e00 provider API Key",
            ])

        return "\n".join(lines)
