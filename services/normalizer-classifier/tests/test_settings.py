from __future__ import annotations

import pytest
from pydantic import ValidationError

from normalizer_classifier.settings import Settings


def test_settings_accepts_model_call_budget() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        MAX_MODEL_CALLS_PER_RUN="20",
        CLOUD_MODEL_API_KEY="test-key",
    )

    assert settings.max_model_calls_per_run == 20


def test_settings_rejects_negative_model_call_budget() -> None:
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            MAX_MODEL_CALLS_PER_RUN="-1",
            CLOUD_MODEL_API_KEY="test-key",
        )


def test_settings_accepts_openrouter_auxiliary_route() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        AUXILIARY_MODEL_ENABLED="true",
        AUXILIARY_MODEL_ROUTE="openrouter_free",
        OPENROUTER_MODEL_API_KEY="openrouter-key",
        OPENROUTER_MODEL_NAME="free-summary-model",
        OPENROUTER_MODEL_RESPONSE_FORMAT="json_object",
    )

    assert settings.auxiliary_model_enabled is True
    assert settings.auxiliary_model_route == "openrouter_free"
    assert settings.openrouter_model_base_url == "https://openrouter.ai/api/v1"


def test_settings_accepts_translation_model_defaults() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        OPENROUTER_MODEL_API_KEY="openrouter-key",
    )

    assert settings.translation_model_enabled is True
    assert settings.translation_primary_model_name == "openai/gpt-oss-20b:free"
    assert settings.translation_fallback_model_name == "openai/gpt-oss-20b"
    assert settings.translation_paid_fallback_enabled is True
    assert settings.translation_high_priority_max_chars == 100000
    assert settings.translation_output_languages == ("zh-Hant", "en")
    assert settings.translation_require_all_languages is True


def test_settings_accepts_configured_translation_languages() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        TRANSLATION_OUTPUT_LANGUAGES="zh-Hant,en,th,ja",
        TRANSLATION_LANGUAGE_LABELS_JSON='{"zh-Hant":"Traditional Chinese","en":"English","th":"Thai","ja":"Japanese"}',
        TRANSLATION_REQUIRE_ALL_LANGUAGES="false",
    )

    assert settings.translation_output_languages == ("zh-Hant", "en", "th", "ja")
    assert settings.translation_language_labels["th"] == "Thai"
    assert settings.translation_require_all_languages is False


def test_settings_rejects_duplicate_translation_languages() -> None:
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            CLOUD_MODEL_API_KEY="test-key",
            TRANSLATION_OUTPUT_LANGUAGES="en,en",
        )


def test_settings_accepts_stale_task_timeout() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        STALE_TASK_TIMEOUT_SECONDS="1200",
    )

    assert settings.stale_task_timeout_seconds == 1200


def test_settings_accepts_db_pool_size() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        DB_POOL_MIN_SIZE="2",
        DB_POOL_MAX_SIZE="8",
    )

    assert settings.db_pool_min_size == 2
    assert settings.db_pool_max_size == 8


def test_settings_rejects_negative_db_pool_size() -> None:
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            CLOUD_MODEL_API_KEY="test-key",
            DB_POOL_MAX_SIZE="-1",
        )


def test_settings_rejects_short_stale_task_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            CLOUD_MODEL_API_KEY="test-key",
            STALE_TASK_TIMEOUT_SECONDS="30",
        )
