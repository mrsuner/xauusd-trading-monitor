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
    )

    response = await client.classify(raw_item, source, normalized)

    assert response.provider == "cloud_small"
    assert response.model == "test-model"
    assert response.result.is_relevant is True
    assert response.result.relevance_score == 82
