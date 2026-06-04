from __future__ import annotations

from public_syncer.security_scrub import sanitize_provider_response, sanitize_text


def test_sanitize_text_masks_bearer_and_signature() -> None:
    sanitized = sanitize_text("Bearer abcdefghijklmnopqrstuvwxyz123456 X-XER-Signature=secret-signature-value")

    assert "abcdefghijklmnopqrstuvwxyz123456" not in sanitized
    assert "secret-signature-value" not in sanitized


def test_sanitize_provider_response_redacts_signature_key() -> None:
    response = sanitize_provider_response(
        {
            "status": "created",
            "X-XER-Signature": "secret",
            "public_event_id": "evt_123",
        }
    )

    assert response["X-XER-Signature"] == "[REDACTED]"
    assert response["public_event_id"] == "evt_123"
