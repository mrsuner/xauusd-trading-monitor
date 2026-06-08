from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from public_syncer.models import PublicOutboxItem, PublicOutboxTranslation
from public_syncer.payload import build_payload, clamp_text, idempotency_key_for, public_translation_rows, sanitize_source_links


def make_item() -> PublicOutboxItem:
    event_id = uuid4()
    return PublicOutboxItem(
        id=uuid4(),
        event_id=event_id,
        public_title_zh="標題",
        public_summary_zh="摘要",
        public_title_en="Title",
        public_summary_en="Summary",
        translations=[
            {"language": "en", "title": "Title from row", "summary": "Summary from row", "status": "approved"},
            {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約", "status": "approved"},
        ],
        public_source_links=[
            {"url": "https://example.com/news", "source_name": "Example"},
            {"url": "javascript:alert(1)", "source_name": "Bad"},
        ],
        severity="A",
        relevance_score=80,
        confirmation_state="confirmed",
        topic_tags=["Iran", "Gold"],
        retry_count_web=1,
        generated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def test_idempotency_key_for_event() -> None:
    item = make_item()
    assert idempotency_key_for(item) == f"event:{item.event_id}:v1"


def test_build_payload_is_public_safe() -> None:
    item = make_item()
    payload = build_payload(item)

    assert payload["schema_version"] == "public_event.v1"
    assert payload["upstream_event_id"] == str(item.event_id)
    assert payload["public_title_zh"] == "標題"
    assert payload["public_summary_zh"] == "摘要"
    assert payload["public_title_en"] == "Title"
    assert payload["public_summary_en"] == "Summary"
    assert payload["translations"] == [
        {"language": "en", "title": "Title from row", "summary": "Summary from row"},
        {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
    ]
    assert payload["public_source_links"] == [
        {"url": "https://example.com/news", "source_name": "Example", "label": "Example"}
    ]
    assert payload["route_metadata"]["public_outbox_id"] == str(item.id)
    assert "available_languages" not in payload


def test_build_payload_preserves_missing_language_fields() -> None:
    item = make_item()
    item.public_title_zh = None
    item.public_summary_zh = None
    item.translations = []

    payload = build_payload(item)

    assert payload["public_title_zh"] is None
    assert payload["public_summary_zh"] is None
    assert payload["public_title_en"] == "Title"
    assert payload["public_summary_en"] == "Summary"
    assert payload["translations"] == [{"language": "en", "title": "Title", "summary": "Summary"}]


def test_public_translation_rows_fall_back_to_legacy_fields() -> None:
    item = make_item()
    item.translations = []

    assert public_translation_rows(item) == [
        {"language": "zh-Hant", "title": "標題", "summary": "摘要"},
        {"language": "en", "title": "Title", "summary": "Summary"},
    ]


def test_public_translation_rows_prefer_translation_rows_without_changing_idempotency() -> None:
    item = make_item()

    assert idempotency_key_for(item) == f"event:{item.event_id}:v1"
    assert public_translation_rows(item) == [
        {"language": "en", "title": "Title from row", "summary": "Summary from row"},
        {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
    ]


def test_public_translation_rows_skip_unapproved_rows() -> None:
    item = make_item()
    item.translations = [
        PublicOutboxTranslation(language="en", title="Draft title", summary="Draft summary", status="draft"),
        PublicOutboxTranslation(language="ja", title="日本語タイトル", summary="日本語要約", status="approved"),
    ]

    assert public_translation_rows(item) == [
        {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
    ]


def test_public_translation_rows_do_not_fallback_when_rows_are_unapproved() -> None:
    item = make_item()
    item.translations = [
        PublicOutboxTranslation(language="en", title="Draft title", summary="Draft summary", status="draft"),
    ]

    assert public_translation_rows(item) == []


def test_sanitize_source_links_filters_non_http_urls() -> None:
    assert sanitize_source_links([{"url": "ftp://example.com/file"}, {"url": "http://example.com"}]) == [
        {"url": "http://example.com", "source_name": None, "label": None}
    ]


def test_clamp_text_normalizes_and_truncates_long_titles() -> None:
    text = "  alpha   " + ("x" * 400)

    clamped = clamp_text(text, max_chars=300)

    assert clamped is not None
    assert len(clamped) == 300
    assert clamped.startswith("alpha ")
    assert clamped.endswith("…")
