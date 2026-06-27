from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from x_publisher.models import PublicOutboxItem
from x_publisher.semantic_dedupe import SemanticDedupeClient, parse_response, semantic_dedupe_models
from x_publisher.settings import Settings


def make_settings(**overrides: object) -> Settings:
    data = {
        "DATABASE_URL": "postgresql://x:y@localhost/db",
        "X_SEMANTIC_DEDUPE_ENABLED": True,
        "X_SEMANTIC_DEDUPE_MODEL_BASE_URL": "https://model.test/v1",
        "X_SEMANTIC_DEDUPE_MODEL_API_KEY": "key",
        "X_SEMANTIC_DEDUPE_MODEL_NAME": "small-model",
    }
    data.update(overrides)
    return Settings(**data)


def make_item(**overrides: object) -> PublicOutboxItem:
    data = {
        "id": uuid4(),
        "event_id": uuid4(),
        "title": "IRGC 聲稱攻擊美軍基地",
        "summary": "IRGC聲稱對科威特與巴林的美軍基地及第五艦隊設施發動打擊。",
        "public_source_links": [{"source_name": "Press TV", "url": "https://example.com/news"}],
        "severity": "S",
        "confirmation_state": "unconfirmed",
        "topic_tags": ["geopolitics", "iran"],
        "generated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return PublicOutboxItem.model_validate(data)


def test_parse_response_accepts_json_object_content() -> None:
    result = parse_response(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"is_duplicate": true, "similarity_score": 94, '
                            '"matched_item_id": "abc", "reason": "same claim"}'
                        )
                    }
                }
            ]
        }
    )

    assert result.is_duplicate is True
    assert result.similarity_score == 94
    assert result.matched_item_id == "abc"


def test_semantic_dedupe_models_use_free_then_paid_fallback() -> None:
    settings = make_settings(
        X_SEMANTIC_DEDUPE_MODEL_NAME="",
        X_SEMANTIC_DEDUPE_FALLBACK_MODEL_NAME="",
        TRANSLATION_PRIMARY_MODEL_NAME="openai/gpt-oss-20b:free",
        TRANSLATION_FALLBACK_MODEL_NAME="openai/gpt-oss-20b",
        TRANSLATION_PAID_FALLBACK_ENABLED=True,
    )

    assert semantic_dedupe_models(settings) == ["openai/gpt-oss-20b:free", "openai/gpt-oss-20b"]


@pytest.mark.asyncio
async def test_compare_posts_openai_compatible_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_response(
                                True,
                                91,
                                str(candidate.id),
                                "same facilities",
                            )
                        }
                    }
                ]
            },
        )

    current = make_item()
    candidate = make_item(summary="IRGC聲稱打擊科威特與巴林的美軍設施。")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await SemanticDedupeClient(make_settings(), http_client).compare(current, [candidate])

    assert result is not None
    assert result.is_duplicate is True
    assert result.matched_item_id == str(candidate.id)
    assert result.model == "small-model"
    assert requests[0].url == "https://model.test/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer key"
    assert requests[0].headers["x-title"] == "XAUUSD Event Radar"


@pytest.mark.asyncio
async def test_compare_ignores_duplicate_below_threshold() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"is_duplicate": true, "similarity_score": 70, '
                                '"matched_item_id": "abc", "reason": "broadly related"}'
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await SemanticDedupeClient(
            make_settings(X_SEMANTIC_DEDUPE_THRESHOLD=85),
            http_client,
        ).compare(make_item(), [make_item()])

    assert result is not None
    assert result.is_duplicate is False


@pytest.mark.asyncio
async def test_compare_falls_back_when_primary_model_fails() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json_body(request)
        requests.append(body["model"])
        if body["model"] == "free-model":
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_response(True, 90, "abc", "same claim")
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await SemanticDedupeClient(
            make_settings(
                X_SEMANTIC_DEDUPE_MODEL_NAME="free-model",
                X_SEMANTIC_DEDUPE_FALLBACK_MODEL_NAME="paid-model",
            ),
            http_client,
        ).compare(make_item(), [make_item()])

    assert result is not None
    assert result.is_duplicate is True
    assert result.model == "paid-model"
    assert requests == ["free-model", "paid-model"]


def json_response(is_duplicate: bool, score: int, matched_item_id: str | None, reason: str | None) -> str:
    import json

    return json.dumps(
        {
            "is_duplicate": is_duplicate,
            "similarity_score": score,
            "matched_item_id": matched_item_id,
            "reason": reason,
        }
    )


def json_body(request: httpx.Request) -> dict[str, object]:
    import json

    return json.loads(request.read().decode("utf-8"))
