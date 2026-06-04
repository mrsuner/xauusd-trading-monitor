from __future__ import annotations

from dashboard_api.settings import Settings


def test_settings_normalizes_placeholder_token() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost/db", API_TOKEN="change-me")

    assert settings.api_token is None


def test_settings_parses_cors_origins() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CORS_ORIGINS="http://localhost:5173, https://example.test",
    )

    assert settings.cors_origin_list == ["http://localhost:5173", "https://example.test"]
