from __future__ import annotations

import pytest
from pydantic import ValidationError

from telegram_channel_publisher.settings import Settings


def test_settings_defaults_safe() -> None:
    settings = Settings(DATABASE_URL="postgresql://x:y@localhost/db")

    assert settings.enabled is False
    assert settings.dry_run is True
    assert settings.min_severity == "A"


def test_settings_normalizes_change_me() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x:y@localhost/db",
        TELEGRAM_CHANNEL_BOT_TOKEN="change-me",
        TELEGRAM_CHANNEL_ID="",
    )

    assert settings.bot_token is None
    assert settings.channel_id is None


def test_settings_rejects_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql://x:y@localhost/db", TELEGRAM_CHANNEL_MIN_SEVERITY="P0")
