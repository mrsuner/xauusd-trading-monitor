"""Cloud wire contracts only: every HTTP request is mocked."""
from __future__ import annotations

import copy
import json
import logging

import httpx
import pytest

from normalizer_classifier.model_client import build_model_client, build_translation_model_clients
from normalizer_classifier.model_contracts import ModelClientError
from normalizer_classifier.models import ClassificationResult
from normalizer_classifier.ollama_cloud_client import OllamaCloudClient
from normalizer_classifier.openrouter_client import OpenRouterClient
from normalizer_classifier.settings import Settings
from normalizer_classifier.taxonomy import CategoryOption, TaxonomyContext
from test_model_client import make_objects
from test_translation_runtime import result as translations


def settings(**overrides):
    values = dict(DATABASE_URL="postgresql://unused/unused", CLOUD_MODEL_API_KEY="router-classification-key",
                  TRANSLATION_MODEL_API_KEY="router-translation-key", OLLAMA_API_KEY="cloud-key",
                  OLLAMA_CLOUD_CLASSIFICATION_MODEL="test-cloud-classifier",
                  OLLAMA_CLOUD_TRANSLATION_MODEL="test-cloud-translator", TRANSLATION_OUTPUT_LANGUAGES="zh-Hant,en,th,ja")
    return Settings(**(values | overrides))


def classification():
    return ClassificationResult.model_validate({
        "is_relevant": False, "relevance_score": 20, "primary_domain": None,
        "relevant_domains": [], "content_category": "other",
        "summaries": [{"language": "zh-Hant", "summary": "測試消息。"}],
    }).model_dump()


def envelope(value):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}}


@pytest.mark.parametrize("layer", ["classification", "translation"])
async def test_cloud_request_and_usage_are_independent(monkeypatch, caplog, layer):
    config = settings(CLASSIFICATION_MODEL_PROVIDER="ollama_cloud", TRANSLATION_MODEL_PROVIDER="ollama_cloud",
                      OLLAMA_CLOUD_CLASSIFICATION_TIMEOUT_SECONDS=73, OLLAMA_CLOUD_TRANSLATION_TIMEOUT_SECONDS=91,
                      OLLAMA_CLOUD_CLASSIFICATION_REASONING_EFFORT="low",
                      OLLAMA_CLOUD_TRANSLATION_REASONING_EFFORT="high",
                      TRANSLATION_HTTP_REFERER="https://router-only.test", TRANSLATION_APP_TITLE="Router only")
    client = build_model_client(config) if layer == "classification" else build_translation_model_clients(config)[0]
    calls = []

    async def fake_post(http, url, *, headers, json):
        calls.append(json)
        assert url == "https://ollama.com/v1/chat/completions"
        assert headers == {"Content-Type": "application/json", "Authorization": "Bearer cloud-key"}
        assert not ({"provider", "response_format", "format", "reasoning"} & json.keys())
        assert json["stream"] is False
        assert json["temperature"] == 0
        assert json["reasoning_effort"] == ("low" if layer == "classification" else "high")
        assert json["model"] == ("test-cloud-classifier" if layer == "classification" else "test-cloud-translator")
        assert http.timeout.read == (73 if layer == "classification" else 91)
        assert '"type":"object"' in json["messages"][0]["content"]
        assert '"additionalProperties":false' in json["messages"][0]["content"]
        expected = classification() if layer == "classification" else translations().model_dump()
        return httpx.Response(200, json=envelope(expected), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with caplog.at_level(logging.DEBUG, logger="normalizer_classifier.model_transport"):
        response = await (client.classify(*make_objects()) if layer == "classification"
                          else client.summarize_and_translate(*make_objects()))
    assert len(calls) == 1
    assert response.api_provider == response.usage.provider == "ollama_cloud"
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 30
    assert response.usage.estimated_cost_usd is None
    assert response.usage.response_format == "prompt_json_schema"
    assert response.usage.success is True
    request = next(record for record in caplog.records if record.message == "ai_model_api_request")
    assert request.headers["Authorization"] == "[REDACTED]"
    assert "cloud-key" not in caplog.text


@pytest.mark.parametrize("language,limit", [("zh-Hant", 280), ("en", 400)])
@pytest.mark.parametrize("extra", [0, 1])
async def test_cloud_summary_length_boundaries_still_apply(monkeypatch, language, limit, extra):
    client = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER="ollama_cloud"))[0]
    value = translations().model_dump()
    row = next(row for row in value["translations"] if row["language"] == language)
    row["summary"] = ("據" if language == "zh-Hant" else "a") * (limit + extra)
    calls = []

    async def fake_post(payload, **kwargs):
        calls.append(payload)
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    if extra:
        with pytest.raises(ModelClientError, match=f"summary too long: {language}") as caught:
            await client.summarize_and_translate(*make_objects())
        assert caught.value.usage.success is False
    else:
        response = await client.summarize_and_translate(*make_objects())
        assert response.result.translation_for(language).summary == row["summary"]
    assert len(calls) == 1
    assert len(row["summary"]) == limit + extra


@pytest.mark.parametrize("layer", ["classification", "translation"])
@pytest.mark.parametrize("failure", ["empty", "reasoning_only", "length", "refusal", "json", "fenced", "choices", "message", "content_type"])
async def test_cloud_rejects_invalid_answers_with_usage(monkeypatch, layer, failure):
    config = settings(CLASSIFICATION_MODEL_PROVIDER="ollama_cloud", TRANSLATION_MODEL_PROVIDER="ollama_cloud")
    client = build_model_client(config) if layer == "classification" else build_translation_model_clients(config)[0]
    body = envelope(classification() if layer == "classification" else translations().model_dump())
    choice = body["choices"][0]
    message = choice["message"]
    if failure == "empty":
        message["content"] = ""
    elif failure == "reasoning_only":
        message["reasoning_content"] = message.pop("content")
    elif failure == "length":
        choice["finish_reason"] = "length"
    elif failure == "refusal":
        message["refusal"] = "Refused"
    elif failure == "json":
        message["content"] = "not json"
    elif failure == "fenced":
        message["content"] = "```json\n" + message["content"] + "\n```"
    elif failure == "choices":
        body["choices"] = []
    elif failure == "message":
        choice["message"] = None
    else:
        message["content"] = {"answer": message["content"]}
    calls = []

    async def fake_post(payload, **kwargs):
        calls.append(payload)
        return body

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError) as caught:
        await (client.classify(*make_objects()) if layer == "classification"
               else client.summarize_and_translate(*make_objects()))
    assert len(calls) == 1
    assert caught.value.retryable is True
    assert caught.value.usage.success is False
    assert caught.value.usage.provider == "ollama_cloud"
    assert caught.value.usage.input_tokens == 100


@pytest.mark.parametrize("change", ["unknown_domain", "disabled_domains", "unknown_category"])
async def test_cloud_rejects_unknown_taxonomy(monkeypatch, change):
    client = build_model_client(settings(CLASSIFICATION_MODEL_PROVIDER="ollama_cloud"))
    value = classification()
    if change in {"unknown_domain", "disabled_domains"}:
        value["relevant_domains"] = ["unknown"]
    else:
        value["content_category"] = "unknown"

    async def fake_post(payload, **kwargs):
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError, match="disabled or unknown"):
        await client.classify(*make_objects(), enabled_domain_keys=[] if change == "disabled_domains" else ["geopolitics"],
                              taxonomy_context=TaxonomyContext(categories=[CategoryOption("diplomacy", "Diplomacy")]))


@pytest.mark.parametrize("failure", ["missing", "duplicate", "unsupported", "script", "long", "missing_full"])
async def test_cloud_reuses_translation_business_validation(monkeypatch, failure):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER="ollama_cloud"))
    value = translations().model_dump()
    rows = value["translations"]
    if failure == "missing":
        rows.pop()
    elif failure == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif failure == "unsupported":
        rows[3]["language"] = "de"
    elif failure == "script":
        rows[2]["summary"] = "English only."
    elif failure == "long":
        rows[0]["summary"] = "中" * 281
    else:
        rows[0]["full_translation"] = None

    async def fake_post(payload, **kwargs):
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError) as caught:
        await client.summarize_and_translate(*make_objects())
    assert caught.value.usage.success is False


@pytest.mark.parametrize("status,retryable", [(400, False), (401, False), (403, False), (404, False),
                                             (408, True), (429, True), (500, True), (503, True)])
async def test_http_failure_classification(monkeypatch, status, retryable):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER="ollama_cloud"))

    async def fake_post(http, url, **kwargs):
        return httpx.Response(status, json={"error": "test"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ModelClientError) as caught:
        await client.summarize_and_translate(*make_objects())
    assert caught.value.retryable is retryable
    assert caught.value.usage.success is False


@pytest.mark.parametrize("body", [None, [], "bad json", {"choices": None}, {"choices": []},
                                  {"choices": [{"message": {"content": "{}"}}], "usage": "bad"}])
async def test_malformed_envelopes_are_accounted(monkeypatch, body):
    client = build_model_client(settings(CLASSIFICATION_MODEL_PROVIDER="ollama_cloud"))

    async def fake_post(http, url, **kwargs):
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ModelClientError) as caught:
        await client.classify(*make_objects())
    assert caught.value.usage.success is False


@pytest.mark.parametrize("classification_provider,translation_provider", [
    ("openrouter", "openrouter"), ("ollama_cloud", "openrouter"),
    ("openrouter", "ollama_cloud"), ("ollama_cloud", "ollama_cloud"),
])
def test_layers_select_providers_independently(classification_provider, translation_provider):
    config = settings(CLASSIFICATION_MODEL_PROVIDER=classification_provider, TRANSLATION_MODEL_PROVIDER=translation_provider)
    assert build_model_client(config).api_provider == classification_provider
    assert build_translation_model_clients(config)[0].api_provider == translation_provider


@pytest.mark.parametrize("primary,fallback", [("openrouter", "ollama_cloud"), ("ollama_cloud", "openrouter"),
                                             ("openrouter", "openrouter"), ("ollama_cloud", "ollama_cloud")])
def test_translation_fallback_has_its_own_provider_configuration(primary, fallback):
    config = settings(TRANSLATION_MODEL_PROVIDER=primary, TRANSLATION_FALLBACK_PROVIDER=fallback,
                      TRANSLATION_PAID_FALLBACK_ENABLED=True, TRANSLATION_FALLBACK_MODEL_NAME="explicit-fallback",
                      TRANSLATION_MODEL_TIMEOUT_SECONDS=45, OLLAMA_CLOUD_TRANSLATION_TIMEOUT_SECONDS=80)
    first, second = build_translation_model_clients(config)
    assert [first.api_provider, second.api_provider] == [primary, fallback]
    assert second.model == "explicit-fallback"
    assert second.provider == "translation_paid_fallback"
    assert second.api_key == ("cloud-key" if fallback == "ollama_cloud" else "router-translation-key")
    assert second.timeout_seconds == (80 if fallback == "ollama_cloud" else 45)
    assert second.base_url == ("https://ollama.com/v1" if fallback == "ollama_cloud" else "https://openrouter.ai/api/v1")


@pytest.mark.parametrize("layer", ["classification", "translation"])
@pytest.mark.parametrize("missing", ["key", "model"])
def test_selected_cloud_route_requires_explicit_credentials_and_model(layer, missing):
    overrides = {f"{layer.upper()}_MODEL_PROVIDER": "ollama_cloud"}
    overrides["OLLAMA_API_KEY" if missing == "key" else f"OLLAMA_CLOUD_{layer.upper()}_MODEL"] = " "
    config = settings(**overrides)
    with pytest.raises(ValueError, match="required"):
        (build_model_client if layer == "classification" else build_translation_model_clients)(config)


def test_unused_cloud_credentials_are_not_required():
    config = settings(OLLAMA_API_KEY=None, OLLAMA_CLOUD_CLASSIFICATION_MODEL=None, OLLAMA_CLOUD_TRANSLATION_MODEL=None)
    assert isinstance(build_model_client(config), OpenRouterClient)
    assert isinstance(build_translation_model_clients(config)[0], OpenRouterClient)


@pytest.mark.parametrize("url", ["http://localhost:11434/v1", "https://example.test/v1", "https://ollama.com/api",
                                  "https://key@ollama.com/v1", "https://ollama.com/v1?token=test"])
def test_cloud_provider_only_targets_direct_cloud(url):
    with pytest.raises(ValueError, match="OLLAMA_CLOUD_BASE_URL"):
        OllamaCloudClient(provider="test", base_url=url, api_key="test", model="test", timeout_seconds=5)


@pytest.mark.parametrize("field", ["CLASSIFICATION_MODEL_PROVIDER", "TRANSLATION_MODEL_PROVIDER", "TRANSLATION_FALLBACK_PROVIDER"])
def test_unknown_provider_fails_fast(field):
    with pytest.raises(ValueError):
        settings(**{field: "unknown"})


@pytest.mark.parametrize("field", ["MODEL_TIMEOUT_SECONDS", "CLOUD_MODEL_TIMEOUT_SECONDS", "TRANSLATION_MODEL_TIMEOUT_SECONDS",
                                   "OLLAMA_CLOUD_CLASSIFICATION_TIMEOUT_SECONDS", "OLLAMA_CLOUD_TRANSLATION_TIMEOUT_SECONDS"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_timeout_must_be_positive_finite(field, value):
    with pytest.raises(ValueError):
        settings(**{field: value})


def test_disabled_translation_does_not_require_cloud_configuration():
    assert build_translation_model_clients(settings(TRANSLATION_MODEL_ENABLED=False,
        TRANSLATION_MODEL_PROVIDER="ollama_cloud", OLLAMA_API_KEY=None, OLLAMA_CLOUD_TRANSLATION_MODEL=None)) == []


def test_enabled_fallback_requires_model():
    with pytest.raises(ValueError, match="TRANSLATION_FALLBACK_MODEL_NAME"):
        build_translation_model_clients(settings(TRANSLATION_PAID_FALLBACK_ENABLED=True))
