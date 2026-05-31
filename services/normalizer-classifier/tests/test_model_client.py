from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from normalizer_classifier.model_client import OpenAIStyleModelClient
from normalizer_classifier.models import NormalizedItem, RawItem, SourceMetadata


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
