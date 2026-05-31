from __future__ import annotations

import pytest
from pydantic import ValidationError

from alert_dispatcher.settings import Settings


def test_settings_default_to_safe_dry_run() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost/db")

    assert settings.alert_dry_run is True
    assert settings.dispatch_existing_events_on_start is False


def test_settings_normalizes_placeholder_secrets() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        TELEGRAM_BOT_TOKEN="change-me",
        TELEGRAM_CHAT_ID="",
    )

    assert settings.telegram_bot_token is None
    assert settings.telegram_chat_id is None


def test_settings_rejects_negative_budget() -> None:
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            MAX_ALERTS_PER_RUN="-1",
        )
