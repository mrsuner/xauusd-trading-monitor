from __future__ import annotations

import pytest
from pydantic import ValidationError

from public_api.settings import Settings


def test_settings_normalizes_optional_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:secret@postgres:5432/public")
    monkeypatch.setenv("PUBLIC_INGEST_AUTH_MODE", "hmac")
    monkeypatch.setenv("PUBLIC_INGEST_KEY_ID", "change-me")
    monkeypatch.setenv("PUBLIC_INGEST_SECRET", "")

    settings = Settings()

    assert settings.ingest_key_id is None
    assert settings.ingest_secret is None


def test_settings_rejects_invalid_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:secret@postgres:5432/public")
    monkeypatch.setenv("PUBLIC_INGEST_AUTH_MODE", "none")

    with pytest.raises(ValidationError):
        Settings()
