from __future__ import annotations

import pytest

from event_router.settings import Settings


def test_settings_validate_backfill_mode() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://example",
        EVENT_ROUTER_BACKFILL_MODE="telegram_only",
        PUBLIC_X_A_RELEVANCE_THRESHOLD=85,
    )

    assert settings.backfill_mode == "telegram_only"
    assert settings.public_x_a_relevance_threshold == 85
    assert settings.public_outbox_languages == ("zh-Hant", "en")
    assert settings.public_outbox_default_language == "en"


def test_settings_accepts_public_outbox_languages() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://example",
        PUBLIC_OUTBOX_LANGUAGES="zh-Hant,en,th,ja",
        PUBLIC_OUTBOX_DEFAULT_LANGUAGE="en",
    )

    assert settings.public_outbox_languages == ("zh-Hant", "en", "th", "ja")


def test_settings_reject_invalid_backfill_mode() -> None:
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="postgresql://example", EVENT_ROUTER_BACKFILL_MODE="bad")


def test_settings_reject_duplicate_public_outbox_languages() -> None:
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="postgresql://example", PUBLIC_OUTBOX_LANGUAGES="en,en")
