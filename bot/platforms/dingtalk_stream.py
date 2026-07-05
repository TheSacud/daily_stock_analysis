# -*- coding: utf-8 -*-
"""
===================================
DingTalk Stream mode\u9002\u914d\u5668
===================================

\u4f7f\u7528DingTalk\u5b98\u65b9 Stream SDK \u63a5\u5165\u673a\u5668\u4eba; \u65e0\u9700\u516c\u7f51 IP \u548c Webhook config.

\u4f18\u52bf:
- \u4e0d\u9700\u8981\u516c\u7f51 IP or\u57df\u540d
- \u4e0d\u9700\u8981config Webhook URL
- \u901a\u8fc7 WebSocket \u957f\u8fde\u63a5\u63a5\u6536\u6d88\u606f
- \u66f4\u7b80\u5355\u7684\u63a5\u5165\u65b9\u5f0f

\u4f9d\u8d56:
pip install dingtalk-stream

DingTalk Stream SDK:
https://github.com/open-dingtalk/dingtalk-stream-sdk-python
"""

import logging
import inspect
import threading
from datetime import datetime
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

# \u5c1d\u8bd5\u5bfc\u5165DingTalk Stream SDK
try:
    import dingtalk_stream
    from dingtalk_stream import AckMessage

    DINGTALK_STREAM_AVAILABLE = True
except ImportError:
    DINGTALK_STREAM_AVAILABLE = False
    logger.warning("[DingTalk Stream] dingtalk-stream SDK is not installed; Stream modeunavailable")
    logger.warning("[DingTalk Stream] please run: pip install dingtalk-stream")

from bot.models import BotMessage, BotResponse, ChatType


class DingtalkStreamHandler:
    """
    DingTalk Stream mode\u6d88\u606f\u5904\u7406\u5668

    \u5c06 Stream SDK \u7684\u56de\u8c03\u8f6c\u6362\u4e3a\u7edf\u4e00\u7684 BotMessage \u683c\u5f0f;
    \u5e76\u8c03\u7528command\u5206\u53d1\u5668\u5904\u7406.
    """

    def __init__(self, on_message: Callable[[BotMessage], Any]):
        """
        Args:
            on_message: \u6d88\u606f\u5904\u7406\u56de\u8c03\u51fd\u6570; \u63a5\u6536 BotMessage \u8fd4\u56de BotResponse
        """
        self._on_message = on_message
        self._logger = logger

    @staticmethod
    def _truncate_log_content(text: str, max_len: int = 200) -> str:
        cleaned = text.replace("\n", " ").strip()
        if len(cleaned) > max_len:
            return f"{cleaned[:max_len]}..."
        return cleaned

    def _log_incoming_message(self, message: BotMessage) -> None:
        content = message.raw_content or message.content or ""
        summary = self._truncate_log_content(content)
        self._logger.info(
            "[DingTalk Stream] Incoming message: msg_id=%s user_id=%s chat_id=%s chat_type=%s content=%s",
            message.message_id,
            message.user_id,
            message.chat_id,
            getattr(message.chat_type, "value", message.chat_type),
            summary,
        )

    if DINGTALK_STREAM_AVAILABLE:
        class _ChatbotHandler(dingtalk_stream.ChatbotHandler):
            """\u5185\u90e8\u6d88\u606f\u5904\u7406\u5668"""

            def __init__(self, parent: 'DingtalkStreamHandler'):
                super().__init__()
                self._parent = parent
                self.logger = logger

            async def process(self, callback: dingtalk_stream.CallbackMessage):
                """\u5904\u7406received\u7684\u6d88\u606f"""
                try:
                    # \u89e3\u6790\u6d88\u606f
                    incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)

                    # \u8f6c\u6362\u4e3a\u7edf\u4e00\u683c\u5f0f
                    bot_message = self._parent._parse_stream_message(incoming, callback.data)

                    if bot_message:
                        self._parent._log_incoming_message(bot_message)
                        # \u8c03\u7528\u6d88\u606f\u5904\u7406\u56de\u8c03
                        response = self._parent._on_message(bot_message)
                        if inspect.isawaitable(response):
                            response = await response

                        # \u53d1\u9001\u56de\u590d
                        if response and response.text:
                            # \u6784\u5efa @user prefix (\u7fa4\u804a\u573a\u666f\u4e0b\u9700\u8981\u5728\u6587\u672cMedium\u5305\u542b @user\u540d)
                            if response.at_user and incoming.sender_nick:
                                if response.markdown:
                                    self.reply_markdown(
                                        title="\u80a1\u7968analyze\u52a9\u624b",
                                        text=f"@{incoming.sender_nick} " + response.text,
                                        incoming_message=incoming
                                    )
                                else:
                                    self.reply_text(response.text, incoming)

                    return AckMessage.STATUS_OK, 'OK'

                except Exception as e:
                    self.logger.error(f"[DingTalk Stream] message handling failed: {e}")
                    self.logger.exception(e)
                    return AckMessage.STATUS_SYSTEM_EXCEPTION, str(e)

        def create_handler(self) -> '_ChatbotHandler':
            """\u521b\u5efa SDK \u9700\u8981\u7684\u5904\u7406\u5668\u5b9e\u4f8b"""
            return self._ChatbotHandler(self)

    def _parse_stream_message(self, incoming: Any, raw_data: dict) -> Optional[BotMessage]:
        """
        \u89e3\u6790 Stream \u6d88\u606f\u4e3a\u7edf\u4e00\u683c\u5f0f

        Args:
            incoming: ChatbotMessage \u5bf9\u8c61
            raw_data: \u539f\u59cb\u56de\u8c03\u6570\u636e
        """
        try:
            raw_data = dict(raw_data or {})

            # \u83b7\u53d6\u6d88\u606f\u5185\u5bb9
            raw_content = incoming.text.content if incoming.text else ''

            # \u63d0\u53d6command (\u53bb\u9664 @\u673a\u5668\u4eba)
            content = self._extract_command(raw_content)

            # conversation\u7c7b\u578b
            conversation_type = getattr(incoming, 'conversation_type', None)
            if conversation_type == '1':
                chat_type = ChatType.PRIVATE
            elif conversation_type == '2':
                chat_type = ChatType.GROUP
            else:
                chat_type = ChatType.UNKNOWN

            # \u662f\u5426 @\u4e86\u673a\u5668\u4eba (Stream mode\u4e0breceived\u7684\u6d88\u606f\u4e00\u822c\u90fd\u662f @\u673a\u5668\u4eba\u7684)
            mentioned = True

            # \u63d0\u53d6 sessionWebhook; \u4fbf\u4e8e\u5f02\u6b65\u63a8\u9001
            session_webhook = (
                    getattr(incoming, 'session_webhook', None)
                    or raw_data.get('sessionWebhook')
                    or raw_data.get('session_webhook')
            )
            if session_webhook:
                raw_data['_session_webhook'] = session_webhook

            return BotMessage(
                platform='dingtalk',
                message_id=getattr(incoming, 'msg_id', '') or '',
                user_id=getattr(incoming, 'sender_id', '') or '',
                user_name=getattr(incoming, 'sender_nick', '') or '',
                chat_id=getattr(incoming, 'conversation_id', '') or '',
                chat_type=chat_type,
                content=content,
                raw_content=raw_content,
                mentioned=mentioned,
                mentions=[],
                timestamp=datetime.now(),
                raw_data=raw_data,
            )

        except Exception as e:
            logger.error(f"[DingTalk Stream] message parse failed: {e}")
            return None

    def _extract_command(self, text: str) -> str:
        """\u63d0\u53d6command\u5185\u5bb9 (\u53bb\u9664 @\u673a\u5668\u4eba)"""
        import re
        text = re.sub(r'^@[\S]+\s*', '', text.strip())
        return text.strip()


class DingtalkStreamClient:
    """
    DingTalk Stream mode\u5ba2\u6237\u7aef

    \u5c01\u88c5 dingtalk-stream SDK; \u63d0\u4f9b\u7b80\u5355\u7684started\u63a5\u53e3.

    \u4f7f\u7528\u65b9\u5f0f:
        client = DingtalkStreamClient()
        client.start()  # \u963b\u585e\u8fd0\u884c

        # or\u8005\u5728\u540e\u53f0\u8fd0\u884c
        client.start_background()
    """

    def __init__(
            self,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None
    ):
        """
        Args:
            client_id: \u5e94\u7528 AppKey (\u4e0d\u4f20\u5219\u4ececonfig\u8bfb\u53d6)
            client_secret: \u5e94\u7528 AppSecret (\u4e0d\u4f20\u5219\u4ececonfig\u8bfb\u53d6)
        """
        if not DINGTALK_STREAM_AVAILABLE:
            raise ImportError(
                "dingtalk-stream SDK is not installed.\n"
                "please run: pip install dingtalk-stream"
            )

        from src.config import get_config
        config = get_config()

        self._client_id = client_id or getattr(config, 'dingtalk_app_key', None)
        self._client_secret = client_secret or getattr(config, 'dingtalk_app_secret', None)

        if not self._client_id or not self._client_secret:
            raise ValueError(
                "DingTalk Stream mode\u9700\u8981config DINGTALK_APP_KEY \u548c DINGTALK_APP_SECRET"
            )

        self._client: Optional[dingtalk_stream.DingTalkStreamClient] = None
        self._background_thread: Optional[threading.Thread] = None
        self._running = False

    def _create_message_handler(self) -> Callable[[BotMessage], Any]:
        """\u521b\u5efa\u6d88\u606f\u5904\u7406\u51fd\u6570"""

        async def handle_message(message: BotMessage) -> BotResponse:
            from bot.dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            return await dispatcher.dispatch_async(message)

        return handle_message

    def start(self) -> None:
        """
        started Stream \u5ba2\u6237\u7aef (\u963b\u585e)

        \u6b64\u65b9\u6cd5\u4f1a\u963b\u585e\u5f53\u524d\u7ebf\u7a0b; \u76f4\u5230\u5ba2\u6237\u7aef\u505c\u6b62.
        """
        logger.info("[DingTalk Stream] starting...")

        # \u521b\u5efa\u51ed\u8bc1
        credential = dingtalk_stream.Credential(
            self._client_id,
            self._client_secret
        )

        # \u521b\u5efa\u5ba2\u6237\u7aef
        self._client = dingtalk_stream.DingTalkStreamClient(credential)

        # \u6ce8\u518c\u6d88\u606f\u5904\u7406\u5668
        handler = DingtalkStreamHandler(self._create_message_handler())
        self._client.register_callback_handler(
            dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
            handler.create_handler()
        )

        self._running = True
        logger.info("[DingTalk Stream] client started; waiting for messages...")

        # started (\u963b\u585e)
        self._client.start_forever()

    def start_background(self) -> None:
        """
        \u5728\u540e\u53f0\u7ebf\u7a0bstarted Stream \u5ba2\u6237\u7aef (\u975e\u963b\u585e)

        \u9002\u7528\u4e8e\u4e0eother\u670d\u52a1 (\u5982 WebUI)\u540c\u65f6\u8fd0\u884c\u7684\u573a\u666f.
        """
        if self._background_thread and self._background_thread.is_alive():
            logger.warning("[DingTalk Stream] client is already running")
            return

        self._running = True
        self._background_thread = threading.Thread(
            target=self._run_in_background,
            daemon=True,
            name="DingtalkStreamClient"
        )
        self._background_thread.start()
        logger.info("[DingTalk Stream] \u540e\u53f0client started")

    def _run_in_background(self) -> None:
        """\u540e\u53f0\u8fd0\u884c (\u5904\u7406\u5f02\u5e38\u548c\u91cd\u8fde)"""
        import time

        while self._running:
            try:
                self.start()
            except Exception as e:
                logger.error(f"[DingTalk Stream] runtime exception: {e}")
                if self._running:
                    logger.info("[DingTalk Stream] reconnecting in 5 seconds...")
                    time.sleep(5)

    def stop(self) -> None:
        """\u505c\u6b62\u5ba2\u6237\u7aef"""
        self._running = False
        logger.info("[DingTalk Stream] client stopped")

    @property
    def is_running(self) -> bool:
        """\u662f\u5426\u6b63\u5728\u8fd0\u884c"""
        return self._running


# \u5168\u5c40\u5ba2\u6237\u7aef\u5b9e\u4f8b
_stream_client: Optional[DingtalkStreamClient] = None


def get_dingtalk_stream_client() -> Optional[DingtalkStreamClient]:
    """\u83b7\u53d6\u5168\u5c40 Stream \u5ba2\u6237\u7aef\u5b9e\u4f8b"""
    global _stream_client

    if _stream_client is None and DINGTALK_STREAM_AVAILABLE:
        try:
            _stream_client = DingtalkStreamClient()
        except (ImportError, ValueError) as e:
            logger.warning(f"[DingTalk Stream] unable to create client: {e}")
            return None

    return _stream_client


def start_dingtalk_stream_background() -> bool:
    """
    \u5728\u540e\u53f0startedDingTalk Stream \u5ba2\u6237\u7aef

    Returns:
        \u662f\u5426successstarted
    """
    client = get_dingtalk_stream_client()
    if client:
        client.start_background()
        return True
    return False
