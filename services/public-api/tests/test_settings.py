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
    assert settings.public_default_language == "en"
    assert settings.public_language_priority == ("en", "zh-Hant")


def test_settings_accepts_public_language_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:secret@postgres:5432/public")
    monkeypatch.setenv("PUBLIC_DEFAULT_LANGUAGE", "zh-Hant")
    monkeypatch.setenv("PUBLIC_LANGUAGE_PRIORITY", "zh-Hant,en,th,ja")

    settings = Settings()

    assert settings.public_default_language == "zh-Hant"
    assert settings.public_language_priority == ("zh-Hant", "en", "th", "ja")


def test_settings_rejects_invalid_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:secret@postgres:5432/public")
    monkeypatch.setenv("PUBLIC_INGEST_AUTH_MODE", "none")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_duplicate_public_language_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:secret@postgres:5432/public")
    monkeypatch.setenv("PUBLIC_LANGUAGE_PRIORITY", "en,en")

    with pytest.raises(ValidationError):
        Settings()
