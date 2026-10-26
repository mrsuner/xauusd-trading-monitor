"""Offline env/Compose admission: no containers, private env files, DBs, or model APIs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from dotenv import dotenv_values
import pytest

from normalizer_classifier.model_client import build_model_client, build_translation_model_clients
from normalizer_classifier.settings import Settings
from test_ollama_cloud import settings

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("route", ["local_8b", "local", "claude_code_agent", "unknown"])
def test_retired_or_unsupported_route_fails_before_any_client_is_built(route):
    with pytest.raises(ValueError, match="MODEL_ROUTE"):
        settings(MODEL_ROUTE=route)


def test_local_model_fields_are_retired():
    assert not any(name.startswith("local_model_") for name in Settings.model_fields)


@pytest.mark.parametrize("example", ["infra/.env.example", "infra/.env.dev.example", "services/normalizer-classifier/.env.example"])
def test_public_env_samples_preserve_openrouter_defaults(example):
    path = ROOT / example
    text = path.read_text()
    assert "LOCAL_MODEL_" not in text
    assert "local_8b" not in text
    values = dict(dotenv_values(path, interpolate=False))
    config = Settings(**(values | {"DATABASE_URL": "postgresql://unused/unused",
                                  "CLOUD_MODEL_API_KEY": "fixture", "TRANSLATION_MODEL_API_KEY": "fixture"}))
    assert build_model_client(config).api_provider == "openrouter"
    assert [client.api_provider for client in build_translation_model_clients(config)] == ["openrouter"]
    assert config.translation_fallback_provider is None
    assert config.cloud_model_timeout_seconds is None
    assert config.translation_model_timeout_seconds is None
    assert config.translation_full_source_tokens == 2500
    assert config.ai_max_source_tokens == 8000
    assert config.ai_item_token_limit == 30000
    assert config.ai_daily_token_limit == 5000000


def compose_environment(overrides):
    compose = ROOT / "infra/docker-compose.prod.yml"
    # Remove interpolation inputs inherited from a developer shell. Read only the
    # public example, and inject non-secret fixtures for each selected scenario.
    names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", compose.read_text()))
    env = {key: value for key, value in os.environ.items() if key not in names}
    env.update(overrides)
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(ROOT / "infra/.env.example"),
         "-f", str(compose), "config", "--format", "json"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["services"]["normalizer-classifier"]["environment"]


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker CLI is required for offline Compose parsing")
@pytest.mark.parametrize("provider", ["openrouter", "ollama_cloud"])
def test_compose_passes_provider_settings_to_worker(provider):
    overrides = {}
    if provider == "ollama_cloud":
        overrides = {
            "CLASSIFICATION_MODEL_PROVIDER": "ollama_cloud", "TRANSLATION_MODEL_PROVIDER": "ollama_cloud",
            "OLLAMA_API_KEY": "fixture-cloud-key", "OLLAMA_CLOUD_CLASSIFICATION_MODEL": "fixture-classifier",
            "OLLAMA_CLOUD_TRANSLATION_MODEL": "fixture-translator",
            "OLLAMA_CLOUD_CLASSIFICATION_TIMEOUT_SECONDS": "71", "OLLAMA_CLOUD_TRANSLATION_TIMEOUT_SECONDS": "89",
            "OLLAMA_CLOUD_CLASSIFICATION_REASONING_EFFORT": "low", "OLLAMA_CLOUD_TRANSLATION_REASONING_EFFORT": "high",
            "TRANSLATION_FALLBACK_PROVIDER": "openrouter", "TRANSLATION_PAID_FALLBACK_ENABLED": "true",
            "TRANSLATION_FALLBACK_MODEL_NAME": "fixture-fallback",
            "CLOUD_MODEL_TIMEOUT_SECONDS": "41", "TRANSLATION_MODEL_TIMEOUT_SECONDS": "47",
        }
    values = compose_environment(overrides)
    assert not any(key.startswith("LOCAL_MODEL_") for key in values)
    config = Settings(**values)
    classifier = build_model_client(config)
    translators = build_translation_model_clients(config)
    assert classifier.api_provider == translators[0].api_provider == provider
    assert classifier.max_input_tokens == translators[0].max_input_tokens == 16000
    assert classifier.max_output_tokens == 2048
    assert translators[0].max_output_tokens == 10000
    assert translators[0].summary_output_tokens == 1500
    assert config.translation_full_source_tokens == 2500
    assert config.ai_max_source_tokens == 8000
    assert config.ai_item_token_limit == 30000
    assert config.ai_daily_token_limit == 5000000
    if provider == "ollama_cloud":
        assert classifier.timeout_seconds == 71
        assert classifier.reasoning_effort == "low"
        assert classifier.model == "fixture-classifier"
        assert translators[0].timeout_seconds == 89
        assert translators[0].reasoning_effort == "high"
        assert translators[1].api_provider == "openrouter"
        assert translators[1].timeout_seconds == 47
    else:
        assert len(translators) == 1
        assert classifier.timeout_seconds == translators[0].timeout_seconds == 30


@pytest.mark.parametrize("provider", ["openrouter", "ollama_cloud"])
def test_blank_fallback_provider_inherits_primary(provider):
    config = settings(TRANSLATION_MODEL_PROVIDER=provider, TRANSLATION_FALLBACK_PROVIDER="",
                      TRANSLATION_PAID_FALLBACK_ENABLED=True, TRANSLATION_FALLBACK_MODEL_NAME="fixture-fallback")
    assert [client.api_provider for client in build_translation_model_clients(config)] == [provider, provider]


def test_blank_openrouter_timeouts_inherit_global_timeout():
    config = settings(CLOUD_MODEL_TIMEOUT_SECONDS="", TRANSLATION_MODEL_TIMEOUT_SECONDS=" ", MODEL_TIMEOUT_SECONDS=54)
    assert build_model_client(config).timeout_seconds == 54
    assert build_translation_model_clients(config)[0].timeout_seconds == 54
