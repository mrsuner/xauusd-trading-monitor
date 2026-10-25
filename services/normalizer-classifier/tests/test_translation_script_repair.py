"""Replay the copied-English incident with mocked HTTP; never call a live API or DB."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from normalizer_classifier.model_client import build_translation_model_clients
from normalizer_classifier.model_contracts import ModelClientError, TranslationScriptError
from normalizer_classifier.model_tasks import validate_auxiliary_text_result
from normalizer_classifier.models import AuxiliaryTextResult
from normalizer_classifier.taxonomy import TaxonomyContext
from test_model_client import make_objects
from test_ollama_cloud import classification, envelope, settings
from test_worker_model_providers import make_worker


SOURCE = (
    "South Korean lawmakers oppose Hormuz deployment, demand policy review. "
    "Frank Smith reports from Seoul. @PressTV"
)
SCRIPT_FIELDS = ("zh-Hant.full_translation", "th.full_translation", "ja.full_translation")


def incident(*, repaired=False):
    rows = [
        {"language": "zh-Hant", "summary": "南韓議員反對荷姆茲部署，要求檢討政策。",
         "full_translation": "南韓議員反對荷姆茲部署，要求檢討政策。Frank Smith 自首爾報導。@PressTV"},
        {"language": "en", "summary": "South Korean lawmakers oppose Hormuz deployment and demand policy review.",
         "full_translation": SOURCE},
        {"language": "th", "summary": "สมาชิกรัฐสภาเกาหลีใต้คัดค้านการส่งกำลังไปฮอร์มุซ",
         "full_translation": "สมาชิกรัฐสภาเกาหลีใต้คัดค้านการส่งกำลังไปฮอร์มุซและเรียกร้องให้ทบทวนนโยบาย Frank Smith รายงานจากโซล @PressTV"},
        {"language": "ja", "summary": "韓国の議員がホルムズ派遣に反対し、政策見直しを要求。",
         "full_translation": "韓国の議員がホルムズ派遣に反対し、政策見直しを要求。Frank Smith がソウルから報告。@PressTV"},
    ]
    if not repaired:
        for row in rows:
            row["full_translation"] = SOURCE
    return {"translations": rows}


@pytest.mark.parametrize("field", ["summary", "full_translation"])
def test_script_validation_identifies_every_failed_locale_and_field(field):
    value = incident(repaired=True)
    for row in value["translations"]:
        if row["language"] != "en":
            row[field] = SOURCE
    with pytest.raises(TranslationScriptError) as caught:
        validate_auxiliary_text_result(AuxiliaryTextResult.model_validate(value),
            languages=("zh-Hant", "en", "th", "ja"), require_all_languages=True, full_translation_required=True)
    assert caught.value.fields == tuple(f"{lang}.{field}" for lang in ("zh-Hant", "th", "ja"))


def test_target_language_text_can_keep_english_names_and_handles():
    validate_auxiliary_text_result(AuxiliaryTextResult.model_validate(incident(repaired=True)),
        languages=("zh-Hant", "en", "th", "ja"), require_all_languages=True, full_translation_required=True)


async def test_client_reports_script_fields_without_hidden_retry(monkeypatch):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER="ollama_cloud"))
    calls = []

    async def fake_post(payload, **kwargs):
        calls.append(payload)
        return envelope(incident())

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    with pytest.raises(ModelClientError) as caught:
        await client.summarize_and_translate(*make_objects())
    assert len(calls) == 1
    assert caught.value.script_validation_fields == SCRIPT_FIELDS
    assert caught.value.usage.success is False
    assert caught.value.usage.error_type == "TranslationScriptError"
    for field in SCRIPT_FIELDS:
        assert field in caught.value.usage.error_message
    assert "Validate summary and full_translation independently" in calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("repaired", [True, False])
async def test_worker_repairs_once_and_records_each_attempt(monkeypatch, repaired):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False)
    task.raw_item.text_raw = normalized.text_clean = SOURCE
    calls = []

    async def fake_post(http, url, **kwargs):
        calls.append(copy.deepcopy(kwargs["json"]))
        return httpx.Response(200, json=envelope(incident(repaired=repaired and len(calls) == 2)),
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == db.reserve_ai_request.await_count == db.insert_ai_model_call.await_count == 2
    assert calls[0]["model"] == calls[1]["model"] == "test-cloud-translator"
    assert "previous attempt failed" not in calls[0]["messages"][0]["content"]
    feedback = calls[1]["messages"][0]["content"]
    assert "previous attempt failed" in feedback
    assert all(field in feedback for field in SCRIPT_FIELDS)
    assert calls[0]["messages"][1] == calls[1]["messages"][1]
    assert json.loads(calls[1]["messages"][1]["content"])["raw_item"]["text_clean"] == SOURCE
    usages = [call.kwargs["usage"] for call in db.insert_ai_model_call.await_args_list]
    assert [usage.success for usage in usages] == [False, repaired]
    assert all(usage.provider == "ollama_cloud" and usage.ai_layer == "translation_summary" for usage in usages)
    if repaired:
        db.update_translation_failed.assert_not_awaited()
        db.update_translation_result.assert_awaited_once()
        assert len(db.update_translation_result.await_args.kwargs["response"].result.translations) == 4
    else:
        db.update_translation_result.assert_not_awaited()
        db.update_translation_failed.assert_awaited_once()


@pytest.mark.parametrize("budget", ["daily", "per_run", "store_unavailable"])
async def test_repair_cannot_bypass_budget(monkeypatch, budget):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False,
        MAX_TRANSLATION_CALLS_PER_RUN=1 if budget == "per_run" else 0)
    if budget == "daily":
        db.reserve_ai_request.side_effect = [True, False]
    elif budget == "store_unavailable":
        db.reserve_ai_request.side_effect = [True, RuntimeError("budget store unavailable")]
    calls = []

    async def fake_post(http, url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=envelope(incident()), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == db.insert_ai_model_call.await_count == 1
    db.update_translation_result.assert_not_awaited()
    db.update_translation_failed.assert_awaited_once()


@pytest.mark.parametrize("failure", ["timeout", "auth", "json", "length", "missing_full"])
async def test_other_failures_do_not_get_a_script_repair(monkeypatch, failure):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False)
    calls = []

    async def fake_post(http, url, **kwargs):
        calls.append(url)
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture timeout")
        value = incident()
        if failure == "length":
            value["translations"][0]["summary"] = "中" * 281
        elif failure == "missing_full":
            value["translations"][0]["full_translation"] = None
        body = envelope(value)
        if failure == "json":
            body["choices"][0]["message"]["content"] = "not JSON"
        return httpx.Response(401 if failure == "auth" else 200, json=body,
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == db.insert_ai_model_call.await_count == 1
    db.update_translation_result.assert_not_awaited()
    db.update_translation_failed.assert_awaited_once()


@pytest.mark.parametrize("provider", ["openrouter", "ollama_cloud"])
async def test_existing_fallback_is_only_used_when_configured(monkeypatch, provider):
    worker, db, task, normalized = make_worker(TRANSLATION_MODEL_PROVIDER=provider)
    calls = []

    async def fake_post(http, url, **kwargs):
        calls.append(url)
        value = incident(repaired=len(calls) == (3 if provider == "ollama_cloud" else 2))
        return httpx.Response(200, json=envelope(value), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == (3 if provider == "ollama_cloud" else 2)
    assert [call.kwargs["usage"].provider for call in db.insert_ai_model_call.await_args_list] == (
        ["ollama_cloud", "ollama_cloud", "openrouter"] if provider == "ollama_cloud" else ["openrouter", "openrouter"])
    db.update_translation_result.assert_awaited_once()


async def test_storage_failure_after_repair_does_not_trigger_fallback(monkeypatch):
    worker, db, task, normalized = make_worker()
    calls = []
    db.update_translation_result.side_effect = RuntimeError("fixture storage failure")

    async def fake_post(http, url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=envelope(incident(repaired=len(calls) == 2)),
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(RuntimeError, match="fixture storage failure"):
        await worker._run_translation_summary(task, normalized)
    assert len(calls) == db.insert_ai_model_call.await_count == 2
    db.update_translation_failed.assert_not_awaited()


async def test_repair_limit_is_shared_across_ollama_primary_and_fallback(monkeypatch):
    worker, db, task, normalized = make_worker(TRANSLATION_FALLBACK_PROVIDER="ollama_cloud")
    calls = []

    async def fake_post(http, url, **kwargs):
        calls.append(kwargs["json"]["model"])
        return httpx.Response(200, json=envelope(incident()), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await worker._run_translation_summary(task, normalized)
    assert calls == ["test-cloud-translator", "test-cloud-translator", "router-fallback"]
    assert db.reserve_ai_request.await_count == db.insert_ai_model_call.await_count == 3
    db.update_translation_result.assert_not_awaited()
    db.update_translation_failed.assert_awaited_once()


async def test_repair_failure_does_not_replay_classification(monkeypatch):
    worker, db, task, normalized = make_worker(TRANSLATION_PAID_FALLBACK_ENABLED=False)
    task.id, task.attempt_count = "processing-id", 0
    routing = SimpleNamespace(prompt_modules=lambda domains: [], domains=[SimpleNamespace(key="geopolitics")])
    db.claim_next_task = AsyncMock(return_value=task)
    db.get_routing_context = AsyncMock(return_value=routing)
    db.get_taxonomy_context = AsyncMock(return_value=TaxonomyContext())
    db.update_normalized_item = AsyncMock()
    db.complete_processed = AsyncMock(return_value="event-id")
    db.mark_failed = AsyncMock()

    async def failed(**kwargs):
        worker._stop_event.set()

    db.update_translation_failed.side_effect = failed
    calls = []

    async def fake_post(http, url, **kwargs):
        model = kwargs["json"]["model"]
        calls.append(model)
        if model == worker.model_client.model:
            value = classification()
        else:
            db.complete_processed.assert_awaited_once()
            value = incident()
        return httpx.Response(200, json=envelope(value), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr("normalizer_classifier.worker.normalize_item", lambda *args: normalized)
    await worker._loop(0)
    assert calls == [worker.model_client.model, "test-cloud-translator", "test-cloud-translator"]
    assert [call.kwargs["usage"].ai_layer for call in db.insert_ai_model_call.await_args_list] == [
        "classification_reasoning", "translation_summary", "translation_summary"]
    db.mark_failed.assert_not_awaited()
    db.complete_processed.assert_awaited_once()
