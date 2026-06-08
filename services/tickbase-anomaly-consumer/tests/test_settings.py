from __future__ import annotations

import pytest

from tickbase_anomaly_consumer.settings import Settings

BASE_ENV = {"DATABASE_URL": "postgresql://localhost/test"}


def test_defaults(monkeypatch):
    for key in ("ANOMALY_CONSUMER_START", "TICKBASE_API_KEY", "ANOMALY_CONSUMER_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(**BASE_ENV)
    assert settings.start_mode == "tail"
    assert settings.start_id is None
    assert settings.enabled is False
    assert settings.api_key is None


def test_start_mode_numeric():
    settings = Settings(**BASE_ENV, ANOMALY_CONSUMER_START="42")
    assert settings.start_id == 42


def test_start_mode_invalid_rejected():
    with pytest.raises(ValueError):
        Settings(**BASE_ENV, ANOMALY_CONSUMER_START="bogus")


def test_severity_multiplier_must_be_at_least_one():
    with pytest.raises(ValueError):
        Settings(**BASE_ENV, ANOMALY_SEVERITY_B_MULTIPLIER="0.5")


def test_api_key_placeholder_normalized():
    settings = Settings(**BASE_ENV, TICKBASE_API_KEY="change-me")
    assert settings.api_key is None
