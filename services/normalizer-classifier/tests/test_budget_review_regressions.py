"""Budget blocks are not provider attempts and must not change their attribution."""
from unittest.mock import AsyncMock

import httpx
import pytest

from test_worker_model_providers import make_worker


@pytest.mark.parametrize("reason", ["item_token_budget_reached", "daily_token_budget_reached", "token_budget_store_unavailable"])
async def test_initial_token_block_is_skipped_without_claiming_a_provider_call(monkeypatch, reason):
    worker, db, task, normalized = make_worker()
    db.reserve_ai_tokens.return_value = reason
    post = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    post.assert_not_awaited()
    db.insert_ai_model_call.assert_not_awaited()
    db.update_translation_failed.assert_not_awaited()
    assert db.update_translation_skipped.await_args.kwargs["reason"] == reason


async def test_unissued_fallback_does_not_replace_actual_failed_provider(monkeypatch):
    worker, db, task, normalized = make_worker()
    db.reserve_ai_tokens.side_effect = [None, "item_token_budget_reached"]
    calls = []

    async def post(http, endpoint, **kwargs):
        calls.append(endpoint)
        raise httpx.ReadTimeout("primary failed")

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    await worker._run_translation_summary(task, normalized)
    assert len(calls) == 1 and "ollama.com" in calls[0]
    assert db.reserve_ai_tokens.await_count == 2
    assert db.insert_ai_model_call.await_count == 1
    assert db.update_translation_failed.await_args.kwargs["provider"] == "translation_primary"
    assert db.update_translation_failed.await_args.kwargs["model"] == "test-cloud-translator"
    assert db.update_translation_failed.await_args.kwargs["error_message"] == "item_token_budget_reached"
