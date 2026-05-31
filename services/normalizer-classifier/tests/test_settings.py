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
