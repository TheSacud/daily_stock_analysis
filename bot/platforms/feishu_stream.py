# -*- coding: utf-8 -*-
"""
===================================
Feishu Stream mode\u9002\u914d\u5668
===================================

\u4f7f\u7528Feishu\u5b98\u65b9 lark-oapi SDK \u7684 WebSocket \u957f\u8fde\u63a5mode\u63a5\u5165\u673a\u5668\u4eba;
\u65e0\u9700\u516c\u7f51 IP \u548c Webhook config.

\u4f18\u52bf:
- \u4e0d\u9700\u8981\u516c\u7f51 IP or\u57df\u540d
- \u4e0d\u9700\u8981config Webhook URL
- \u901a\u8fc7 WebSocket \u957f\u8fde\u63a5\u63a5\u6536\u6d88\u606f
- \u66f4\u7b80\u5355\u7684\u63a5\u5165\u65b9\u5f0f
- \u5185\u7f6e\u81ea\u52a8\u91cd\u8fde\u548c\u5fc3\u8df3\u4fdd\u6d3b

\u4f9d\u8d56:
pip install lark-oapi

Feishu\u957f\u8fde\u63a5docs:
https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/handle-events
"""

import json
import logging
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Callable
import time

logger = logging.getLogger(__name__)

# \u5c1d\u8bd5\u5bfc\u5165Feishu SDK
try:
    import lark_oapi as lark
    from lark_oapi import ws
    from lark_oapi.api.im.v1 import (
        P2ImMessageReceiveV1,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
    )

    FEISHU_SDK_AVAILABLE = True
except ImportError:
    FEISHU_SDK_AVAILABLE = False
    logger.warning("[Feishu Stream] lark-oapi SDK is not installed; Stream modeunavailable")
    logger.warning("[Feishu Stream] please run: pip install lark-oapi")

from bot.models import BotMessage, BotResponse, ChatType
from src.formatters import format_feishu_markdown, chunk_content_by_max_bytes
from src.config import get_config


class FeishuReplyClient:
    """
    Feishu\u6d88\u606f\u56de\u590d\u5ba2\u6237\u7aef

    \u4f7f\u7528Feishu API \u53d1\u9001\u56de\u590d\u6d88\u606f.
    """

    def __init__(self, app_id: str, app_secret: str):
        """
        Args:
            app_id: Feishu\u5e94\u7528 ID
            app_secret: Feishu\u5e94\u7528\u5bc6\u94a5
        """
        if not FEISHU_SDK_AVAILABLE:
            raise ImportError("lark-oapi SDK is not installed")

        self._client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.WARNING) \
            .build()

        # \u83b7\u53d6config\u7684\u6700\u5927\u5b57\u8282\u6570
        config = get_config()
        self._max_bytes = getattr(config, 'feishu_max_bytes', 20000)

    def _send_interactive_card(self, content: str, message_id: Optional[str] = None,
                               chat_id: Optional[str] = None,
                               receive_id_type: str = "chat_id",
                               at_user: bool = False, user_id: Optional[str] = None) -> bool:
        """
        \u53d1\u9001\u4ea4\u4e92\u5361\u7247\u6d88\u606f (\u652f\u6301 Markdown \u6e32\u67d3)

        Args:
            content: Markdown \u683c\u5f0f\u7684\u5185\u5bb9
            message_id: \u539f\u6d88\u606f ID (\u56de\u590d\u65f6\u4f7f\u7528)
            chat_id: conversation ID (\u4e3b\u52a8\u53d1\u9001\u65f6\u4f7f\u7528)
            receive_id_type: \u63a5\u6536\u8005 ID \u7c7b\u578b
            at_user: \u662f\u5426 @user
            user_id: user open_id (at_user=True \u65f6\u9700\u8981)

        Returns:
            \u662f\u5426send succeeded
        """
        try:
            # \u5982\u679c\u9700\u8981 @user; \u5728\u5185\u5bb9\u524d\u6dfb\u52a0 @ \u6807\u8bb0
            final_content = content
            if at_user and user_id:
                final_content = f"<at user_id=\"{user_id}\"></at> {content}"

            # \u6784\u5efa\u4ea4\u4e92\u5361\u7247 payload
            card_data = {
                "config": {"wide_screen_mode": True},
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": final_content
                        }
                    }
                ]
            }

            content_json = json.dumps(card_data)

            if message_id:
                # \u56de\u590d\u6d88\u606f
                request = ReplyMessageRequest.builder() \
                    .message_id(message_id) \
                    .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content_json)
                    .msg_type("interactive")
                    .build()
                ) \
                    .build()
                response = self._client.im.v1.message.reply(request)
            else:
                # \u4e3b\u52a8\u53d1\u9001\u6d88\u606f
                request = CreateMessageRequest.builder() \
                    .receive_id_type(receive_id_type) \
                    .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .content(content_json)
                    .msg_type("interactive")
                    .build()
                ) \
                    .build()
                response = self._client.im.v1.message.create(request)

            if not response.success():
                logger.error(
                    f"[Feishu Stream] \u53d1\u9001\u4ea4\u4e92\u5361\u7247failed: code={response.code}, "
                    f"msg={response.msg}, log_id={response.get_log_id()}"
                )
                return False

            logger.debug("[Feishu Stream] interactive card sent successfully")
            return True

        except Exception as e:
            logger.error(f"[Feishu Stream] interactive card send exception: {e}")
            return False

    def reply_text(self, message_id: str, text: str, at_user: bool = False,
                   user_id: Optional[str] = None) -> bool:
        """
        \u56de\u590d\u6587\u672c\u6d88\u606f (\u652f\u6301\u4ea4\u4e92\u5361\u7247\u548c\u5206\u6bb5\u53d1\u9001)

        Args:
            message_id: \u539f\u6d88\u606f ID
            text: \u56de\u590d\u6587\u672c
            at_user: \u662f\u5426 @user
            user_id: user open_id (at_user=True \u65f6\u9700\u8981)

        Returns:
            \u662f\u5426send succeeded
        """
        # \u5c06\u6587\u672c\u8f6c\u6362\u4e3aFeishu Markdown \u683c\u5f0f
        formatted_text = format_feishu_markdown(text)

        # \u68c0check\u662f\u5426\u9700\u8981\u5206\u6bb5\u53d1\u9001
        content_bytes = len(formatted_text.encode('utf-8'))
        if content_bytes > self._max_bytes:
            logger.info(
                f"[Feishu Stream] \u56de\u590d\u6d88\u606f\u5185\u5bb9\u8d85\u957f({content_bytes}\u5b57\u8282); \u5c06\u5206\u6279\u53d1\u9001"
            )
            return self._send_to_chat_chunked(
                formatted_text,
                lambda chunk: self._send_interactive_card(
                    chunk,
                    message_id=message_id,
                    at_user=at_user,
                    user_id=user_id,
                ),
            )

        # \u5355\u6761\u6d88\u606f; \u4f7f\u7528\u4ea4\u4e92\u5361\u7247
        return self._send_interactive_card(
            formatted_text, message_id=message_id, at_user=at_user, user_id=user_id
        )

    def send_to_chat(self, chat_id: str, text: str,
                     receive_id_type: str = "chat_id") -> bool:
        """
        \u53d1\u9001\u6d88\u606f\u5230\u6307\u5b9aconversation (\u652f\u6301\u4ea4\u4e92\u5361\u7247\u548c\u5206\u6bb5\u53d1\u9001)

        Args:
            chat_id: conversation ID
            text: \u6d88\u606f\u6587\u672c
            receive_id_type: \u63a5\u6536\u8005 ID \u7c7b\u578b; default chat_id

        Returns:
            \u662f\u5426send succeeded
        """
        # \u5c06\u6587\u672c\u8f6c\u6362\u4e3aFeishu Markdown \u683c\u5f0f
        formatted_text = format_feishu_markdown(text)

        # \u68c0check\u662f\u5426\u9700\u8981\u5206\u6bb5\u53d1\u9001
        content_bytes = len(formatted_text.encode('utf-8'))
        if content_bytes > self._max_bytes:
            logger.info(
                f"[Feishu Stream] \u53d1\u9001\u6d88\u606f\u5185\u5bb9\u8d85\u957f({content_bytes}\u5b57\u8282); \u5c06\u5206\u6279\u53d1\u9001"
            )
            return self._send_to_chat_chunked(
                formatted_text,
                lambda chunk: self._send_interactive_card(
                    chunk,
                    chat_id=chat_id,
                    receive_id_type=receive_id_type,
                ),
            )

        # \u5355\u6761\u6d88\u606f; \u4f7f\u7528\u4ea4\u4e92\u5361\u7247
        return self._send_interactive_card(formatted_text, chat_id=chat_id, receive_id_type=receive_id_type)

    def _send_to_chat_chunked(self, content: str, send_func: Callable[[str], bool]) -> bool:
        """
        \u5206\u6279\u53d1\u9001\u6d88\u606f (\u652f\u6301\u4ea4\u4e92\u5361\u7247\u548c\u5206\u6bb5\u53d1\u9001)

        Args:
            content: \u6d88\u606f\u6587\u672c
            send_func: \u53d1\u9001\u5355\u4e2a\u5206\u7247\u7684\u51fd\u6570; \u8fd4\u56de\u662f\u5426send succeeded

        Returns:
            \u662f\u5426allsend succeeded
        """
        chunks = chunk_content_by_max_bytes(content, self._max_bytes, add_page_marker=True)
        success_count = 0
        for i, chunk in enumerate(chunks):
            if send_func(chunk):
                success_count += 1
            else:
                logger.error(f"[Feishu Stream] message send failed: {chunk}")
            if i < len(chunks) - 1:
                time.sleep(1)
        return success_count == len(chunks)


class FeishuStreamHandler:
    """
    Feishu Stream mode\u6d88\u606f\u5904\u7406\u5668

    \u5c06 SDK \u7684\u4e8b\u4ef6\u8f6c\u6362\u4e3a\u7edf\u4e00\u7684 BotMessage \u683c\u5f0f;
    \u5e76\u8c03\u7528command\u5206\u53d1\u5668\u5904\u7406.
    """

    def __init__(
            self,
            on_message: Callable[[BotMessage], BotResponse],
            reply_client: FeishuReplyClient
    ):
        """
        Args:
            on_message: \u6d88\u606f\u5904\u7406\u56de\u8c03\u51fd\u6570; \u63a5\u6536 BotMessage \u8fd4\u56de BotResponse
            reply_client: Feishu\u56de\u590d\u5ba2\u6237\u7aef
        """
        self._on_message = on_message
        self._reply_client = reply_client
        self._logger = logger
        # Different conversations can run in parallel, but one conversation
        # must stay FIFO so multi-turn chat and replies do not get reordered.
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="feishu-msg")
        self._pending_messages: dict[str, deque[BotMessage]] = {}
        self._active_conversations: set[str] = set()
        self._queue_lock = threading.Lock()
        self._shutdown = False

    def _conversation_key(self, bot_message: BotMessage) -> str:
        """Return the ordering key used for per-conversation FIFO processing."""
        if bot_message.chat_type == ChatType.PRIVATE:
            return bot_message.chat_id or bot_message.user_id or bot_message.message_id

        chat_id = bot_message.chat_id or "unknown-chat"
        user_id = bot_message.user_id or "unknown-user"
        return f"{chat_id}:{user_id}"

    def _enqueue_message(self, bot_message: BotMessage) -> None:
        """Queue a message and start a worker when its conversation is idle."""
        if self._shutdown:
            self._logger.debug("[Feishu Stream] Handler already stopped, dropping message")
            return

        conversation_key = self._conversation_key(bot_message)
        should_start_worker = False

        with self._queue_lock:
            self._pending_messages.setdefault(conversation_key, deque()).append(bot_message)
            if conversation_key not in self._active_conversations:
                self._active_conversations.add(conversation_key)
                should_start_worker = True

        if should_start_worker:
            try:
                self._executor.submit(self._drain_conversation, conversation_key)
            except RuntimeError as exc:
                with self._queue_lock:
                    self._active_conversations.discard(conversation_key)
                    self._pending_messages.pop(conversation_key, None)
                self._logger.error("[Feishu Stream] unable to start message processing thread: %s", exc)

    def _drain_conversation(self, conversation_key: str) -> None:
        """Drain one conversation queue in FIFO order."""
        while True:
            with self._queue_lock:
                queue = self._pending_messages.get(conversation_key)
                if not queue:
                    self._pending_messages.pop(conversation_key, None)
                    self._active_conversations.discard(conversation_key)
                    return
                bot_message = queue.popleft()

            self._process_message(bot_message)

    def _process_message(self, bot_message: BotMessage) -> None:
        """Execute command handling off the SDK callback thread."""
        try:
            response = self._on_message(bot_message)

            if response and response.text:
                self._reply_client.reply_text(
                    message_id=bot_message.message_id,
                    text=response.text,
                    at_user=response.at_user,
                    user_id=bot_message.user_id if response.at_user else None,
                )
        except Exception as e:
            self._logger.error(f"[Feishu Stream] async message handling failed: {e}")
            self._logger.exception(e)

    @staticmethod
    def _truncate_log_content(text: str, max_len: int = 200) -> str:
        """\u622a\u65adlog\u5185\u5bb9"""
        cleaned = text.replace("\n", " ").strip()
        if len(cleaned) > max_len:
            return f"{cleaned[:max_len]}..."
        return cleaned

    def _log_incoming_message(self, message: BotMessage) -> None:
        """\u8bb0\u5f55received\u7684\u6d88\u606flog"""
        content = message.raw_content or message.content or ""
        summary = self._truncate_log_content(content)
        self._logger.info(
            "[Feishu Stream] Incoming message: msg_id=%s user_id=%s "
            "chat_id=%s chat_type=%s content=%s",
            message.message_id,
            message.user_id,
            message.chat_id,
            getattr(message.chat_type, "value", message.chat_type),
            summary,
        )

    def handle_message(self, event: 'P2ImMessageReceiveV1') -> None:
        """
        \u5904\u7406\u63a5received\u7684\u6d88\u606f\u4e8b\u4ef6

        Args:
            event: Feishu\u6d88\u606f\u63a5\u6536\u4e8b\u4ef6
        """
        try:
            # \u89e3\u6790\u6d88\u606f
            bot_message = self._parse_event_message(event)

            if bot_message is None:
                return

            self._log_incoming_message(bot_message)

            self._enqueue_message(bot_message)

        except Exception as e:
            self._logger.error(f"[Feishu Stream] message handling failed: {e}")
            self._logger.exception(e)

    def _parse_event_message(self, event: 'P2ImMessageReceiveV1') -> Optional[BotMessage]:
        """
        \u89e3\u6790Feishu\u4e8b\u4ef6\u6d88\u606f\u4e3a\u7edf\u4e00\u683c\u5f0f

        Args:
            event: P2ImMessageReceiveV1 \u4e8b\u4ef6\u5bf9\u8c61
        """
        try:
            event_data = event.event
            if event_data is None:
                return None

            message_data = event_data.message
            sender_data = event_data.sender

            if message_data is None:
                return None

            # \u53ea\u5904\u7406\u6587\u672c\u6d88\u606f
            message_type = message_data.message_type or ""
            if message_type != "text":
                self._logger.debug(f"[Feishu Stream] ignored non-text message: {message_type}")
                return None

            # \u89e3\u6790\u6d88\u606f\u5185\u5bb9
            content_str = message_data.content or "{}"
            try:
                content_json = json.loads(content_str)
                raw_content = content_json.get("text", "")
            except json.JSONDecodeError:
                raw_content = content_str

            # \u63d0\u53d6command (\u53bb\u9664 @\u673a\u5668\u4eba)
            content = self._extract_command(raw_content, message_data.mentions)
            mentioned = "@" in raw_content or bool(message_data.mentions)

            # \u83b7\u53d6\u53d1\u9001\u8005info
            user_id = ""
            if sender_data and sender_data.sender_id:
                user_id = sender_data.sender_id.open_id or sender_data.sender_id.user_id or ""

            # \u83b7\u53d6conversation\u7c7b\u578b
            chat_type_str = message_data.chat_type or ""
            if chat_type_str == "group":
                chat_type = ChatType.GROUP
            elif chat_type_str == "p2p":
                chat_type = ChatType.PRIVATE
            else:
                chat_type = ChatType.UNKNOWN

            # \u521b\u5efa\u65f6\u95f4
            create_time = message_data.create_time
            try:
                if create_time:
                    timestamp = datetime.fromtimestamp(int(create_time) / 1000)
                else:
                    timestamp = datetime.now()
            except (ValueError, TypeError):
                timestamp = datetime.now()

            # \u6784\u5efa\u539f\u59cb\u6570\u636e
            raw_data = {
                "header": {
                    "event_id": event.header.event_id if event.header else "",
                    "event_type": event.header.event_type if event.header else "",
                    "create_time": event.header.create_time if event.header else "",
                    "token": event.header.token if event.header else "",
                    "app_id": event.header.app_id if event.header else "",
                },
                "event": {
                    "message_id": message_data.message_id,
                    "chat_id": message_data.chat_id,
                    "chat_type": message_data.chat_type,
                    "content": message_data.content,
                }
            }

            return BotMessage(
                platform="feishu",
                message_id=message_data.message_id or "",
                user_id=user_id,
                user_name=user_id,  # Feishu\u4e0d\u76f4\u63a5\u8fd4\u56deuser\u540d
                chat_id=message_data.chat_id or "",
                chat_type=chat_type,
                content=content,
                raw_content=raw_content,
                mentioned=mentioned,
                mentions=[m.key or "" for m in (message_data.mentions or [])],
                timestamp=timestamp,
                raw_data=raw_data,
            )

        except Exception as e:
            self._logger.error(f"[Feishu Stream] message parse failed: {e}")
            return None

    def _extract_command(self, text: str, mentions: list) -> str:
        """
        \u63d0\u53d6command\u5185\u5bb9 (\u53bb\u9664 @\u673a\u5668\u4eba)

        Feishu\u7684 @user \u683c\u5f0f\u662f: @_user_1, @_user_2 \u7b49

        Args:
            text: \u539f\u59cb\u6d88\u606f\u6587\u672c
            mentions: @\u63d0\u53ca\u5217\u8868
        """
        import re

        # \u65b9\u5f0f1: \u901a\u8fc7 mentions \u5217\u8868\u79fb\u9664 (\u7cbe\u786e\u5339\u914d)
        for mention in (mentions or []):
            key = getattr(mention, 'key', '') or ''
            if key:
                text = text.replace(key, '')

        # \u65b9\u5f0f2: \u6b63\u5219\u515c\u5e95; \u79fb\u9664Feishu @user \u683c\u5f0f (@_user_N)
        # \u5f53 mentions \u4e3a\u7a7aor\u672a\u6b63\u786e\u4f20\u9012\u65f6\u751f\u6548
        text = re.sub(r'@_user_\d+\s*', '', text)

        # \u6e05\u7406\u591a\u4f59\u7a7a\u683c
        return ' '.join(text.split())

    def shutdown(self, wait: bool = False) -> None:
        """Stop accepting new messages and tear down worker threads."""
        self._shutdown = True
        with self._queue_lock:
            self._pending_messages.clear()
            self._active_conversations.clear()
        self._executor.shutdown(wait=wait)


class FeishuStreamClient:
    """
    Feishu Stream mode\u5ba2\u6237\u7aef

    \u5c01\u88c5 lark-oapi SDK \u7684 WebSocket \u5ba2\u6237\u7aef; \u63d0\u4f9b\u7b80\u5355\u7684started\u63a5\u53e3.

    \u4f7f\u7528\u65b9\u5f0f:
        client = FeishuStreamClient()
        client.start()  # \u963b\u585e\u8fd0\u884c

        # or\u8005\u5728\u540e\u53f0\u8fd0\u884c
        client.start_background()
    """

    def __init__(
            self,
            app_id: Optional[str] = None,
            app_secret: Optional[str] = None
    ):
        """
        Args:
            app_id: \u5e94\u7528 ID (\u4e0d\u4f20\u5219\u4ececonfig\u8bfb\u53d6)
            app_secret: \u5e94\u7528\u5bc6\u94a5 (\u4e0d\u4f20\u5219\u4ececonfig\u8bfb\u53d6)
        """
        if not FEISHU_SDK_AVAILABLE:
            raise ImportError(
                "lark-oapi SDK is not installed.\n"
                "please run: pip install lark-oapi"
            )

        from src.config import get_config
        config = get_config()

        self._app_id = app_id or getattr(config, 'feishu_app_id', None)
        self._app_secret = app_secret or getattr(config, 'feishu_app_secret', None)

        if not self._app_id or not self._app_secret:
            raise ValueError(
                "Feishu Stream mode\u9700\u8981config FEISHU_APP_ID \u548c FEISHU_APP_SECRET"
            )

        self._ws_client: Optional[ws.Client] = None
        self._reply_client: Optional[FeishuReplyClient] = None
        self._message_handler: Optional[FeishuStreamHandler] = None
        self._background_thread: Optional[threading.Thread] = None
        self._running = False

    def _create_message_handler(self) -> Callable[[BotMessage], BotResponse]:
        """\u521b\u5efa\u6d88\u606f\u5904\u7406\u51fd\u6570"""

        def handle_message(message: BotMessage) -> BotResponse:
            from bot.dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            return dispatcher.dispatch(message)

        return handle_message

    def _create_event_handler(self) -> 'lark.EventDispatcherHandler':
        """\u521b\u5efa\u4e8b\u4ef6\u5206\u53d1\u5904\u7406\u5668"""
        # \u521b\u5efa\u56de\u590d\u5ba2\u6237\u7aef
        self._reply_client = FeishuReplyClient(self._app_id, self._app_secret)

        # \u521b\u5efa\u6d88\u606f\u5904\u7406\u5668
        handler = FeishuStreamHandler(
            self._create_message_handler(),
            self._reply_client
        )
        self._message_handler = handler

        # \u521b\u5efa\u5e76\u6ce8\u518c\u4e8b\u4ef6\u5904\u7406\u5668
        # \u6ce8\u610f: encrypt_key \u548c verification_token \u5728\u957f\u8fde\u63a5mode\u4e0b\u4e0d\u662f\u5fc5\u9700\u7684
        # \u4f46 SDK \u8981\u6c42\u4f20\u5165 (\u53ef\u4ee5\u4e3a\u7a7a\u5b57\u7b26\u4e32)
        from src.config import get_config
        config = get_config()

        encrypt_key = getattr(config, 'feishu_encrypt_key', '') or ''
        verification_token = getattr(config, 'feishu_verification_token', '') or ''

        event_handler = lark.EventDispatcherHandler.builder(
            encrypt_key=encrypt_key,
            verification_token=verification_token,
            level=lark.LogLevel.WARNING
        ).register_p2_im_message_receive_v1(
            handler.handle_message
        ).build()

        return event_handler

    def start(self) -> None:
        """
        started Stream \u5ba2\u6237\u7aef (\u963b\u585e)

        \u6b64\u65b9\u6cd5\u4f1a\u963b\u585e\u5f53\u524d\u7ebf\u7a0b; \u76f4\u5230\u5ba2\u6237\u7aef\u505c\u6b62.
        """
        logger.info("[Feishu Stream] starting...")

        # \u521b\u5efa\u4e8b\u4ef6\u5904\u7406\u5668
        event_handler = self._create_event_handler()

        # \u521b\u5efa WebSocket \u5ba2\u6237\u7aef
        self._ws_client = ws.Client(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.WARNING,
            auto_reconnect=True
        )

        self._running = True
        logger.info("[Feishu Stream] client started; waiting for messages...")

        # started (\u963b\u585e)
        self._ws_client.start()

    def start_background(self) -> None:
        """
        \u5728\u540e\u53f0\u7ebf\u7a0bstarted Stream \u5ba2\u6237\u7aef (\u975e\u963b\u585e)

        \u9002\u7528\u4e8e\u4e0eother\u670d\u52a1 (\u5982 WebUI)\u540c\u65f6\u8fd0\u884c\u7684\u573a\u666f.
        """
        if self._background_thread and self._background_thread.is_alive():
            logger.warning("[Feishu Stream] client is already running")
            return

        self._running = True
        self._background_thread = threading.Thread(
            target=self._run_in_background,
            daemon=True,
            name="FeishuStreamClient"
        )
        self._background_thread.start()
        logger.info("[Feishu Stream] \u540e\u53f0client started")

    def _run_in_background(self) -> None:
        """\u540e\u53f0\u8fd0\u884c (\u5904\u7406\u5f02\u5e38\u548c\u91cd\u8fde)"""
        import time

        while self._running:
            try:
                self.start()
            except Exception as e:
                logger.error(f"[Feishu Stream] runtime exception: {e}")
                if self._running:
                    logger.info("[Feishu Stream] reconnecting in 5 seconds...")
                    time.sleep(5)

    def stop(self) -> None:
        """\u505c\u6b62\u5ba2\u6237\u7aef"""
        self._running = False
        if self._message_handler is not None:
            self._message_handler.shutdown(wait=False)
        logger.info("[Feishu Stream] client stopped")

    @property
    def is_running(self) -> bool:
        """\u662f\u5426\u6b63\u5728\u8fd0\u884c"""
        return self._running


# \u5168\u5c40\u5ba2\u6237\u7aef\u5b9e\u4f8b
_stream_client: Optional[FeishuStreamClient] = None


def get_feishu_stream_client() -> Optional[FeishuStreamClient]:
    """\u83b7\u53d6\u5168\u5c40 Stream \u5ba2\u6237\u7aef\u5b9e\u4f8b"""
    global _stream_client

    if _stream_client is None and FEISHU_SDK_AVAILABLE:
        try:
            _stream_client = FeishuStreamClient()
        except (ImportError, ValueError) as e:
            logger.warning(f"[Feishu Stream] unable to create client: {e}")
            return None

    return _stream_client


def start_feishu_stream_background() -> bool:
    """
    \u5728\u540e\u53f0startedFeishu Stream \u5ba2\u6237\u7aef

    Returns:
        \u662f\u5426successstarted
    """
    client = get_feishu_stream_client()
    if client:
        client.start_background()
        return True
    return False
