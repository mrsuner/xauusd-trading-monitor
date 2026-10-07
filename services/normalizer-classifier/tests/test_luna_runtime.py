"""Luna worker request contracts, without paid API calls or database writes."""
from decimal import Decimal

import pytest

from normalizer_classifier.model_client import (
    OpenAIStyleModelClient,
    build_model_client,
    build_translation_model_clients,
    classification_json_schema_response_format,
)
from normalizer_classifier.settings import Settings
from normalizer_classifier.taxonomy import CategoryOption, TaxonomyContext
from normalizer_classifier.usage import estimated_cost_usd
from test_model_client import make_objects
from test_translation_runtime import result


def settings(**overrides):
    return Settings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        CLOUD_MODEL_API_KEY="test-key",
        TRANSLATION_MODEL_API_KEY="test-key",
        TRANSLATION_OUTPUT_LANGUAGES="zh-Hant,en,th,ja",
        **overrides,
    )


def assert_luna_payload(payload):
    assert payload["model"] == "openai/gpt-6-luna"
    assert "temperature" not in payload
    assert "reasoning_effort" not in payload
    assert payload["reasoning"] == {"enabled": False}
    assert payload["provider"] == {
        "sort": "price", "require_parameters": True,
        "max_price": {"prompt": 0.10, "completion": 0.50},
    }


async def test_luna_classification_uses_strict_schema_and_price_routing(monkeypatch):
    client = build_model_client(settings())

    async def fake_post(payload, **kwargs):
        assert_luna_payload(payload)
        response_format = payload["response_format"]
        assert response_format["type"] == "json_schema"
        schema = response_format["json_schema"]
        assert schema["strict"] is True
        assert schema["schema"]["properties"]["primary_domain"]["enum"] == ["geopolitics", None]
        assert schema["schema"]["properties"]["relevant_domains"]["items"]["enum"] == ["geopolitics"]
        assert schema["schema"]["properties"]["content_category"]["enum"] == ["diplomacy", "other"]
        return {"choices": [{"message": {"content": '{"is_relevant": false, "relevance_score": 20, '
            '"event_type": "OTHER", "claim_direction": "neutral", '
            '"summaries": [{"language": "zh-Hant", "summary": "測試新聞。"}], '
            '"primary_domain": null, "relevant_domains": [], "requires_confirmation": true}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100}}

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    response = await client.classify(*make_objects(), enabled_domain_keys=["geopolitics"],
        taxonomy_context=TaxonomyContext(categories=[CategoryOption(key="diplomacy", label_en="Diplomacy")]))
    assert response.result.relevance_score == 20
    assert response.usage.provider == "openrouter"
    assert settings().relevance_threshold_event == 70


async def test_luna_translates_all_four_languages_without_model_fallback(monkeypatch):
    client, = build_translation_model_clients(settings())

    async def fake_post(payload, **kwargs):
        import json

        assert_luna_payload(payload)
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["response_format"]["json_schema"]["schema"]["properties"]["translations"]["minItems"] == 4
        return {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(result().model_dump())}}]}

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    response = await client.summarize_and_translate(*make_objects())
    assert {row.language for row in response.result.translations} == {"zh-Hant", "en", "th", "ja"}


def test_non_openrouter_clients_do_not_receive_provider_options():
    client = build_model_client(settings(CLOUD_MODEL_BASE_URL="https://api.example.test/v1"))
    assert client.api_provider != "openrouter"
    payload = {"temperature": 0}
    client._apply_common_payload_options(payload, classification_json_schema_response_format())
    assert payload["reasoning_effort"] == "none"
    assert "provider" not in payload


def test_legacy_model_keeps_supported_temperature():
    client = OpenAIStyleModelClient(provider="test", base_url="https://api.example.test/v1",
        api_key="test", model="test-model", timeout_seconds=5, response_format="json_object")
    payload = {"temperature": 0}
    client._apply_common_payload_options(payload, classification_json_schema_response_format())
    assert payload["temperature"] == 0


@pytest.mark.parametrize("key", ["CLOUD_MODEL_MAX_PROMPT_PRICE", "CLOUD_MODEL_MAX_COMPLETION_PRICE"])
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_classification_price_caps_are_positive_finite(key, value):
    with pytest.raises(ValueError):
        settings(**{key: value})


def test_luna_usage_estimate_uses_standard_tier_price():
    assert estimated_cost_usd("openrouter", "openai/gpt-6-luna", 1000, 1000) == Decimal("0.0006")
