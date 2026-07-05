# -*- coding: utf-8 -*-
"""
===================================
command\u5206\u53d1\u5668
===================================

\u8d1f\u8d23\u89e3\u6790command、\u5339\u914d\u5904\u7406\u5668、\u5206\u53d1\u6267\u884c.
"""

import asyncio
import logging
import re
import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Type, Callable

from bot.models import BotMessage, BotResponse
from bot.commands.base import BotCommand

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    \u7b80\u5355\u7684\u9891\u7387limit\u5668

    \u57fa\u4e8e\u6ed1\u52a8\u7a97\u53e3\u7b97\u6cd5; limit\u6bcf\u4e2auser\u7684request\u9891\u7387.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: \u7a97\u53e3\u5185\u6700\u5927request\u6570
            window_seconds: \u7a97\u53e3\u65f6\u95f4 (\u79d2)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        """
        \u68c0checkuser\u662f\u5426\u5141\u8bb8request

        Args:
            user_id: user\u6807\u8bc6

        Returns:
            \u662f\u5426\u5141\u8bb8
        """
        now = time.time()
        window_start = now - self.window_seconds

        # \u6e05\u7406\u8fc7\u671f\u8bb0\u5f55
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if t > window_start
        ]

        # \u68c0check\u662f\u5426\u8d85\u9650
        if len(self._requests[user_id]) >= self.max_requests:
            return False

        # \u8bb0\u5f55this runrequest
        self._requests[user_id].append(now)
        return True

    def get_remaining(self, user_id: str) -> int:
        """\u83b7\u53d6\u5269\u4f59\u53ef\u7528request\u6570"""
        now = time.time()
        window_start = now - self.window_seconds

        # \u6e05\u7406\u8fc7\u671f\u8bb0\u5f55
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if t > window_start
        ]

        return max(0, self.max_requests - len(self._requests[user_id]))


class CommandDispatcher:
    """
    command\u5206\u53d1\u5668

    \u804c\u8d23:
    1. \u6ce8\u518c\u548c\u7ba1\u7406command\u5904\u7406\u5668
    2. \u89e3\u6790\u6d88\u606fMedium\u7684command\u548cparameter
    3. \u5206\u53d1command\u5230\u5bf9\u5e94\u5904\u7406\u5668
    4. \u5904\u7406unknowncommand\u548cerror

    \u4f7f\u7528\u793a\u4f8b:
        dispatcher = CommandDispatcher()
        dispatcher.register(AnalyzeCommand())
        dispatcher.register(HelpCommand())

        response = dispatcher.dispatch(message)
    """

    def __init__(
        self,
        command_prefix: str = "/",
        rate_limit_requests: int = 10,
        rate_limit_window: int = 60,
        admin_users: Optional[List[str]] = None
    ):
        """
        Args:
            command_prefix: commandprefix; default "/"
            rate_limit_requests: \u9891\u7387limit: \u7a97\u53e3\u5185\u6700\u5927request\u6570
            rate_limit_window: \u9891\u7387limit: \u7a97\u53e3\u65f6\u95f4 (\u79d2)
            admin_users: \u7ba1\u7406\u5458user ID \u5217\u8868
        """
        self.command_prefix = command_prefix
        self.admin_users = set(admin_users or [])

        self._commands: Dict[str, BotCommand] = {}
        self._aliases: Dict[str, str] = {}
        self._rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)

        # \u56de\u8c03\u51fd\u6570: \u83b7\u53d6helpcommand\u7684command\u5217\u8868
        self._help_command_getter: Optional[Callable] = None

    def register(self, command: BotCommand) -> None:
        """
        registered command

        Args:
            command: command\u5b9e\u4f8b
        """
        name = command.name.lower()

        if name in self._commands:
            logger.warning(f"[Dispatcher] command '{name}' already exists; will be overwritten")

        self._commands[name] = command
        logger.debug(f"[Dispatcher] registered command: {name}")

        # \u6ce8\u518calias
        for alias in command.aliases:
            alias_lower = alias.lower()
            if alias_lower in self._aliases:
                logger.warning(f"[Dispatcher] alias '{alias_lower}' already exists; will be overwritten")
            self._aliases[alias_lower] = name
            logger.debug(f"[Dispatcher] \u6ce8\u518calias: {alias_lower} -> {name}")

    def register_class(self, command_class: Type[BotCommand]) -> None:
        """
        registered command\u7c7b (\u81ea\u52a8\u5b9e\u4f8b\u5316)

        Args:
            command_class: command\u7c7b
        """
        self.register(command_class())

    def unregister(self, name: str) -> bool:
        """
        unregistered command

        Args:
            name: commandname

        Returns:
            \u662f\u5426success\u6ce8\u9500
        """
        name = name.lower()

        if name not in self._commands:
            return False

        command = self._commands.pop(name)

        # \u79fb\u9664alias
        for alias in command.aliases:
            self._aliases.pop(alias.lower(), None)

        logger.debug(f"[Dispatcher] unregistered command: {name}")
        return True

    def get_command(self, name: str) -> Optional[BotCommand]:
        """
        \u83b7\u53d6command

        \u652f\u6301command\u540d\u548caliasquery.

        Args:
            name: command\u540doralias

        Returns:
            command\u5b9e\u4f8b; or None
        """
        name = name.lower()

        # \u5148checkcommand\u540d
        if name in self._commands:
            return self._commands[name]

        # \u518dcheckalias
        if name in self._aliases:
            return self._commands.get(self._aliases[name])

        return None

    def list_commands(self, include_hidden: bool = False) -> List[BotCommand]:
        """
        \u5217\u51fa\u6240\u6709command

        Args:
            include_hidden: \u662f\u5426\u5305\u542b\u9690\u85cfcommand

        Returns:
            command\u5217\u8868
        """
        commands = list(self._commands.values())

        if not include_hidden:
            commands = [c for c in commands if not c.hidden]

        return sorted(commands, key=lambda c: c.name)

    def is_admin(self, user_id: str) -> bool:
        """\u68c0checkuser\u662f\u5426\u662f\u7ba1\u7406\u5458"""
        return user_id in self.admin_users

    def add_admin(self, user_id: str) -> None:
        """\u6dfb\u52a0\u7ba1\u7406\u5458"""
        self.admin_users.add(user_id)

    def remove_admin(self, user_id: str) -> None:
        """\u79fb\u9664\u7ba1\u7406\u5458"""
        self.admin_users.discard(user_id)

    def dispatch(self, message: BotMessage) -> BotResponse:
        """\u540c\u6b65\u5206\u53d1\u6d88\u606f.

        \u4fdd\u6301\u73b0\u6709\u540c\u6b65\u8c03\u7528\u65b9\u517c\u5bb9; \u5b9e\u9645\u903b\u8f91\u59d4\u6258\u7ed9 `dispatch_async()`.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self._dispatch_sync(message)

        result_holder: Dict[str, BotResponse] = {}
        error_holder: Dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_holder["response"] = self._dispatch_sync(message)
            except BaseException as exc:  # pragma: no cover
                error_holder["error"] = exc

        worker = threading.Thread(target=_runner, daemon=True)
        worker.start()
        worker.join()

        if "error" in error_holder:
            raise error_holder["error"]

        return result_holder.get("response", BotResponse.error_response("command execution failed"))

    def _prepare_dispatch(self, message: BotMessage) -> tuple[Optional[str], List[str], Optional[BotCommand], Optional[BotResponse]]:
        """Run shared dispatch pre-checks for sync/async entrypoints."""
        if not self._rate_limiter.is_allowed(message.user_id):
            remaining_time = self._rate_limiter.window_seconds
            return None, [], None, BotResponse.error_response(
                f"request\u8fc7\u4e8e\u9891\u7e41; \u8bf7 {remaining_time} \u79d2\u540e\u518d\u8bd5"
            )

        cmd_name, args = message.get_command_and_args(self.command_prefix)
        if cmd_name is None:
            return None, args, None, None

        logger.info(f"[Dispatcher] receivedcommand: {cmd_name}, parameter: {args}, user: {message.user_name}")

        command = self.get_command(cmd_name)
        if command is None:
            return cmd_name, args, None, BotResponse.error_response(
                f"unknowncommand: {cmd_name}\n"
                f"\u53d1\u9001 `{self.command_prefix}help` check\u770b\u53ef\u7528command."
            )

        if command.admin_only and not self.is_admin(message.user_id):
            return cmd_name, args, None, BotResponse.error_response("this command requires administrator permissions")

        error_msg = command.validate_args(args)
        if error_msg:
            return cmd_name, args, None, BotResponse.error_response(
                f"{error_msg}\nUsage: `{command.usage}`"
            )

        return cmd_name, args, command, None

    def _dispatch_sync(self, message: BotMessage) -> BotResponse:
        """Pure synchronous dispatch path for webhook/stream integrations."""
        cmd_name, args, command, early_response = self._prepare_dispatch(message)
        if early_response is not None:
            return early_response

        if cmd_name is None:
            nl_result = self._try_nl_routing_sync(message)
            if nl_result is not None:
                return nl_result
            if message.mentioned:
                return BotResponse.text_response(
                    "\u4f60\u597d！\u6211\u662f\u80a1\u7968analyze\u52a9\u624b.\n"
                    f"\u53d1\u9001 `{self.command_prefix}help` check\u770b\u53ef\u7528command."
                )
            return BotResponse.text_response("")

        if command is None:
            return BotResponse.error_response("command execution failed")

        try:
            response = command.execute(message, args)
            logger.info(f"[Dispatcher] command {cmd_name} executed successfully")
            return response
        except Exception as e:
            logger.error(f"[Dispatcher] command {cmd_name} execution failed: {e}")
            logger.exception(e)
            return BotResponse.error_response(f"command execution failed: {str(e)[:100]}")

    async def dispatch_async(self, message: BotMessage) -> BotResponse:
        """
        \u5f02\u6b65\u5206\u53d1\u6d88\u606f\u5230\u5bf9\u5e94command

        Args:
            message: \u6d88\u606f\u5bf9\u8c61

        Returns:
            \u54cd\u5e94\u5bf9\u8c61
        """
        cmd_name, args, command, early_response = self._prepare_dispatch(message)
        if early_response is not None:
            return early_response

        if cmd_name is None:
            # Not a command — try natural language routing before falling back
            nl_result = await self._try_nl_routing(message)
            if nl_result is not None:
                return nl_result
            # No NL match — check if @mentioned for a help hint
            if message.mentioned:
                return BotResponse.text_response(
                    "\u4f60\u597d！\u6211\u662f\u80a1\u7968analyze\u52a9\u624b.\n"
                    f"\u53d1\u9001 `{self.command_prefix}help` check\u770b\u53ef\u7528command."
                )
            # \u975ecommand\u6d88\u606f; \u4e0d\u5904\u7406
            return BotResponse.text_response("")

        if command is None:
            return BotResponse.error_response("command execution failed")

        # 6. \u6267\u884ccommand
        try:
            response = await command.execute_async(message, args)
            logger.info(f"[Dispatcher] command {cmd_name} executed successfully")
            return response
        except Exception as e:
            logger.error(f"[Dispatcher] command {cmd_name} execution failed: {e}")
            logger.exception(e)
            return BotResponse.error_response(f"command execution failed: {str(e)[:100]}")

    def set_help_command_getter(self, getter: Callable) -> None:
        """
        \u8bbe\u7f6ehelpcommand\u7684command\u5217\u8868\u83b7\u53d6\u5668

        \u7528\u4e8e\u8ba9 HelpCommand \u83b7\u53d6command\u5217\u8868.

        Args:
            getter: \u56de\u8c03\u51fd\u6570; \u8fd4\u56decommand\u5217\u8868
        """
        self._help_command_getter = getter

    # ------------------------------------------------------------------ #
    #  Natural language routing (LLM-based)                              #
    # ------------------------------------------------------------------ #

    # Lightweight intent-parsing prompt.  Asks the LLM to output a small
    # JSON object so we can route to the right command.
    _NL_PARSE_PROMPT = """\
You are a stock analysis assistant router.  Given a user's natural-language
message, determine whether it contains a stock-analysis request.

Return a JSON object (and NOTHING else) with these fields:
- "intent": one of "analysis", "chat", "none"
  * "analysis" → the user wants stock analysis / diagnosis / comparison
  * "chat" → the user is asking a general question related to finance
  * "none" → the message is irrelevant or you are unsure
- "codes": a list of stock codes mentioned (may be empty).
  Format: A-share 6-digit ("600519"), HK with prefix ("hk00700"), US ticker uppercase ("AAPL").
- "strategy": strategy/technique name if the user specified one, else null.
  e.g. "\u7f20\u8bba", "MACD", "\u8d8b\u52bf\u8ddf\u8e2a", "chan_theory", etc.

Examples:
User: "\u5e2e\u6211analyze\u4e00\u4e0b600519\u548c000858"
{"intent":"analysis","codes":["600519","000858"],"strategy":null}

User: "\u7528\u7f20\u8bba\u770b\u770bAAPL"
{"intent":"analysis","codes":["AAPL"],"strategy":"\u7f20\u8bba"}

User: "\u4eca\u5929\u5927\u76d8\u600e\u4e48\u6837"
{"intent":"chat","codes":[],"strategy":null}

User: "\u660e\u5929\u5929\u6c14\u5982\u4f55"
{"intent":"none","codes":[],"strategy":null}

User: "600519"
{"intent":"analysis","codes":["600519"],"strategy":null}

User: "\u5e2e\u6211analyze\u8305\u53f0"
{"intent":"analysis","codes":[],"strategy":null}

User: "analyze TSLA and NVDA using trend strategy"
{"intent":"analysis","codes":["TSLA","NVDA"],"strategy":"trend"}
"""

    # Cheap pre-filter: only invoke LLM when the message plausibly contains
    # stock-related content.  This regex checks for:
    #   - 6-digit A-share / BSE codes (0/3/6 and 43/83/87/88/92 prefixes)
    #   - HK codes like hk00700
    #   - 2-5 uppercase ASCII letters (US tickers)
    #   - Common finance/analysis keywords (Chinese and English)
    _NL_PREFILTER = re.compile(
        r'(?:[036]\d{5}|(?:43|83|87|88|92)\d{4})'  # A-share / BSE 6-digit codes
        r'|(?:hk|HK)\d{5}'                    # HK code
        r'|(?<![a-zA-Z])[A-Z]{2,5}(?![a-zA-Z])'  # US ticker — UPPERCASE only, no IGNORECASE
        r'|analyze|\u770b\u770b|check\u4e00?\u4e0b|\u7814\u7a76|\u8bca\u65ad|\u600e\u4e48\u6837|\u8d70\u52bf|\u8d8b\u52bf'
        r'|\u80fd\u4e70|\u53ef\u4ee5\u4e70|\u6da8\u8fd8\u662f\u8dcc|\u600e\u4e48\u770b|\u80fd\u8ffd|\u5efa\u8bae|\u76ee\u6807\u4ef7'
        r'|\u652f\u6491|\u538b\u529b|\u963b\u529b|\u6b62\u635f|\u4e70\u70b9|\u5356\u70b9|\u6280\u672f\u9762|fundamentals|\u7b79\u7801'
        r'|(?i:analyz|stock|buy|sell|trend|backtest|strateg)',
    )

    _NL_NAME_CLEANUP_PATTERNS = (
        r'[; ,..!！?？:: ;；`\'"“”‘’ ()()\[\]{}<>]+',
        r'(?i:\b(?:please|analy[sz]e|analysis|research|check|look\s+at|stock|ticker|trend|price)\b)',
        r'(?:\u5e2e\u6211|\u5e2e\u5fd9|\u9ebb\u70e6|\u8bf7|\u60f3\u8bf7\u4f60|\u6211\u60f3|\u60f3|\u7528|\u6309\u7167|\u57fa\u4e8e|\u5173\u4e8e|\u5bf9)\s*',
        r'(?:analyze|\u770b\u770b|\u7814\u7a76|\u8bca\u65ad|check\u4e00?\u4e0b|\u804a\u804a|\u8bf4\u8bf4|askask|\u8bc4\u4f30)\s*',
        r'(?:\u6700\u8fd1|\u8fd1\u671f|\u5f53\u524d|\u4eca\u5929|\u8fd9\u53ea|\u8fd9\u4e2a|individual stocks|\u80a1\u7968)\s*',
        r'(?:\u8d70\u52bf|\u60c5\u51b5|\u8868\u73b0|\u5982\u4f55|\u600e\u4e48\u6837|\u600e\u4e48\u770b|\u53ef\u4ee5\u5417|\u80fd\u4e70\u5417|\u503c\u4e0d\u503c\u5f97\u4e70|\u6280\u672f\u9762|fundamentals|strategy)\s*',
        r'\s+',
    )

    @classmethod
    def _passes_nl_prefilter(cls, text: str) -> bool:
        """Return whether the message is worth the LLM intent-routing cost."""
        if cls._NL_PREFILTER.search(text):
            return True

        stripped = (text or "").strip()
        if " " in stripped or len(stripped) > 10:
            return False

        from src.agent.orchestrator import _extract_stock_code

        return bool(_extract_stock_code(stripped))

    async def _try_nl_routing(self, message: BotMessage) -> Optional[BotResponse]:
        """Route a non-command message to the appropriate command via LLM intent parsing.

        Two-layer approach to balance cost and accuracy:
        1. **Cheap regex pre-filter**: skip messages that clearly have no stock
           or finance content (avoids LLM cost for irrelevant messages).
        2. **LLM intent parsing**: extract intent, stock codes, and strategy
           from the user text with full multilingual support.

        Only activates when:
        - ``AGENT_NL_ROUTING=true`` in config, **and**
        - the message is in a private chat, **or** the bot was @mentioned.

        Returns ``BotResponse`` if a route was found, ``None`` otherwise.
        """
        from src.config import get_config
        config = get_config()

        if not getattr(config, 'agent_nl_routing', False):
            return None

        # Only handle private chat or @mentioned messages to avoid hijacking
        is_private = message.chat_type.value == "private"
        if not is_private and not message.mentioned:
            return None

        # Keep Bot-side Agent entrypoints behind explicit opt-in so NL routing
        # cannot bypass AGENT_MODE=false.
        if not getattr(config, 'agent_mode', False):
            return None

        text = message.content.strip()
        if not text or len(text) > 500:
            return None

        # Layer 1: cheap pre-filter — skip obviously irrelevant messages
        if not self._passes_nl_prefilter(text):
            return None

        # Layer 2: LLM intent parsing — extract codes, intent, strategy
        parsed = await self._parse_intent_via_llm(text, config)
        if parsed is None:
            return None

        intent = parsed.get("intent", "none")
        codes = parsed.get("codes") or []
        strategy = parsed.get("strategy")

        if intent == "none":
            return None

        if intent == "analysis" and not codes:
            resolved_code = self._resolve_stock_code_from_text(text)
            if resolved_code:
                codes = [resolved_code]

        # "chat" intent → route to /chat with original text
        if intent == "chat":
            chat_cmd = self.get_command("chat")
            if chat_cmd:
                logger.info("[Dispatcher] NL routing → /chat: %s", text[:60])
                return await chat_cmd.execute_async(message, [text])
            return None

        # "analysis" intent → route to /ask
        if intent == "analysis" and codes:
            ask_cmd = self.get_command("ask")
            if not ask_cmd:
                return None

            # Build args: "code1,code2 [strategy]"
            code_str = ",".join(codes[:5])  # cap at 5
            args = [code_str]
            if strategy:
                args.append(strategy)

            logger.info(
                "[Dispatcher] NL routing → /ask %s (strategy=%s, text=%s)",
                code_str, strategy, text[:60],
            )
            return await ask_cmd.execute_async(message, args)

        return None

    def _try_nl_routing_sync(self, message: BotMessage) -> Optional[BotResponse]:
        """Synchronous companion to `_try_nl_routing` for legacy call sites."""
        from src.config import get_config

        config = get_config()
        if not getattr(config, 'agent_nl_routing', False):
            return None

        is_private = message.chat_type.value == "private"
        if not is_private and not message.mentioned:
            return None

        if not getattr(config, 'agent_mode', False):
            return None

        text = message.content.strip()
        if not text or len(text) > 500:
            return None

        if not self._passes_nl_prefilter(text):
            return None

        parsed = self._parse_intent_via_llm_sync(text, config)
        if parsed is None:
            return None

        intent = parsed.get("intent", "none")
        codes = parsed.get("codes") or []
        strategy = parsed.get("strategy")

        if intent == "none":
            return None

        if intent == "analysis" and not codes:
            resolved_code = self._resolve_stock_code_from_text(text)
            if resolved_code:
                codes = [resolved_code]

        if intent == "chat":
            chat_cmd = self.get_command("chat")
            if chat_cmd:
                logger.info("[Dispatcher] NL routing → /chat: %s", text[:60])
                return chat_cmd.execute(message, [text])
            return None

        if intent == "analysis" and codes:
            ask_cmd = self.get_command("ask")
            if not ask_cmd:
                return None

            code_str = ",".join(codes[:5])
            args = [code_str]
            if strategy:
                args.append(strategy)

            logger.info(
                "[Dispatcher] NL routing → /ask %s (strategy=%s, text=%s)",
                code_str, strategy, text[:60],
            )
            return ask_cmd.execute(message, args)

        return None

    @staticmethod
    async def _parse_intent_via_llm(text: str, config) -> Optional[dict]:
        """Call LLM to parse user intent.  Returns parsed dict or None on failure."""
        try:
            from src.agent.llm_adapter import LLMToolAdapter

            messages = [
                {"role": "system", "content": CommandDispatcher._NL_PARSE_PROMPT},
                {"role": "user", "content": text},
            ]
            adapter = LLMToolAdapter(config)
            resp = await asyncio.to_thread(
                adapter.call_text,
                messages,
                temperature=0,
                max_tokens=200,
                timeout=10,
            )
            return CommandDispatcher._parse_intent_payload(resp.content or "")
        except Exception as exc:
            logger.debug("[Dispatcher] NL parse LLM call failed: %s", exc)
            return None

    @staticmethod
    def _parse_intent_via_llm_sync(text: str, config) -> Optional[dict]:
        """Synchronous variant for webhook/stream integrations."""
        try:
            from src.agent.llm_adapter import LLMToolAdapter

            messages = [
                {"role": "system", "content": CommandDispatcher._NL_PARSE_PROMPT},
                {"role": "user", "content": text},
            ]
            adapter = LLMToolAdapter(config)
            resp = adapter.call_text(
                messages,
                temperature=0,
                max_tokens=200,
                timeout=10,
            )
            return CommandDispatcher._parse_intent_payload(resp.content or "")
        except Exception as exc:
            logger.debug("[Dispatcher] NL parse LLM call failed: %s", exc)
            return None

    @staticmethod
    def _parse_intent_payload(raw: str) -> Optional[dict]:
        """Parse the JSON payload returned by the intent-routing LLM call."""
        import json as _json

        cleaned = (raw or "").strip()
        if not cleaned:
            return None

        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            result = _json.loads(cleaned)
        except _json.JSONDecodeError:
            logger.debug("[Dispatcher] NL parse: invalid JSON from LLM: %s", cleaned[:200])
            return None

        if isinstance(result, dict) and "intent" in result:
            return result

        logger.debug("[Dispatcher] NL parse: unexpected structure: %s", cleaned[:200])
        return None

    @classmethod
    def _resolve_stock_code_from_text(cls, text: str) -> Optional[str]:
        """Best-effort stock name/code resolution for NL-routed analysis requests."""
        from data_provider.base import canonical_stock_code
        from src.data.stock_mapping import STOCK_NAME_MAP
        from src.services.name_to_code_resolver import resolve_name_to_code

        def _iter_candidates(raw_text: str) -> List[str]:
            candidates: List[str] = []
            stripped = (raw_text or "").strip()
            if stripped:
                candidates.append(stripped)

            cleaned = stripped
            for pattern in cls._NL_NAME_CLEANUP_PATTERNS:
                cleaned = re.sub(pattern, " ", cleaned)
            cleaned = cleaned.strip(" \u7684").strip()
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

            for source in list(candidates):
                for token in re.findall(r'[A-Za-z][A-Za-z0-9\.]{0,9}|[\u4e00-\u9fff]{2,12}', source):
                    normalized = token.strip(" \u7684").strip()
                    if normalized and normalized not in candidates:
                        candidates.append(normalized)

            return sorted(candidates, key=len, reverse=True)

        def _unique_partial_match(candidate: str) -> Optional[str]:
            if not re.search(r'[\u4e00-\u9fff]', candidate):
                return None
            matches = [
                code for code, stock_name in STOCK_NAME_MAP.items()
                if candidate and candidate in stock_name
            ]
            unique_matches = list(dict.fromkeys(matches))
            if len(unique_matches) == 1:
                return canonical_stock_code(unique_matches[0])
            return None

        candidates = _iter_candidates(text)

        # Prefer deterministic local alias/partial-name matches before any
        # resolver path that may touch online market data providers.
        for candidate in candidates:
            partial = _unique_partial_match(candidate)
            if partial:
                return partial

        for candidate in candidates:
            resolved = resolve_name_to_code(candidate)
            if resolved:
                return canonical_stock_code(resolved)

        return None


# \u5168\u5c40\u5206\u53d1\u5668\u5b9e\u4f8b
_dispatcher: Optional[CommandDispatcher] = None


def get_dispatcher() -> CommandDispatcher:
    """
    \u83b7\u53d6\u5168\u5c40\u5206\u53d1\u5668\u5b9e\u4f8b

    \u4f7f\u7528\u5355\u4f8bmode; \u9996\u6b21\u8c03\u7528\u65f6\u81ea\u52a8\u521d\u59cb\u5316\u5e76\u6ce8\u518c\u6240\u6709command.
    """
    global _dispatcher

    if _dispatcher is None:
        from src.config import get_config

        config = get_config()

        # \u521b\u5efa\u5206\u53d1\u5668
        _dispatcher = CommandDispatcher(
            command_prefix=getattr(config, 'bot_command_prefix', '/'),
            rate_limit_requests=getattr(config, 'bot_rate_limit_requests', 10),
            rate_limit_window=getattr(config, 'bot_rate_limit_window', 60),
            admin_users=getattr(config, 'bot_admin_users', []),
        )

        # \u81ea\u52a8\u6ce8\u518c\u6240\u6709command
        from bot.commands import ALL_COMMANDS
        for command_class in ALL_COMMANDS:
            _dispatcher.register_class(command_class)

        logger.info(f"[Dispatcher] initialization complete; registered {len(_dispatcher._commands)} \u4e2acommand")

    return _dispatcher


def reset_dispatcher() -> None:
    """\u91cd\u7f6e\u5168\u5c40\u5206\u53d1\u5668 (\u4e3b\u8981\u7528\u4e8e\u6d4b\u8bd5)"""
    global _dispatcher
    _dispatcher = None
