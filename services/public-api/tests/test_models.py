from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from public_api.models import (
    PublicEventIngestRequest,
    PublicRawItemIngestRequest,
    SubscriptionCatalogIngestRequest,
    SubscriptionCategoryInput,
    SubscriptionTagInput,
    subscription_catalog_revision,
)


def subscription_catalog_payload() -> dict:
    categories = [
        SubscriptionCategoryInput(
            key="fed",
            label_en="Federal Reserve",
            label_zh="聯準會",
            description="Federal Reserve policy.",
            sort_order=10,
        )
    ]
    tags = [
        SubscriptionTagInput(
            key="inflation",
            label_en="Inflation",
            label_zh="通膨",
            tag_type="topic",
            aliases=[],
        )
    ]
    revision = subscription_catalog_revision(categories, tags)
    return {
        "schema_version": "subscription_catalog.v1",
        "idempotency_key": f"subscription_catalog:{revision}",
        "revision": revision,
        "generated_at": "2026-09-11T00:00:00Z",
        "categories": [item.model_dump(mode="json") for item in categories],
        "tags": [item.model_dump(mode="json") for item in tags],
    }


def test_subscription_catalog_accepts_matching_content_revision() -> None:
    payload = SubscriptionCatalogIngestRequest.model_validate(subscription_catalog_payload())

    assert payload.categories[0].key == "fed"
    assert payload.tags[0].label_zh == "通膨"


def test_subscription_catalog_rejects_tampered_content() -> None:
    raw = subscription_catalog_payload()
    raw["tags"][0]["label_en"] = "Changed after hashing"

    with pytest.raises(ValidationError, match="revision mismatch"):
        SubscriptionCatalogIngestRequest.model_validate(raw)


def test_public_event_ingest_request_normalizes_taxonomy() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "topic_tags": [" Iran ", "iran", "", "Gold"],
            "mentioned_actors": ["Trump", " trump "],
            "public_source_links": [{"url": "https://example.com/news", "source_name": "Example"}],
        }
    )

    assert payload.topic_tags == ["Iran", "Gold"]
    assert payload.mentioned_actors == ["Trump"]


def test_public_event_ingest_request_rejects_legacy_translation_fields() -> None:
    with pytest.raises(ValidationError):
        PublicEventIngestRequest.model_validate(
            {
                "schema_version": "public_event.v1",
                "idempotency_key": "event:1:v1",
                "upstream_event_id": str(uuid4()),
                "severity": "A",
                "public_summary_zh": "legacy summary",
                "translations": [{"language": "zh-Hant", "summary": "中文摘要"}],
            }
        )


def test_public_event_ingest_request_accepts_translation_rows() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "translations": [
                {"language": " ja ", "title": " 日本語タイトル ", "summary": " 日本語要約 "},
                {"language": "zh-Hant", "summary": "中文摘要"},
            ],
        }
    )

    assert [(item.language, item.title, item.summary) for item in payload.translations] == [
        ("ja", "日本語タイトル", "日本語要約"),
        ("zh-Hant", None, "中文摘要"),
    ]


def test_public_event_ingest_request_rejects_invalid_translation_language() -> None:
    with pytest.raises(ValidationError):
        PublicEventIngestRequest.model_validate(
            {
                "schema_version": "public_event.v1",
                "idempotency_key": "event:1:v1",
                "upstream_event_id": str(uuid4()),
                "severity": "A",
                "translations": [{"language": "not a language", "summary": "Summary"}],
            }
        )


def test_public_event_ingest_request_rejects_empty_translation_content() -> None:
    with pytest.raises(ValidationError):
        PublicEventIngestRequest.model_validate(
            {
                "schema_version": "public_event.v1",
                "idempotency_key": "event:1:v1",
                "upstream_event_id": str(uuid4()),
                "severity": "A",
                "translations": [{"language": "ja", "summary": "   "}],
            }
        )


def test_public_event_ingest_request_rejects_unsupported_schema() -> None:
    with pytest.raises(ValidationError):
        PublicEventIngestRequest.model_validate(
            {
                "schema_version": "public_event.v2",
                "idempotency_key": "event:1:v2",
                "upstream_event_id": str(uuid4()),
                "severity": "A",
            }
        )


def test_public_raw_item_ingest_request_normalizes_public_fields() -> None:
    raw_item_id = uuid4()
    event_id = uuid4()

    payload = PublicRawItemIngestRequest.model_validate(
        {
            "schema_version": "public_raw_item.v1",
            "idempotency_key": f"raw_item:{raw_item_id}:v1",
            "upstream_raw_item_id": str(raw_item_id),
            "source": {
                "name": " Example ",
                "source_type": "telegram",
                "source_group": "macro",
                "official_level": "official",
                "priority": "P1",
                "internal_id": "ignored",
            },
            "source_url": "https://example.com/news",
            "title": " Title ",
            "original_content": " Clean content ",
            "language": " en ",
            "topic_tags": [" Iran ", "iran", "Gold"],
            "mentioned_actors": ["Fed", " fed "],
            "upstream_event_ids": [str(event_id), str(event_id)],
            "translations": [
                {
                    "language": " zh-Hant ",
                    "summary": " 翻譯摘要 ",
                    "full_translation": " 全文翻譯 ",
                    "status": "completed",
                }
            ],
            "classification": {"is_relevant": True, "relevance_score": 88},
        }
    )

    assert payload.source.name == "Example"
    assert str(payload.source_url) == "https://example.com/news"
    assert payload.title == "Title"
    assert payload.original_content == "Clean content"
    assert payload.language == "en"
    assert payload.topic_tags == ["Iran", "Gold"]
    assert payload.mentioned_actors == ["Fed"]
    assert payload.upstream_event_ids == [event_id]
    assert [(item.language, item.summary, item.full_translation, item.status) for item in payload.translations] == [
        ("zh-Hant", "翻譯摘要", "全文翻譯", "completed")
    ]


def test_public_raw_item_ingest_request_rejects_legacy_translation_fields() -> None:
    with pytest.raises(ValidationError):
        PublicRawItemIngestRequest.model_validate(
            {
                "schema_version": "public_raw_item.v1",
                "idempotency_key": "raw_item:1:v1",
                "upstream_raw_item_id": str(uuid4()),
                "title": "Title",
                "summary_zh": "中文摘要",
            }
        )


def test_public_raw_item_ingest_request_rejects_unsupported_schema() -> None:
    with pytest.raises(ValidationError):
        PublicRawItemIngestRequest.model_validate(
            {
                "schema_version": "public_raw_item.v2",
                "idempotency_key": "raw_item:1:v2",
                "upstream_raw_item_id": str(uuid4()),
                "title": "Title",
            }
        )


def test_public_raw_item_ingest_request_rejects_invalid_source_url() -> None:
    with pytest.raises(ValidationError):
        PublicRawItemIngestRequest.model_validate(
            {
                "schema_version": "public_raw_item.v1",
                "idempotency_key": "raw_item:1:v1",
                "upstream_raw_item_id": str(uuid4()),
                "source_url": "ftp://example.com/file",
                "title": "Title",
            }
        )


def test_public_raw_item_ingest_request_rejects_empty_translation_content() -> None:
    with pytest.raises(ValidationError):
        PublicRawItemIngestRequest.model_validate(
            {
                "schema_version": "public_raw_item.v1",
                "idempotency_key": "raw_item:1:v1",
                "upstream_raw_item_id": str(uuid4()),
                "title": "Title",
                "translations": [{"language": "en", "summary": "  "}],
            }
        )
