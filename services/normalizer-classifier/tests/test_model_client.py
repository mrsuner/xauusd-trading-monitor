from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from normalizer_classifier.model_client import (
    OpenAIStyleModelClient,
    build_auxiliary_model_client,
    build_translation_model_clients,
    auxiliary_text_json_schema_response_format,
)
from normalizer_classifier.models import AuxiliaryTextResult, NormalizedItem, RawItem, SourceMetadata
from normalizer_classifier.settings import Settings


def make_objects() -> tuple[RawItem, SourceMetadata, NormalizedItem]:
    raw_item = RawItem(
        id=uuid4(),
        source_id=uuid4(),
        ingested_at=datetime.now(timezone.utc),
        title="Iran nuclear deal",
        text_raw="Trump says Iran deal is close.",
        media_type="none",
        raw_json={},
        dedupe_key="telegram:1:2",
    )
    source = SourceMetadata(
        id=raw_item.source_id,
        name="Trump tracker",
        handle_or_url="@TrumpTruthSocial_Alert",
        source_type="telegram",
        source_group="us_trump",
        official_level="unofficial_mirror",
        priority="P0",
        reliability_score=65,
        latency_score=95,
        requires_confirmation=True,
    )
    normalized = NormalizedItem(
        text_clean="Trump says Iran deal is close.",
        language="en",
        keyword_score=66,
        matched_keywords=["trump", "iran"],
        prefilter_passed=True,
    )
    return raw_item, source, normalized


async def test_openai_style_model_client_parses_json_response(monkeypatch) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        assert url == "https://api.example.test/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-key"
        assert json["response_format"] == {"type": "json_object"}
        content = {
            "is_relevant": True,
            "relevance_score": 82,
            "event_type": "IRAN_NUCLEAR",
            "source_stance": "us_trump",
            "claim_direction": "confirm",
            "claim_text": "Trump says Iran deal is close.",
            "summary_zh": "Trump 表示伊朗協議接近完成。",
            "summary_en": "Trump says an Iran deal is close.",
            "actors": ["Trump", "Iran"],
            "xauusd_impact_channel": ["safe_haven"],
            "requires_confirmation": True,
            "confidence": 74,
            "reason": "High value Trump/Iran headline.",
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}]},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="cloud_small",
        base_url="https://api.example.test/v1/",
        api_key="test-key",
        model="test-model",
        timeout_seconds=5,
        response_format="json_object",
        reasoning_effort="none",
    )

    response = await client.classify(raw_item, source, normalized)

    assert response.provider == "cloud_small"
    assert response.model == "test-model"
    assert response.result.is_relevant is True
    assert response.result.relevance_score == 82


async def test_openai_style_model_client_logs_api_request_and_response(monkeypatch, caplog) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        assert headers["Authorization"] == "Bearer test-key"
        content = {
            "is_relevant": True,
            "relevance_score": 82,
            "event_type": "IRAN_NUCLEAR",
            "claim_direction": "confirm",
            "summary_zh": "Trump 表示伊朗協議接近完成。",
            "requires_confirmation": True,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}], "usage": {"total_tokens": 12}},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="cloud_small",
        base_url="https://api.example.test/v1/",
        api_key="test-key",
        model="test-model",
        timeout_seconds=5,
        response_format="json_object",
    )

    with caplog.at_level(logging.DEBUG, logger="normalizer_classifier.model_client"):
        await client.classify(raw_item, source, normalized)

    request_record = next(record for record in caplog.records if record.message == "ai_model_api_request")
    response_record = next(record for record in caplog.records if record.message == "ai_model_api_response")
    assert request_record.request_kind == "classify_raw_item"
    assert request_record.headers["Authorization"] == "[REDACTED]"
    assert request_record.payload["messages"][1]["content"]
    assert response_record.status_code == 200
    assert response_record.response_body["usage"]["total_tokens"] == 12
    assert "test-key" not in json.dumps(request_record.headers)


async def test_openai_style_model_client_can_omit_json_response_format(monkeypatch) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        assert "response_format" not in json
        content = {
            "is_relevant": False,
            "relevance_score": 10,
            "event_type": "UNKNOWN",
            "claim_direction": "unknown",
            "summary_zh": "低相關消息。",
            "requires_confirmation": True,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}]},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="local_8b",
        base_url="http://localhost:11434/v1",
        api_key=None,
        model="test-model",
        timeout_seconds=5,
        response_format="none",
    )

    response = await client.classify(raw_item, source, normalized)

    assert response.provider == "local_8b"
    assert response.result.is_relevant is False


async def test_openai_style_model_client_supports_json_schema_reasoning_content(monkeypatch) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        assert json["response_format"]["type"] == "json_schema"
        content = {
            "is_relevant": True,
            "relevance_score": 75,
            "event_type": "US_FED",
            "source_stance": None,
            "claim_direction": "neutral",
            "claim_text": None,
            "summary_zh": "Fed 相關消息。",
            "summary_en": None,
            "actors": ["Fed"],
            "xauusd_impact_channel": ["real_rate"],
            "requires_confirmation": True,
            "confidence": 70,
            "reason": "Relevant to rates.",
            "region": "US",
            "primary_actor": "Fed",
            "secondary_actor": None,
            "market_relevance": "May affect real rates.",
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "", "reasoning_content": json_module.dumps(content)}}]},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="local_8b",
        base_url="http://localhost:1234/v1",
        api_key=None,
        model="test-model",
        timeout_seconds=5,
        response_format="json_schema",
    )

    response = await client.classify(raw_item, source, normalized)

    assert response.result.is_relevant is True
    assert response.result.event_type == "US_FED"


async def test_openai_style_model_client_sends_reasoning_effort(monkeypatch) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        assert json["reasoning_effort"] == "none"
        content = {
            "is_relevant": False,
            "relevance_score": 20,
            "event_type": "UNKNOWN",
            "claim_direction": "unknown",
            "summary_zh": "測試。",
            "requires_confirmation": True,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}]},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="local_8b",
        base_url="http://localhost:11434/v1",
        api_key=None,
        model="test-model",
        timeout_seconds=5,
        response_format="json_object",
        reasoning_effort="none",
    )

    response = await client.classify(raw_item, source, normalized)

    assert response.result.relevance_score == 20


async def test_openai_style_model_client_summarizes_with_openrouter_headers(monkeypatch) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        assert headers["Authorization"] == "Bearer openrouter-key"
        assert headers["HTTP-Referer"] == "https://example.test"
        assert headers["X-Title"] == "XAUUSD Event Radar"
        assert json["response_format"] == {"type": "json_object"}
        content = {
            "summary_zh": "Trump 稱伊朗協議接近完成。",
            "summary_en": "Trump says an Iran deal is close.",
            "full_translation_zh": "Trump 表示伊朗協議已接近完成。",
            "full_translation_en": "Trump says Iran deal is close.",
            "content_category": "diplomacy",
            "topic_tags": ["trump", "iran", "nuclear"],
            "mentioned_actors": ["Trump", "Iran"],
            "detected_language": "en",
            "notes": None,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}]},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="openrouter_free",
        base_url="https://openrouter.ai/api/v1",
        api_key="openrouter-key",
        model="free-summary-model",
        timeout_seconds=5,
        response_format="json_object",
        extra_headers={"HTTP-Referer": "https://example.test", "X-Title": "XAUUSD Event Radar"},
    )

    response = await client.summarize_and_translate(raw_item, source, normalized)

    assert response.provider == "openrouter_free"
    assert response.model == "free-summary-model"
    assert response.result.summary_zh == "Trump 稱伊朗協議接近完成。"
    assert response.result.summary_en == "Trump says an Iran deal is close."
    assert response.result.full_translation_zh == "Trump 表示伊朗協議已接近完成。"
    assert response.result.content_category == "diplomacy"
    assert response.result.topic_tags == ["trump", "iran", "nuclear"]
    assert response.result.mentioned_actors == ["Trump", "Iran"]


async def test_openai_style_model_client_parses_auxiliary_translations_array(monkeypatch) -> None:
    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        content = {
            "translations": [
                {
                    "language": "zh-Hant",
                    "summary": "Trump 稱伊朗協議接近完成。",
                    "full_translation": "Trump 表示伊朗協議已接近完成。",
                },
                {
                    "language": "en",
                    "summary": "Trump says an Iran deal is close.",
                    "full_translation": "Trump says Iran deal is close.",
                },
                {
                    "language": "ja",
                    "summary": "トランプ氏はイラン合意が近いと述べた。",
                    "full_translation": "トランプ氏はイラン合意が近いと述べた。",
                },
            ],
            "content_category": "diplomacy",
            "topic_tags": ["trump", "iran"],
            "mentioned_actors": ["Trump", "Iran"],
            "detected_language": "en",
            "notes": None,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}]},
            request=httpx.Request("POST", url),
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    raw_item, source, normalized = make_objects()
    client = OpenAIStyleModelClient(
        provider="translation_primary",
        base_url="https://api.example.test/v1",
        api_key="test-key",
        model="translation-model",
        timeout_seconds=5,
        response_format="json_object",
    )

    response = await client.summarize_and_translate(raw_item, source, normalized)

    assert response.result.summary_zh == "Trump 稱伊朗協議接近完成。"
    assert response.result.summary_en == "Trump says an Iran deal is close."
    assert response.result.full_translation_zh == "Trump 表示伊朗協議已接近完成。"
    assert response.result.translation_for("ja") is not None


def test_auxiliary_text_result_backfills_translations_from_legacy_fields() -> None:
    result = AuxiliaryTextResult.model_validate(
        {
            "summary_zh": "中文摘要",
            "summary_en": "English summary",
            "full_translation_zh": "中文全文",
            "full_translation_en": "English full text",
        }
    )

    assert [(translation.language, translation.summary) for translation in result.translations] == [
        ("zh-Hant", "中文摘要"),
        ("en", "English summary"),
    ]


def test_auxiliary_text_json_schema_uses_translations_array() -> None:
    schema = auxiliary_text_json_schema_response_format()["json_schema"]["schema"]

    assert "translations" in schema["properties"]
    assert "summary_zh" not in schema["properties"]
    assert "translations" in schema["required"]
    translation_item = schema["properties"]["translations"]["items"]
    assert translation_item["required"] == ["language", "summary", "full_translation"]


def test_build_auxiliary_model_client_openrouter() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        AUXILIARY_MODEL_ENABLED="true",
        AUXILIARY_MODEL_ROUTE="openrouter_free",
        OPENROUTER_MODEL_API_KEY="openrouter-key",
        OPENROUTER_MODEL_NAME="free-summary-model",
        OPENROUTER_HTTP_REFERER="https://example.test",
    )

    client = build_auxiliary_model_client(settings)

    assert client is not None
    assert client.provider == "openrouter_free"
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.model == "free-summary-model"
    assert client.extra_headers["HTTP-Referer"] == "https://example.test"


def test_build_translation_model_clients_use_free_then_paid_fallback() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        CLOUD_MODEL_API_KEY="test-key",
        OPENROUTER_MODEL_API_KEY="openrouter-key",
        TRANSLATION_MODEL_ENABLED="true",
        TRANSLATION_PRIMARY_MODEL_NAME="openai/gpt-oss-20b:free",
        TRANSLATION_FALLBACK_MODEL_NAME="openai/gpt-oss-20b",
        TRANSLATION_PAID_FALLBACK_ENABLED="true",
    )

    clients = build_translation_model_clients(settings)

    assert [client.provider for client in clients] == ["translation_primary", "translation_paid_fallback"]
    assert [client.model for client in clients] == ["openai/gpt-oss-20b:free", "openai/gpt-oss-20b"]
