from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from normalizer_classifier import token_budget
from normalizer_classifier.model_client import build_model_client, build_translation_model_clients
from normalizer_classifier.token_budget import ModelBudgetError, RequestTokenBudget, prepare_bounded_request
from test_model_client import make_objects
from test_ollama_cloud import classification, envelope, settings
from test_translation_runtime import result


@pytest.mark.parametrize("estimated,allowed", [(100, True), (101, False)])
async def test_input_reservation_boundary_includes_headroom(monkeypatch, estimated, allowed):
    monkeypatch.setattr(token_budget, "source_tokens", lambda text: estimated)
    db = SimpleNamespace(reserve_ai_tokens=AsyncMock(return_value=None))
    budget = RequestTokenBudget(db, "raw-id", 30000, 5000000)
    payload = {"messages": [], "response_format": {"schema": "fixture"}}
    if allowed:
        await prepare_bounded_request(SimpleNamespace(max_input_tokens=381), payload, output_limit=99, token_budget=budget)
        assert db.reserve_ai_tokens.await_args.kwargs == dict(raw_item_id="raw-id", tokens=480, item_limit=30000, daily_limit=5000000)
    else:
        with pytest.raises(ModelBudgetError, match="request_input_token_limit_exceeded"):
            await prepare_bounded_request(SimpleNamespace(max_input_tokens=381), payload, output_limit=99, token_budget=budget)
        db.reserve_ai_tokens.assert_not_awaited()
    assert payload["max_tokens"] == 99


@pytest.mark.parametrize("provider", ["ollama_cloud", "openrouter"])
@pytest.mark.parametrize("mode", ["classification", "full", "summary"])
async def test_both_provider_payloads_have_output_caps_and_reservations(monkeypatch, provider, mode):
    config = settings(CLASSIFICATION_MODEL_PROVIDER=provider, TRANSLATION_MODEL_PROVIDER=provider,
        CLASSIFICATION_MAX_OUTPUT_TOKENS=456, TRANSLATION_MAX_OUTPUT_TOKENS=789, SUMMARY_MAX_OUTPUT_TOKENS=123)
    client = build_model_client(config) if mode == "classification" else build_translation_model_clients(config)[0]
    db = SimpleNamespace(reserve_ai_tokens=AsyncMock(return_value=None))
    budget = RequestTokenBudget(db, "raw-id", 30000, 5000000)
    calls = []

    async def post(payload, **kwargs):
        calls.append(payload)
        value = classification() if mode == "classification" else result().model_dump()
        if mode == "summary":
            for row in value["translations"]:
                row["full_translation"] = None
        return envelope(value)

    monkeypatch.setattr(client, "_post_chat_completions", post)
    if mode == "classification":
        await client.classify(*make_objects(), token_budget=budget)
    else:
        await client.summarize_and_translate(*make_objects(), token_budget=budget, full_translation_required=mode == "full")
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == dict(classification=456, full=789, summary=123)[mode]
    db.reserve_ai_tokens.assert_awaited_once()
    assert db.reserve_ai_tokens.await_args.kwargs["tokens"] > calls[0]["max_tokens"]


async def test_schema_and_repair_feedback_count_towards_input_cap(monkeypatch):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER="ollama_cloud", AI_MAX_INPUT_TOKENS=16000))
    post = AsyncMock(return_value=envelope(result().model_dump()))
    monkeypatch.setattr(client, "_post_chat_completions", post)
    await client.summarize_and_translate(*make_objects())
    payload = post.await_args.args[0]
    import json, math
    initial = math.ceil(token_budget.source_tokens(json.dumps(payload, ensure_ascii=False, sort_keys=True)) * 1.25) + 256
    client.max_input_tokens = initial
    with pytest.raises(ModelBudgetError, match="request_input_token_limit_exceeded"):
        await client.summarize_and_translate(*make_objects(), script_repair_fields=("zh-Hant.full_translation",))
    assert post.await_count == 1


@pytest.mark.parametrize("reason", ["daily_token_budget_reached", "item_token_budget_reached", "store_unavailable"])
async def test_reservation_failure_prevents_http(monkeypatch, reason):
    client, = build_translation_model_clients(settings(TRANSLATION_MODEL_PROVIDER="ollama_cloud"))
    db = SimpleNamespace(reserve_ai_tokens=AsyncMock(return_value=reason))
    if reason == "store_unavailable":
        db.reserve_ai_tokens.side_effect = RuntimeError("fixture")
    post = AsyncMock()
    monkeypatch.setattr(client, "_post_chat_completions", post)
    with pytest.raises(ModelBudgetError):
        await client.summarize_and_translate(*make_objects(), token_budget=RequestTokenBudget(db, "id", 30000, 5000000))
    post.assert_not_awaited()


def test_token_estimation_failure_is_fail_closed(monkeypatch):
    def fail(*args):
        raise OSError("fixture tokenizer unavailable")
    monkeypatch.setattr(token_budget.tiktoken, "get_encoding", fail)
    with pytest.raises(ModelBudgetError, match="token_estimation_failed"):
        token_budget.source_tokens("source")


@pytest.mark.parametrize("name", ["TRANSLATION_FULL_SOURCE_TOKENS", "AI_MAX_SOURCE_TOKENS", "AI_MAX_INPUT_TOKENS",
    "CLASSIFICATION_MAX_OUTPUT_TOKENS", "TRANSLATION_MAX_OUTPUT_TOKENS", "SUMMARY_MAX_OUTPUT_TOKENS",
    "AI_ITEM_TOKEN_LIMIT", "AI_DAILY_TOKEN_LIMIT"])
def test_new_budget_limits_cannot_be_unlimited(name):
    with pytest.raises(ValueError):
        settings(**{name: 0})


def test_source_thresholds_must_be_ordered():
    with pytest.raises(ValueError):
        settings(TRANSLATION_FULL_SOURCE_TOKENS=8001)
