from __future__ import annotations

from telegram_channel_publisher.security import sanitize_provider_response, sanitize_text


def test_sanitize_text_masks_telegram_bot_url() -> None:
    sanitized = sanitize_text("https://api.telegram.org/botsecret-token/sendMessage failed")

    assert "secret-token" not in sanitized
    assert "https://api.telegram.org/bot[REDACTED]" in sanitized


def test_sanitize_provider_response_redacts_chat_id() -> None:
    response = sanitize_provider_response({"result": {"message_id": 456, "chat_id": "-100secret"}})

    assert response["result"]["message_id"] == 456
    assert response["result"]["chat_id"] == "[REDACTED]"
