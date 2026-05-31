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
