# -*- coding: utf-8 -*-
"""
===================================
Discord \u5e73\u53f0\u9002\u914d\u5668
===================================

\u8d1f\u8d23:
1. \u9a8c\u8bc1 Discord Webhook request
2. \u89e3\u6790 Discord \u6d88\u606f\u4e3a\u7edf\u4e00\u683c\u5f0f
3. \u5c06\u54cd\u5e94\u8f6c\u6362\u4e3a Discord \u683c\u5f0f
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

import requests
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from bot.platforms.base import BotPlatform
from bot.models import BotMessage, WebhookResponse, ChatType


logger = logging.getLogger(__name__)


class DiscordPlatform(BotPlatform):
    """Discord \u5e73\u53f0\u9002\u914d\u5668"""

    def __init__(self):
        from src.config import get_config

        config = get_config()
        self._interactions_public_key = (
            getattr(config, "discord_interactions_public_key", None) or ""
        ).strip()

    @property
    def platform_name(self) -> str:
        """\u5e73\u53f0\u6807\u8bc6name"""
        return "discord"

    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:
        """\u9a8c\u8bc1 Discord Webhook request\u7b7e\u540d

        Discord Webhook \u7b7e\u540d\u9a8c\u8bc1:
        1. \u4ecerequest\u5934\u83b7\u53d6 X-Signature-Ed25519 \u548c X-Signature-Timestamp
        2. \u4f7f\u7528\u516c\u94a5\u9a8c\u8bc1\u7b7e\u540d

        Args:
            headers: HTTP request\u5934
            body: request\u4f53\u539f\u59cb\u5b57\u8282

        Returns:
            \u7b7e\u540d\u662f\u5426\u6709\u6548
        """
        if not self._interactions_public_key:
            logger.warning("[Discord] not configured interactions public key; request rejected")
            return False

        normalized_headers = {str(k).lower(): v for k, v in headers.items()}
        signature = normalized_headers.get("x-signature-ed25519", "")
        timestamp = normalized_headers.get("x-signature-timestamp", "")

        if not signature or not timestamp:
            logger.warning("[Discord] missing signature headers; request rejected")
            return False

        # \u6821\u9a8c timestamp \u683c\u5f0f\u4e0e\u65f6\u6548; \u9632\u6b62\u91cd\u653e\u653b\u51fb
        try:
            ts_int = int(timestamp)
        except (TypeError, ValueError):
            logger.warning("[Discord] invalid timestamp: must be Unix seconds integer; request rejected")
            return False

        try:
            now_ts = int(time.time())
        except Exception as exc:
            logger.warning("[Discord] failed to get current time: %s; request rejected", exc)
            return False

        # \u5141\u8bb8\u7684\u65f6\u95f4\u7a97\u53e3: ±5 \u5206\u949f
        if abs(now_ts - ts_int) > 300:
            logger.warning(
                "[Discord] request timestamp \u8d85\u51fa\u5141\u8bb8\u7a97\u53e3; \u53ef\u80fd\u4e3a\u91cd\u653e\u653b\u51fb: timestamp=%s, now=%s",
                ts_int,
                now_ts,
            )
            return False

        try:
            verify_key = VerifyKey(bytes.fromhex(self._interactions_public_key))
            signature_bytes = bytes.fromhex(signature)
        except ValueError:
            logger.warning("[Discord] public key or signature is not valid hex; request rejected")
            return False
        except Exception as exc:
            logger.warning("[Discord] unable to load signature public key: %s", exc)
            return False

        try:
            verify_key.verify(timestamp.encode("utf-8") + body, signature_bytes)
        except BadSignatureError:
            logger.warning("[Discord] signature verification failed")
            return False
        except Exception as exc:
            logger.warning("[Discord] signature validation exception: %s", exc)
            return False

        return True

    def handle_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
        data: Dict[str, Any],
    ) -> Tuple[Optional[BotMessage], Optional[WebhookResponse]]:
        """Discord \u9700\u8981\u5148\u9a8c\u7b7e; \u518d\u5904\u7406 ping/challenge."""
        if not self.verify_request(headers, body):
            return None, WebhookResponse.error("Invalid Discord signature", 401)

        challenge_response = self.handle_challenge(data)
        if challenge_response:
            return None, challenge_response

        message = self.parse_message(data)
        if message is not None and data.get("type") == 2:
            # Discord requires an initial response within 3 s.  Return a
            # deferred acknowledgement (type 5 = DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE)
            # so the handler can dispatch the command in the background and
            # deliver the result via follow-up webhook.
            return message, WebhookResponse.success({"type": 5})

        return message, None

    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:
        """\u89e3\u6790 Discord \u6d88\u606f\u4e3a\u7edf\u4e00\u683c\u5f0f

        Args:
            data: \u89e3\u6790\u540e\u7684 JSON \u6570\u636e

        Returns:
            BotMessage \u5bf9\u8c61; or None (\u4e0d\u9700\u8981\u5904\u7406)
        """
        interaction_type = data.get("type")
        if interaction_type != 2:
            return None

        interaction_data = data.get("data", {})
        content = self._build_command_content(interaction_data)
        if not content:
            return None

        author = (
            data.get("user")
            or (data.get("member") or {}).get("user")
            or data.get("author", {})
        )
        user_id = str(author.get("id") or "")
        user_name = author.get("username", "unknown")
        channel_id = str(data.get("channel_id") or "")
        guild_id = str(data.get("guild_id") or "")

        if guild_id:
            chat_type = ChatType.GROUP
        elif channel_id:
            chat_type = ChatType.PRIVATE
        else:
            chat_type = ChatType.UNKNOWN

        return BotMessage(
            platform=self.platform_name,
            message_id=str(data.get("id") or ""),
            user_id=user_id,
            user_name=user_name,
            chat_id=channel_id or guild_id or user_id,
            chat_type=chat_type,
            content=content,
            raw_content=content,
            mentioned=False,
            mentions=[],
            timestamp=self._parse_timestamp(data.get("timestamp")),
            raw_data={
                **data,
                "_interaction_name": interaction_data.get("name", ""),
            },
        )

    def format_response(self, response: Any, message: BotMessage) -> WebhookResponse:
        """\u5c06\u7edf\u4e00\u54cd\u5e94\u8f6c\u6362\u4e3a Discord \u683c\u5f0f

        \u5bf9\u4e8e Interaction (type=2)request; \u8fd4\u56de Discord Interaction Response
        callback \u683c\u5f0f (type=4 CHANNEL_MESSAGE_WITH_SOURCE + nested data).

        Args:
            response: \u7edf\u4e00\u54cd\u5e94\u5bf9\u8c61
            message: \u539f\u59cb\u6d88\u606f\u5bf9\u8c61

        Returns:
            WebhookResponse \u5bf9\u8c61
        """
        content = response.text if hasattr(response, "text") else str(response)

        message_data = {
            "content": content,
            "tts": False,
            "embeds": [],
            "allowed_mentions": {
                "parse": ["users", "roles", "everyone"]
            },
        }

        # Interaction (slash-command)\u9700\u8981 Interaction Response \u56de\u8c03\u683c\u5f0f
        if message.raw_data.get("type") == 2:
            discord_response = {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": message_data,
            }
        else:
            discord_response = message_data

        return WebhookResponse.success(discord_response)

    # Discord message content hard limit
    DISCORD_MAX_CONTENT_LENGTH = 2000

    def send_followup(self, response: Any, message: BotMessage) -> bool:
        """Edit the deferred interaction placeholder with the real result.

        Uses ``PATCH /webhooks/{application_id}/{token}/messages/@original``
        to update the original deferred message, then sends additional
        follow-up messages via ``POST`` if the content exceeds Discord's
        2 000-character limit.
        """
        raw = message.raw_data
        application_id = raw.get("application_id", "")
        interaction_token = raw.get("token", "")
        if not application_id or not interaction_token:
            logger.warning(
                "[Discord] \u7f3a\u5c11 application_id or interaction token; \u65e0\u6cd5\u53d1\u9001 follow-up"
            )
            return False

        content = response.text if hasattr(response, "text") else str(response)

        from src.formatters import chunk_content_by_max_words

        try:
            chunks = chunk_content_by_max_words(
                content, self.DISCORD_MAX_CONTENT_LENGTH
            )
        except (ValueError, Exception) as exc:
            logger.warning("[Discord] message chunking failed: %s; trying whole-message send", exc)
            chunks = [content]

        base_url = (
            f"https://discord.com/api/v10/webhooks/"
            f"{application_id}/{interaction_token}"
        )

        success = True
        for idx, chunk in enumerate(chunks):
            try:
                if idx == 0:
                    # PATCH the original deferred message
                    resp = requests.patch(
                        f"{base_url}/messages/@original",
                        json={"content": chunk},
                        timeout=10,
                    )
                else:
                    # POST additional follow-up messages
                    resp = requests.post(
                        base_url,
                        json={"content": chunk},
                        timeout=10,
                    )
                if resp.status_code >= 300:
                    logger.error(
                        "[Discord] follow-up chunk %d/%d send failed: %s %s",
                        idx + 1,
                        len(chunks),
                        resp.status_code,
                        resp.text[:200],
                    )
                    success = False
            except Exception as exc:
                logger.error(
                    "[Discord] follow-up chunk %d/%d request\u5f02\u5e38: %s",
                    idx + 1,
                    len(chunks),
                    exc,
                )
                success = False

        if success:
            logger.info("[Discord] follow-up message sent successfully (%d chunks)", len(chunks))
        return success

    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:
        """\u5904\u7406 Discord \u9a8c\u8bc1request

        Discord \u5728config Webhook \u65f6\u4f1a\u53d1\u9001\u9a8c\u8bc1request

        Args:
            data: request\u6570\u636e

        Returns:
            \u9a8c\u8bc1\u54cd\u5e94; or None (\u4e0d\u662f\u9a8c\u8bc1request)
        """
        # Discord Webhook \u9a8c\u8bc1request\u7c7b\u578b\u662f 1
        if data.get("type") == 1:
            return WebhookResponse.success({
                "type": 1
            })

        # Discord command\u4ea4\u4e92\u9a8c\u8bc1
        if "challenge" in data:
            return WebhookResponse.success({
                "challenge": data["challenge"]
            })

        return None

    def _build_command_content(self, interaction_data: Dict[str, Any]) -> str:
        command_name = str(interaction_data.get("name", "")).strip()
        if not command_name:
            return ""

        parts = [f"/{command_name}"]
        self._append_option_parts(parts, interaction_data.get("options", []))
        return " ".join(parts).strip()

    def _append_option_parts(self, parts: List[str], options: Any) -> None:
        if not isinstance(options, list):
            return

        for option in options:
            if not isinstance(option, dict):
                continue

            nested_options = option.get("options")
            if nested_options:
                nested_name = str(option.get("name", "")).strip()
                if nested_name:
                    parts.append(nested_name)
                self._append_option_parts(parts, nested_options)
                continue

            value = option.get("value")
            if value is None:
                continue
            if isinstance(value, bool):
                # Emit the option name for truthy flags so downstream
                # commands receive a semantic token (e.g. "full") instead
                # of a literal "true"/"false" string.  False flags are
                # simply omitted.
                if value:
                    opt_name = str(option.get("name", "")).strip()
                    if opt_name:
                        parts.append(opt_name)
            else:
                parts.append(str(value))

    def _parse_timestamp(self, value: Any) -> datetime:
        if not value:
            return datetime.now()

        if isinstance(value, datetime):
            return value

        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return datetime.now()
