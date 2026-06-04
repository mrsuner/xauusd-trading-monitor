from __future__ import annotations

import pytest
from pydantic import ValidationError

from x_publisher.settings import Settings


def test_settings_normalize_change_me_credentials() -> None:
    settings = Settings(DATABASE_URL="postgresql://x:y@localhost/db", X_API_KEY="change-me")

    assert settings.api_key is None
    assert settings.dry_run is True
    assert settings.enabled is False


def test_settings_validate_severity() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql://x:y@localhost/db", X_PUBLISHER_MIN_SEVERITY="P0")


def test_settings_parse_min_generated_at() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x:y@localhost/db",
        X_PUBLISHER_MIN_GENERATED_AT="2026-06-03T15:05:00+00:00",
    )

    assert settings.min_generated_at is not None
    assert settings.min_generated_at.isoformat() == "2026-06-03T15:05:00+00:00"
