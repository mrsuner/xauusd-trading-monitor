from __future__ import annotations

import pytest
from pydantic import ValidationError

from public_syncer.settings import Settings


def test_settings_normalizes_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "https://news.example.com/")
    monkeypatch.setenv("PUBLIC_INGEST_PATH", "ingest/events")

    settings = Settings()

    assert settings.public_api_base_url == "https://news.example.com"
    assert settings.public_ingest_path == "/ingest/events"
    assert settings.ingest_url == "https://news.example.com/ingest/events"


def test_settings_rejects_invalid_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_SYNC_AUTH_MODE", "none")

    with pytest.raises(ValidationError):
        Settings()
