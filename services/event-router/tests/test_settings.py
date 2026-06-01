from __future__ import annotations

import pytest

from event_router.settings import Settings


def test_settings_validate_backfill_mode() -> None:
    settings = Settings(DATABASE_URL="postgresql://example", EVENT_ROUTER_BACKFILL_MODE="telegram_only")

    assert settings.backfill_mode == "telegram_only"


def test_settings_reject_invalid_backfill_mode() -> None:
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="postgresql://example", EVENT_ROUTER_BACKFILL_MODE="bad")
