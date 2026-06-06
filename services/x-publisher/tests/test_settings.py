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


def test_settings_parse_semantic_dedupe_model_config() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x:y@localhost/db",
        X_SEMANTIC_DEDUPE_ENABLED="true",
        X_SEMANTIC_DEDUPE_MODEL_BASE_URL="https://model.test/v1/",
        X_SEMANTIC_DEDUPE_MODEL_API_KEY="change-me",
        TRANSLATION_MODEL_API_KEY="translation-key",
        TRANSLATION_PRIMARY_MODEL_NAME="translation-model",
    )

    assert settings.semantic_dedupe_enabled is True
    assert settings.semantic_dedupe_model_base_url == "https://model.test/v1"
    assert settings.semantic_dedupe_model_api_key is None
    assert settings.translation_model_api_key == "translation-key"
    assert settings.translation_primary_model_name == "translation-model"


def test_settings_validate_semantic_dedupe_threshold() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql://x:y@localhost/db", X_SEMANTIC_DEDUPE_THRESHOLD=101)
