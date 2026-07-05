# -*- coding: utf-8 -*-
"""
Chat command for free-form conversation with the Agent.
"""

import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse, ChatType
from src.config import get_config

logger = logging.getLogger(__name__)


def _scoped_chat_session_id(message: BotMessage) -> str:
    """Return the chat session id for the current conversation scope."""
    base_session_id = f"{message.platform}_{message.user_id}"
    if message.chat_type == ChatType.GROUP and message.chat_id:
        return f"{base_session_id}:{message.chat_id}:chat"
    return f"{base_session_id}:chat"


def _resolve_chat_session_id(message: BotMessage) -> str:
    """Prefer the legacy private-chat session id when prior history already exists."""
    legacy_session_id = f"{message.platform}_{message.user_id}"
    session_id = _scoped_chat_session_id(message)

    # Group chats must stay room-scoped so parallel threads in different groups
    # do not share one persisted conversation history.
    if message.chat_type == ChatType.GROUP and message.chat_id:
        return session_id

    try:
        from src.storage import get_db

        db = get_db()
        legacy_exists = db.conversation_session_exists(legacy_session_id)
        current_exists = db.conversation_session_exists(session_id)
        if legacy_exists and not current_exists:
            return legacy_session_id
    except Exception as exc:
        logger.debug("Chat session compatibility check failed: %s", exc)

    return session_id

class ChatCommand(BotCommand):
    """
    Chat command handler.

    Usage: /chat <message>
    Example: /chat \u5e2e\u6211analyze\u4e00\u4e0b\u8305\u53f0\u6700\u8fd1\u7684\u8d70\u52bf
    """

    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "free-form chat with the AI assistant (requires Agent mode)"

    @property
    def usage(self) -> str:
        return "/chat <question>"

    @property
    def aliases(self) -> list[str]:
        return ["c", "ask"]

    def validate_args(self, args: List[str]) -> Optional[str]:
        """Require at least one argument (the question)."""
        if not args:
            return "provide the question to ask."
        return None

    def execute(self, message: BotMessage, args: list[str]) -> BotResponse:
        """Execute the chat command."""
        config = get_config()

        if not config.agent_mode:
            return BotResponse.text_response(
                "⚠️ Agent mode\u672a\u5f00\u542f; \u65e0\u6cd5\u4f7f\u7528\u5bf9\u8bdd\u529f\u80fd.\n\u8bf7\u5728configMedium\u8bbe\u7f6e `AGENT_MODE=true`."
            )

        if not args:
            return BotResponse.text_response(
                "⚠️ provide the question to ask.\nUsage: `/chat <question>`\n\u793a\u4f8b: `/chat \u5e2e\u6211analyze\u4e00\u4e0b\u8305\u53f0\u6700\u8fd1\u7684\u8d70\u52bf`"
            )

        user_message = " ".join(args)
        session_id = _resolve_chat_session_id(message)

        try:
            from src.agent.factory import build_agent_executor
            executor = build_agent_executor(config)
            result = executor.chat(message=user_message, session_id=session_id)

            if result.success:
                return BotResponse.text_response(result.content)
            else:
                return BotResponse.text_response(f"⚠️ conversation failed: {result.error}")

        except Exception as e:
            logger.error(f"Chat command failed: {e}")
            logger.exception("Chat error details:")
            return BotResponse.text_response(f"⚠️ conversation execution error: {str(e)}")
