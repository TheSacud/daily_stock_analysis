# -*- coding: utf-8 -*-
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

from nacl.signing import SigningKey

from bot.models import ChatType
from bot.platforms.discord import DiscordPlatform


def _make_platform(public_key: str) -> DiscordPlatform:
    with patch(
        "src.config.get_config",
        return_value=SimpleNamespace(
            discord_interactions_public_key=public_key,
        ),
    ):
        return DiscordPlatform()


def _current_timestamp() -> str:
    """\u8fd4\u56de\u5f53\u524d Unix \u79d2\u5b57\u7b26\u4e32，\u7528\u4e8e\u751f\u6210\u6709\u6548\u7b7e\u540d。"""
    return str(int(time.time()))


def _sign_headers(signing_key: SigningKey, body: bytes, timestamp: str | None = None):
    if timestamp is None:
        timestamp = _current_timestamp()
    signature = signing_key.sign(timestamp.encode("utf-8") + body).signature.hex()
    return {
        "X-Signature-Ed25519": signature,
        "X-Signature-Timestamp": timestamp,
    }


def test_signed_ping_request_is_accepted():
    signing_key = SigningKey.generate()
    platform = _make_platform(signing_key.verify_key.encode().hex())
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")

    message, response = platform.handle_webhook(
        _sign_headers(signing_key, body),
        body,
        payload,
    )

    assert message is None
    assert response is not None
    assert response.status_code == 200
    assert response.body == {"type": 1}


def test_signed_interaction_request_returns_deferred_ack():
    """type=2 \u4ea4\u4e92\u5e94\u8fd4\u56de type 5 \u5ef6\u8fdf ACK，\u540c\u65f6\u4ecd\u89e3\u6790\u51fa BotMessage。"""
    signing_key = SigningKey.generate()
    platform = _make_platform(signing_key.verify_key.encode().hex())
    payload = {
        "id": "interaction-1",
        "type": 2,
        "channel_id": "channel-1",
        "guild_id": "guild-1",
        "application_id": "app-123",
        "token": "interaction-token",
        "member": {
            "user": {
                "id": "user-1",
                "username": "tester",
            }
        },
        "data": {
            "name": "analyze",
            "options": [
                {"name": "stock_code", "value": "600519"},
            ],
        },
    }
    body = json.dumps(payload).encode("utf-8")

    message, response = platform.handle_webhook(
        _sign_headers(signing_key, body),
        body,
        payload,
    )

    # \u5e94\u8fd4\u56de type 5 \u5ef6\u8fdf ACK
    assert response is not None
    assert response.status_code == 200
    assert response.body == {"type": 5}

    # \u540c\u65f6\u4ecd\u89e3\u6790\u51fa\u6d88\u606f
    assert message is not None
    assert message.platform == "discord"
    assert message.chat_id == "channel-1"
    assert message.chat_type == ChatType.GROUP
    assert message.user_id == "user-1"
    assert message.user_name == "tester"
    assert message.content == "/analyze 600519"
    # follow-up \u9700\u8981\u7684\u5b57\u6bb5\u5b58\u5728\u4e8e raw_data
    assert message.raw_data.get("application_id") == "app-123"
    assert message.raw_data.get("token") == "interaction-token"


def test_invalid_signature_ping_request_is_rejected_before_challenge():
    signing_key = SigningKey.generate()
    platform = _make_platform(signing_key.verify_key.encode().hex())
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")
    headers = _sign_headers(signing_key, body)
    headers["X-Signature-Ed25519"] = "00" * 64

    message, response = platform.handle_webhook(headers, body, payload)

    assert message is None
    assert response is not None
    assert response.status_code == 401
    assert response.body == {"error": "Invalid Discord signature"}


def test_missing_signature_header_is_rejected():
    signing_key = SigningKey.generate()
    platform = _make_platform(signing_key.verify_key.encode().hex())
    payload = {
        "id": "interaction-2",
        "type": 2,
        "data": {"name": "help"},
    }
    body = json.dumps(payload).encode("utf-8")

    message, response = platform.handle_webhook(
        {"X-Signature-Timestamp": _current_timestamp()},
        body,
        payload,
    )

    assert message is None
    assert response is not None
    assert response.status_code == 401
    assert response.body == {"error": "Invalid Discord signature"}


def test_invalid_public_key_configuration_is_rejected():
    platform = _make_platform("not-a-hex-public-key")
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")

    message, response = platform.handle_webhook(
        {
            "X-Signature-Ed25519": "00" * 64,
            "X-Signature-Timestamp": _current_timestamp(),
        },
        body,
        payload,
    )

    assert message is None
    assert response is not None
    assert response.status_code == 401
    assert response.body == {"error": "Invalid Discord signature"}


def test_expired_timestamp_is_rejected():
    """\u8fc7\u671f timestamp（\u8d85\u51fa ±5 \u5206\u949f\u7a97\u53e3）\u5e94\u88ab\u62d2\u7edd，\u9632\u91cd\u653e\u653b\u51fb。"""
    signing_key = SigningKey.generate()
    platform = _make_platform(signing_key.verify_key.encode().hex())
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")
    # 10 \u5206\u949f\u524d\u7684 timestamp
    stale_ts = str(int(time.time()) - 600)

    message, response = platform.handle_webhook(
        _sign_headers(signing_key, body, timestamp=stale_ts),
        body,
        payload,
    )

    assert message is None
    assert response is not None
    assert response.status_code == 401


def test_format_response_wraps_interaction_callback():
    """type=2 \u4ea4\u4e92\u54cd\u5e94\u5e94\u4f7f\u7528 Interaction Response \u56de\u8c03\u683c\u5f0f（type=4 + data）。"""
    from bot.models import BotMessage, BotResponse, ChatType

    platform = _make_platform("00" * 32)
    message = BotMessage(
        platform="discord",
        message_id="msg-1",
        user_id="user-1",
        user_name="tester",
        chat_id="channel-1",
        chat_type=ChatType.GROUP,
        content="/analyze 600519",
        raw_data={"type": 2, "data": {"name": "analyze"}},
    )
    response = BotResponse.text_response("\u5206\u6790\u7ed3\u679c")

    webhook_response = platform.format_response(response, message)

    assert webhook_response.status_code == 200
    assert webhook_response.body["type"] == 4
    assert "data" in webhook_response.body
    assert webhook_response.body["data"]["content"] == "\u5206\u6790\u7ed3\u679c"
    assert webhook_response.body["data"]["tts"] is False


def test_send_followup_patches_original_message():
    """send_followup \u5e94 PATCH Discord follow-up webhook。"""
    from bot.models import BotMessage, BotResponse, ChatType

    platform = _make_platform("00" * 32)
    message = BotMessage(
        platform="discord",
        message_id="msg-1",
        user_id="user-1",
        user_name="tester",
        chat_id="channel-1",
        chat_type=ChatType.GROUP,
        content="/analyze 600519",
        raw_data={
            "type": 2,
            "application_id": "app-123",
            "token": "interaction-token",
        },
    )
    response = BotResponse.text_response("\u5206\u6790\u7ed3\u679c")

    with patch("bot.platforms.discord.requests") as mock_requests:
        mock_resp = type("R", (), {"status_code": 200, "text": "ok"})()
        mock_requests.patch.return_value = mock_resp
        result = platform.send_followup(response, message)

    assert result is True
    mock_requests.patch.assert_called_once()
    call_args = mock_requests.patch.call_args
    assert "/app-123/interaction-token/messages/@original" in call_args[0][0]
    assert call_args[1]["json"]["content"] == "\u5206\u6790\u7ed3\u679c"


def test_send_followup_chunks_long_content():
    """\u8d85\u8fc7 2000 \u5b57\u7b26\u7684 follow-up \u5e94\u88ab\u5206\u5757：\u9996\u5757 PATCH，\u540e\u7eed POST。"""
    from bot.models import BotMessage, BotResponse, ChatType

    platform = _make_platform("00" * 32)
    message = BotMessage(
        platform="discord",
        message_id="msg-1",
        user_id="user-1",
        user_name="tester",
        chat_id="channel-1",
        chat_type=ChatType.GROUP,
        content="/analyze 600519",
        raw_data={
            "type": 2,
            "application_id": "app-123",
            "token": "interaction-token",
        },
    )
    # \u751f\u6210\u8d85\u8fc7 2000 \u5b57\u7b26\u7684\u5185\u5bb9
    long_content = "A" * 3500
    response = BotResponse.text_response(long_content)

    with patch("bot.platforms.discord.requests") as mock_requests:
        mock_resp = type("R", (), {"status_code": 200, "text": "ok"})()
        mock_requests.patch.return_value = mock_resp
        mock_requests.post.return_value = mock_resp
        result = platform.send_followup(response, message)

    assert result is True
    # \u9996\u5757\u4f7f\u7528 PATCH
    mock_requests.patch.assert_called_once()
    patch_url = mock_requests.patch.call_args[0][0]
    assert "/messages/@original" in patch_url
    # \u540e\u7eed\u5757\u4f7f\u7528 POST
    assert mock_requests.post.call_count >= 1
    post_url = mock_requests.post.call_args[0][0]
    assert post_url.endswith("/app-123/interaction-token")


def test_send_followup_missing_token_returns_false():
    """\u7f3a\u5c11 interaction token \u65f6 send_followup \u5e94\u8fd4\u56de False。"""
    from bot.models import BotMessage, BotResponse, ChatType

    platform = _make_platform("00" * 32)
    message = BotMessage(
        platform="discord",
        message_id="msg-1",
        user_id="user-1",
        user_name="tester",
        chat_id="channel-1",
        chat_type=ChatType.GROUP,
        content="/analyze 600519",
        raw_data={"type": 2},
    )
    response = BotResponse.text_response("\u5206\u6790\u7ed3\u679c")
    assert platform.send_followup(response, message) is False


def test_non_numeric_timestamp_is_rejected():
    """\u975e\u6570\u5b57 timestamp \u5e94\u88ab\u62d2\u7edd。"""
    signing_key = SigningKey.generate()
    platform = _make_platform(signing_key.verify_key.encode().hex())
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")

    message, response = platform.handle_webhook(
        _sign_headers(signing_key, body, timestamp="not-a-number"),
        body,
        payload,
    )

    assert message is None
    assert response is not None
    assert response.status_code == 401


def test_boolean_option_true_emits_name():
    """\u5e03\u5c14 True \u9009\u9879\u5e94\u8f93\u51fa option name，\u800c\u975e\u5b57\u9762 'true'。"""
    platform = _make_platform("00" * 32)
    interaction_data = {
        "name": "analyze",
        "options": [
            {"name": "stock_code", "value": "600519"},
            {"name": "full", "value": True},
        ],
    }
    content = platform._build_command_content(interaction_data)
    assert content == "/analyze 600519 full"


def test_boolean_option_false_is_omitted():
    """\u5e03\u5c14 False \u9009\u9879\u5e94\u88ab\u5ffd\u7565，\u4e0d\u51fa\u73b0\u5728\u547d\u4ee4\u5185\u5bb9\u4e2d。"""
    platform = _make_platform("00" * 32)
    interaction_data = {
        "name": "analyze",
        "options": [
            {"name": "stock_code", "value": "600519"},
            {"name": "full", "value": False},
        ],
    }
    content = platform._build_command_content(interaction_data)
    assert content == "/analyze 600519"
