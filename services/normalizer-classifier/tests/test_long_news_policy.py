import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from normalizer_classifier.db import aggregate_raw_item_translation_status
from normalizer_classifier.model_contracts import ModelClientError
from normalizer_classifier.taxonomy import TaxonomyContext
from test_ollama_cloud import envelope
from test_translation_runtime import result
from test_translation_script_repair import incident
from test_worker_model_providers import make_worker


@pytest.mark.parametrize("tokens,mode", [(2499, "full"), (2500, "full"), (2501, "summary"),
    (7999, "summary"), (8000, "summary"), (8001, "skipped")])
@pytest.mark.parametrize("source_type", ["telegram", "rss", "html_polling"])
async def test_source_boundary_is_independent_of_source_type(monkeypatch, tokens, mode, source_type):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False)
    task.source.source_type = source_type
    task.source.always_full_translate = True
    monkeypatch.setattr("normalizer_classifier.worker.source_tokens", lambda text: tokens)
    calls = []

    async def post(http, url, **kwargs):
        payload = kwargs["json"]
        calls.append(payload)
        scope = json.loads(payload["messages"][1]["content"])["translation_scope"]
        assert scope["full_translation_required"] is (mode == "full")
        value = result().model_dump()
        if mode == "summary":
            for row in value["translations"]:
                row["full_translation"] = None
        return httpx.Response(200, json=envelope(value), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    if mode == "skipped":
        assert not calls
        db.reserve_ai_request.assert_not_awaited()
        db.reserve_ai_tokens.assert_not_awaited()
        assert db.update_translation_skipped.await_args.kwargs["reason"] == "source_token_limit_exceeded"
    else:
        assert len(calls) == 1
        assert calls[0]["max_tokens"] == (10000 if mode == "full" else 1500)
        saved = db.update_translation_result.await_args.kwargs
        assert saved["status"] == ("completed" if mode == "full" else "summary_only")
        if mode == "summary":
            assert all(row.full_translation is None for row in saved["response"].result.translations)


@pytest.mark.parametrize("policy,always", [("summary_only", False), ("summary_only", True), ("disabled", True)])
async def test_source_policy_cannot_be_upgraded_by_priority(monkeypatch, policy, always):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False)
    task.source.translation_policy, task.source.always_full_translate = policy, always
    calls = []

    async def post(http, url, **kwargs):
        calls.append(kwargs["json"])
        value = result().model_dump()
        for row in value["translations"]:
            row["full_translation"] = None
        return httpx.Response(200, json=envelope(value), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == (0 if policy == "disabled" else 1)
    if calls:
        assert db.update_translation_result.await_args.kwargs["status"] == "summary_only"


async def test_summary_mode_rejects_accidental_full_text(monkeypatch):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False)
    monkeypatch.setattr("normalizer_classifier.worker.source_tokens", lambda text: 2501)
    calls = []

    async def post(http, url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=envelope(result().model_dump()), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == 1
    db.update_translation_result.assert_not_awaited()
    assert "summary-only mode" in db.update_translation_failed.await_args.kwargs["error_message"]


@pytest.mark.parametrize("reason", ["item_token_budget_reached", "daily_token_budget_reached", "store_unavailable"])
async def test_script_repair_requires_fresh_shared_tokens(monkeypatch, reason):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=True)
    db.reserve_ai_tokens.side_effect = [None, RuntimeError("fixture") if reason == "store_unavailable" else reason]
    calls = []

    async def post(http, url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=envelope(incident()), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == db.insert_ai_model_call.await_count == 1
    assert db.reserve_ai_tokens.await_count == 2
    db.update_translation_result.assert_not_awaited()
    db.update_translation_failed.assert_awaited_once()


async def test_old_character_limit_does_not_silently_truncate_translation(monkeypatch):
    worker, db, task, normalized = make_worker(TRANSLATION_SINGLE_CALL_MAX_CHARS=5)
    post = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    post.assert_not_awaited()
    assert db.update_translation_skipped.await_args.kwargs["reason"] == "translation_input_char_limit_exceeded"


@pytest.mark.parametrize("case,reason", [("source", "source_token_limit_exceeded"),
    ("input", "request_input_token_limit_exceeded"), ("item", "item_token_budget_reached"),
    ("daily", "daily_token_budget_reached"), ("store", "token_budget_store_unavailable")])
async def test_worker_blocks_before_classification_and_uses_correct_state(monkeypatch, case, reason):
    worker, db, task, normalized = make_worker(AI_MAX_INPUT_TOKENS=1 if case == "input" else 16000)
    task.id, task.attempt_count = "processing", 0
    db.claim_next_task = AsyncMock(return_value=task)
    db.get_routing_context = AsyncMock(return_value=SimpleNamespace(prompt_modules=lambda domains: [],
        domains=[SimpleNamespace(key="geopolitics")]))
    db.get_taxonomy_context = AsyncMock(return_value=TaxonomyContext())
    db.update_normalized_item = AsyncMock()
    db.complete_processed = AsyncMock()
    db.mark_failed = AsyncMock()

    async def stop(**kwargs):
        worker._stop_event.set()

    db.complete_skipped = AsyncMock(side_effect=stop)
    db.defer_for_model_budget = AsyncMock(side_effect=stop)
    if case == "source":
        monkeypatch.setattr("normalizer_classifier.worker.source_tokens", lambda text: 8001)
    elif case in {"item", "daily"}:
        db.reserve_ai_tokens.return_value = reason
    elif case == "store":
        db.reserve_ai_tokens.side_effect = RuntimeError("fixture")
    post = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    monkeypatch.setattr("normalizer_classifier.worker.normalize_item", lambda *args: normalized)
    await worker._loop(0)
    post.assert_not_awaited()
    db.complete_processed.assert_not_awaited()
    db.mark_failed.assert_not_awaited()
    if case in {"daily", "store"}:
        assert db.defer_for_model_budget.await_args.kwargs["reason"] == reason
    else:
        assert db.complete_skipped.await_args.kwargs["normalized"].filter_reason == reason


def test_summary_only_aggregation_does_not_claim_full_completion():
    assert aggregate_raw_item_translation_status(["summary_only"] * 4) == "summary_only"
    assert aggregate_raw_item_translation_status(["summary_only", "failed"]) == "partial_completed"
    assert aggregate_raw_item_translation_status(["summary_only", "completed"]) == "partial_completed"
