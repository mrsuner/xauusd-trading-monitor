"""Regressions found while reviewing the cloud-provider refactor; all I/O is mocked."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
import time

import httpx
import pytest

from normalizer_classifier.model_client import build_model_client, build_translation_model_clients
from normalizer_classifier.model_contracts import ModelClientError
from normalizer_classifier.model_tasks import classification_json_schema_response_format
from normalizer_classifier.taxonomy import TaxonomyContext
from normalizer_classifier import usage
from test_model_client import make_objects
from test_ollama_cloud import classification, envelope, settings
from test_translation_runtime import result as translations
from test_worker_model_providers import make_worker


@pytest.mark.parametrize("failure", ["classification_usage", "translation_usage", "translation_result", "translation_failure_usage"])
async def test_post_classification_storage_failure_never_requeues_or_erases_results(monkeypatch, failure):
    worker, db, task, normalized = make_worker()
    task.id = "processing-id"
    task.attempt_count = 0
    db.claim_next_task = AsyncMock(return_value=task)
    db.get_routing_context = AsyncMock(return_value=SimpleNamespace(prompt_modules=lambda domains: [], domains=[]))
    db.get_taxonomy_context = AsyncMock(return_value=TaxonomyContext())
    db.update_normalized_item = AsyncMock()
    db.complete_processed = AsyncMock(return_value="event-id")
    db.mark_failed = AsyncMock()
    monkeypatch.setattr("normalizer_classifier.worker.normalize_item", lambda *args: normalized)
    monkeypatch.setattr(usage, "estimate_messages_tokens", lambda *args: 12)
    monkeypatch.setattr(usage, "estimate_text_tokens", lambda *args: 7)

    def fail():
        worker._stop_event.set()
        raise RuntimeError("fixture DB write unavailable")

    async def store_usage(**kwargs):
        layer = kwargs["usage"].ai_layer
        if (failure == "classification_usage" and layer == "classification_reasoning"
                or failure in {"translation_usage", "translation_failure_usage"} and layer == "translation_summary"):
            fail()

    async def store_translation(**kwargs):
        if failure == "translation_result":
            fail()

    db.insert_ai_model_call.side_effect = store_usage
    db.update_translation_result.side_effect = store_translation

    async def fake_post(http, url, **kwargs):
        if kwargs["json"]["model"] == "openai/gpt-6-luna":
            value = classification()
        elif failure == "translation_failure_usage":
            return httpx.Response(401, json={"error": "fixture"}, request=httpx.Request("POST", url))
        else:
            value = translations().model_dump()
        return httpx.Response(200, json=envelope(value), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._loop(0)
    db.complete_processed.assert_awaited_once()
    db.mark_failed.assert_not_awaited()
    db.update_translation_failed.assert_not_awaited()
    assert db.claim_next_task.await_count == 1


@pytest.mark.parametrize("provider", ["openrouter", "ollama_cloud"])
@pytest.mark.parametrize("missing", ["summary", "full_translation"])
async def test_partial_language_policy_still_requires_complete_present_languages(monkeypatch, provider, missing):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER=provider, TRANSLATION_REQUIRE_ALL_LANGUAGES=False))
    value = translations().model_dump()
    value["translations"] = [value["translations"][0]]
    value["translations"][0][missing] = None

    async def fake_post(payload, **kwargs):
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError, match="incomplete languages") as caught:
        await client.summarize_and_translate(*make_objects())
    assert caught.value.usage.success is False


@pytest.mark.parametrize("provider", ["openrouter", "ollama_cloud"])
async def test_partial_language_policy_accepts_a_complete_subset(monkeypatch, provider):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER=provider, TRANSLATION_REQUIRE_ALL_LANGUAGES=False))
    value = translations().model_dump()
    value["translations"] = [value["translations"][0]]

    async def fake_post(payload, **kwargs):
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    response = await client.summarize_and_translate(*make_objects())
    assert response.usage.success is True


@pytest.mark.parametrize("finish,refusal", [("length", None), ("content_filter", None), ("stop", "Refused")])
async def test_openrouter_classification_rejects_incomplete_or_refused_valid_json(monkeypatch, finish, refusal):
    client = build_model_client(settings())
    body = envelope(classification())
    body["choices"][0]["finish_reason"] = finish
    body["choices"][0]["message"]["refusal"] = refusal

    async def fake_post(payload, **kwargs):
        return body

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError) as caught:
        await client.classify(*make_objects())
    assert caught.value.usage.success is False
    assert caught.value.usage.input_tokens == 100


@pytest.mark.parametrize("provider", ["openrouter", "ollama_cloud"])
async def test_no_enabled_categories_only_allows_other(monkeypatch, provider):
    client = build_model_client(settings(CLASSIFICATION_MODEL_PROVIDER=provider))
    value = classification()
    value["content_category"] = "disabled-category"

    async def fake_post(payload, **kwargs):
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError, match="disabled or unknown category"):
        await client.classify(*make_objects(), taxonomy_context=TaxonomyContext())


def test_empty_taxonomy_schema_matches_response_validation():
    schema = classification_json_schema_response_format(enabled_domain_keys=[], enabled_category_keys=[])["json_schema"]["schema"]
    props = schema["properties"]
    assert props["content_category"]["enum"] == ["other"]
    assert props["primary_domain"]["enum"] == [None]
    assert props["relevant_domains"]["maxItems"] == 0


@pytest.mark.parametrize("failure_stage", ["input", "output"])
def test_usage_estimation_failure_does_not_hide_the_model_attempt(monkeypatch, failure_stage):
    def unavailable(*args):
        raise OSError("fixture tokenizer unavailable")
    monkeypatch.setattr(usage, "estimate_messages_tokens", unavailable if failure_stage == "input" else lambda *args: 12)
    monkeypatch.setattr(usage, "estimate_text_tokens", unavailable if failure_stage == "output" else lambda *args: 7)
    record = usage.build_model_call_usage(route_name="cloud_small", api_provider="openrouter", model="openai/gpt-6-luna",
        response_format="json_schema", payload={"messages": []}, ai_layer="classification_reasoning",
        request_kind="classify_raw_item", started=time.perf_counter(), success=False,
        output_text="fixture output", error=ValueError("original model response invalid"))
    assert record.error_type == "ValueError"
    assert record.success is False
    assert record.input_tokens == (None if failure_stage == "input" else 12)
    assert record.output_tokens == (None if failure_stage == "output" else 7)
    assert record.total_tokens is None
    assert record.estimated_cost_usd is None
    assert record.usage_json["estimation_errors"]


def test_unknown_completion_usage_is_not_billed_as_zero():
    assert usage.estimated_cost_usd("openrouter", "openai/gpt-6-luna", 12, None) is None


async def test_refused_response_without_completion_usage_remains_unknown(monkeypatch):
    client = build_model_client(settings())
    body = envelope(classification())
    body["choices"][0]["finish_reason"] = "length"
    body["usage"] = {"prompt_tokens": 100}

    async def fake_post(payload, **kwargs):
        return body

    def unexpected_estimate(*args):
        raise AssertionError("There is no accepted final answer to estimate")

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    monkeypatch.setattr(usage, "estimate_text_tokens", unexpected_estimate)
    with pytest.raises(ModelClientError) as caught:
        await client.classify(*make_objects())
    assert caught.value.usage.input_tokens == 100
    assert caught.value.usage.output_tokens is None
    assert caught.value.usage.total_tokens is None
    assert caught.value.usage.estimated_cost_usd is None
    assert "estimation_errors" not in caught.value.usage.usage_json
