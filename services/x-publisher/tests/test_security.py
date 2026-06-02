from __future__ import annotations

from x_publisher.security import sanitize_provider_response, sanitize_text


def test_sanitize_text_masks_oauth_values() -> None:
    sanitized = sanitize_text('OAuth oauth_token="access-token", oauth_signature="signature-value"')

    assert "access-token" not in sanitized
    assert "signature-value" not in sanitized
    assert 'oauth_token="[REDACTED]"' in sanitized


def test_sanitize_provider_response_redacts_auth_header() -> None:
    response = sanitize_provider_response({"Authorization": "OAuth secret", "data": {"id": "123"}})

    assert response["Authorization"] == "[REDACTED]"
    assert response["data"]["id"] == "123"
