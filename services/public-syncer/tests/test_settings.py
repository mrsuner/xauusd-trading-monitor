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
    assert settings.public_raw_ingest_path == "/ingest/raw-items"
    assert settings.raw_ingest_url == "https://news.example.com/ingest/raw-items"
    assert settings.public_sync_languages == ("zh-Hant", "en")
    assert settings.public_raw_sync_languages == ("zh-Hant", "en")


def test_settings_normalizes_raw_ingest_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "https://news.example.com/")
    monkeypatch.setenv("PUBLIC_RAW_INGEST_PATH", "ingest/raw-items")
    monkeypatch.setenv("PUBLIC_RAW_MIN_RELEVANCE_SCORE", "75")

    settings = Settings()

    assert settings.public_raw_ingest_path == "/ingest/raw-items"
    assert settings.raw_min_relevance_score == 75


def test_settings_accepts_sync_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_SYNC_LANGUAGES", "zh-Hant,en,th,ja")
    monkeypatch.setenv("PUBLIC_RAW_SYNC_LANGUAGES", "zh-Hant,en,th,ja")

    settings = Settings()

    assert settings.public_sync_languages == ("zh-Hant", "en", "th", "ja")
    assert settings.public_raw_sync_languages == ("zh-Hant", "en", "th", "ja")


def test_settings_rejects_invalid_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_SYNC_AUTH_MODE", "none")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_duplicate_sync_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_SYNC_LANGUAGES", "en,en")

    with pytest.raises(ValidationError):
        Settings()
