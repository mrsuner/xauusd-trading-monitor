"""Worker routing and accounting with real clients, mocked HTTP and an in-memory DB double."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from normalizer_classifier.model_client import build_model_client, build_translation_model_clients
from normalizer_classifier.taxonomy import TaxonomyContext
from normalizer_classifier.worker import NormalizerClassifierWorker
from test_model_client import make_objects
from test_ollama_cloud import classification, envelope, settings
from test_translation_runtime import result as translations


def make_worker(**overrides):
    config = settings(**(dict(TRANSLATION_MODEL_PROVIDER="ollama_cloud", TRANSLATION_FALLBACK_PROVIDER="openrouter",
                             TRANSLATION_PAID_FALLBACK_ENABLED=True, TRANSLATION_FALLBACK_MODEL_NAME="router-fallback")
                         | overrides))
    db = SimpleNamespace(**{name: AsyncMock() for name in (
        "reserve_ai_request", "update_translation_result", "insert_ai_model_call",
        "update_translation_failed", "update_translation_skipped",
    )})
    db.reserve_ai_request.return_value = True
    worker = NormalizerClassifierWorker(config, db, build_model_client(config), build_translation_model_clients(config))
    raw, source, normalized = make_objects()
    return worker, db, SimpleNamespace(raw_item=raw, source=source), normalized


@pytest.mark.parametrize("failure", ["success", "timeout", "connection", "rate_limit", "server", "invalid_output", "auth", "bad_request"])
async def test_translation_fallback_and_attempt_usage(monkeypatch, failure):
    worker, db, task, normalized = make_worker()
    requests = []

    async def fake_post(http, url, **kwargs):
        requests.append(url)
        if "ollama.com" in url:
            if failure == "timeout":
                raise httpx.ReadTimeout("timed out")
            if failure == "connection":
                raise httpx.ConnectError("unavailable")
            status = {"rate_limit": 429, "server": 503, "auth": 401, "bad_request": 400}.get(failure, 200)
            body = envelope(translations().model_dump()) if failure != "invalid_output" else envelope({"translations": []})
            return httpx.Response(status, json=body, request=httpx.Request("POST", url))
        return httpx.Response(200, json=envelope(translations().model_dump()), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    should_fallback = failure in {"timeout", "connection", "rate_limit", "server", "invalid_output"}
    assert len(requests) == (2 if should_fallback else 1)
    assert db.reserve_ai_request.await_count == len(requests)
    assert db.insert_ai_model_call.await_count == len(requests)
    usage = [call.kwargs["usage"] for call in db.insert_ai_model_call.await_args_list]
    assert usage[0].provider == "ollama_cloud"
    assert usage[0].success is (failure == "success")
    if should_fallback:
        assert usage[1].provider == "openrouter"
        assert usage[1].success is True
        db.update_translation_result.assert_awaited_once()
    elif failure == "success":
        db.update_translation_failed.assert_not_awaited()
    else:
        db.update_translation_result.assert_not_awaited()
        assert db.update_translation_failed.await_args.kwargs["provider"] == "translation_primary"
        assert db.update_translation_failed.await_args.kwargs["model"] == "test-cloud-translator"


@pytest.mark.parametrize("budget", ["daily_primary", "daily_fallback", "per_run", "fallback_per_run"])
async def test_budget_prevents_unreserved_api_calls(monkeypatch, budget):
    worker, db, task, normalized = make_worker(MAX_TRANSLATION_CALLS_PER_RUN=1 if budget == "per_run" else 0,
                                              MAX_TRANSLATION_PAID_FALLBACK_CALLS_PER_RUN=1)
    if budget == "fallback_per_run":
        worker._translation_paid_fallback_call_count = 1
    if budget == "daily_primary":
        db.reserve_ai_request.return_value = False
    elif budget == "daily_fallback":
        db.reserve_ai_request.side_effect = [True, False]
    calls = []

    async def fake_post(http, url, **kwargs):
        calls.append(url)
        raise httpx.ReadTimeout("test timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == (0 if budget == "daily_primary" else 1)
    assert db.insert_ai_model_call.await_count == len(calls)
    if calls:
        assert db.update_translation_failed.await_args.kwargs["model"] == "test-cloud-translator"
    else:
        db.update_translation_failed.assert_not_awaited()
        assert db.update_translation_skipped.await_args.kwargs["reason"] == "translation_call_budget_reached"


async def test_both_failures_are_recorded_and_last_attempt_is_attributed(monkeypatch):
    worker, db, task, normalized = make_worker()

    async def fake_post(http, url, **kwargs):
        return httpx.Response(503, json={"error": "unavailable"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert [call.kwargs["usage"].provider for call in db.insert_ai_model_call.await_args_list] == ["ollama_cloud", "openrouter"]
    assert db.update_translation_failed.await_args.kwargs["provider"] == "translation_paid_fallback"
    assert db.update_translation_failed.await_args.kwargs["model"] == "router-fallback"


async def test_unexpected_failure_does_not_trigger_another_provider(monkeypatch):
    worker, db, task, normalized = make_worker()
    first, second = worker.translation_model_clients
    first.summarize_and_translate = AsyncMock(side_effect=RuntimeError("unexpected"))
    second.summarize_and_translate = AsyncMock()
    await worker._run_translation_summary(task, normalized)
    second.summarize_and_translate.assert_not_awaited()
    db.update_translation_failed.assert_awaited_once()


async def test_budget_store_unavailable_does_not_call_provider():
    worker, db, task, normalized = make_worker()
    db.reserve_ai_request.side_effect = RuntimeError("db unavailable")
    for client in worker.translation_model_clients:
        client.summarize_and_translate = AsyncMock()
    await worker._run_translation_summary(task, normalized)
    for client in worker.translation_model_clients:
        client.summarize_and_translate.assert_not_awaited()
    db.update_translation_skipped.assert_awaited_once()


async def test_classification_is_persisted_before_translation_and_survives_failure(monkeypatch):
    worker, db, task, normalized = make_worker()
    task.id = "processing-id"
    task.attempt_count = 0
    events = []
    routing = SimpleNamespace(prompt_modules=lambda domains: [], domains=[SimpleNamespace(key="geopolitics")])
    db.claim_next_task = AsyncMock(return_value=task)
    db.get_routing_context = AsyncMock(return_value=routing)
    db.get_taxonomy_context = AsyncMock(return_value=TaxonomyContext())
    db.update_normalized_item = AsyncMock()
    db.mark_failed = AsyncMock()

    async def complete(**kwargs):
        events.append("classification_persisted")
        return "event-id"

    async def failed(**kwargs):
        events.append("translation_failed")
        worker._stop_event.set()

    db.complete_processed = AsyncMock(side_effect=complete)
    db.update_translation_failed.side_effect = failed
    monkeypatch.setattr("normalizer_classifier.worker.normalize_item", lambda *args: normalized)

    async def fake_post(http, url, **kwargs):
        if kwargs["json"]["model"] == "openai/gpt-6-luna":
            events.append("classification_called")
            return httpx.Response(200, json=envelope(classification()), request=httpx.Request("POST", url))
        assert "classification_persisted" in events
        events.append("translation_called")
        return httpx.Response(401, json={"error": "test"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._loop(0)
    assert events == ["classification_called", "classification_persisted", "translation_called", "translation_failed"]
    db.complete_processed.assert_awaited_once()
    db.mark_failed.assert_not_awaited()
    assert [call.kwargs["usage"].ai_layer for call in db.insert_ai_model_call.await_args_list] == [
        "classification_reasoning", "translation_summary"]
