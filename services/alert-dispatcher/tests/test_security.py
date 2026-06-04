from __future__ import annotations

from alert_dispatcher.security import sanitize_provider_response, sanitize_text


def test_sanitize_text_masks_common_secret_patterns() -> None:
    value = (
        "POST https://api.telegram.org/bot1234567890:abcdefghijklmnopqrstuvwxyz/sendMessage "
        'Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456 '
        'oauth_token="token-value"'
    )

    sanitized = sanitize_text(value)

    assert "bot1234567890" not in sanitized
    assert "abcdefghijklmnopqrstuvwxyz123456" not in sanitized
    assert 'oauth_token="token-value"' not in sanitized
    assert "https://api.telegram.org/bot[REDACTED]" in sanitized


def test_sanitize_provider_response_redacts_sensitive_keys() -> None:
    response = sanitize_provider_response(
        {
            "ok": True,
            "token": "secret-token",
            "result": {
                "message_id": 123,
                "chat_id": "-100123",
                "text": "public message",
            },
        }
    )

    assert response["token"] == "[REDACTED]"
    assert response["result"]["chat_id"] == "[REDACTED]"
    assert response["result"]["message_id"] == 123
