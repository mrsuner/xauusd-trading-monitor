from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from public_syncer.models import PublicOutboxItem, PublicOutboxTranslation, PublicRawItem
from public_syncer.payload import build_payload, clamp_text, idempotency_key_for, public_translation_rows, sanitize_source_links
from public_syncer.payload import build_raw_item_payload, raw_item_idempotency_key_for


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
    payload = build_payload(item, sync_languages=("zh-Hant", "en", "ja"))

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
    assert public_translation_rows(item, sync_languages=("zh-Hant", "en", "ja")) == [
        {"language": "en", "title": "Title from row", "summary": "Summary from row"},
        {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
    ]


def test_public_translation_rows_respects_sync_languages() -> None:
    item = make_item()

    assert public_translation_rows(item, sync_languages=("zh-Hant", "en")) == [
        {"language": "en", "title": "Title from row", "summary": "Summary from row"},
    ]


def test_public_translation_rows_skip_unapproved_rows() -> None:
    item = make_item()
    item.translations = [
        PublicOutboxTranslation(language="en", title="Draft title", summary="Draft summary", status="draft"),
        PublicOutboxTranslation(language="ja", title="日本語タイトル", summary="日本語要約", status="approved"),
    ]

    assert public_translation_rows(item, sync_languages=("zh-Hant", "en", "ja")) == [
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


def make_raw_item() -> PublicRawItem:
    raw_item_id = uuid4()
    return PublicRawItem(
        id=raw_item_id,
        source_id=uuid4(),
        source_updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        title=" Raw item title ",
        text_clean="Original content with token=abcdefghijklmnopqrstuvwxyz123456 and useful market detail.",
        language="en",
        url="https://example.com/news",
        media_type="none",
        translations=[
            {
                "language": "zh-Hant",
                "summary": "中文摘要",
                "full_translation": "中文全文翻譯",
                "status": "completed",
                "input_chars": 120,
            },
            {
                "language": "en",
                "summary": "English summary",
                "full_translation": "English full translation",
                "status": "completed",
                "input_chars": 120,
            },
            {
                "language": "ja",
                "summary": "日本語要約",
                "full_translation": "日本語全文",
                "status": "completed",
                "input_chars": 120,
            }
        ],
        translation_status="completed",
        translation_input_chars=120,
        content_category="macro_policy",
        topic_tags=["Fed", "fed", "Gold"],
        mentioned_actors=["Federal Reserve"],
        source_name="Example",
        source_type="rss",
        source_group="macro",
        official_level="official",
        priority="P1",
        classification_stage="completed",
        classification_status="completed",
        is_relevant=True,
        relevance_score=88,
        upstream_event_ids=[uuid4()],
    )


def test_raw_item_idempotency_key() -> None:
    item = make_raw_item()

    assert raw_item_idempotency_key_for(item) == f"raw_item:{item.id}:v1"


def test_build_raw_item_payload_is_public_safe() -> None:
    item = make_raw_item()

    payload = build_raw_item_payload(
        item,
        max_original_chars=4000,
        max_translation_chars=8000,
        sync_languages=("zh-Hant", "en", "ja"),
    )

    assert payload["schema_version"] == "public_raw_item.v1"
    assert payload["idempotency_key"] == f"raw_item:{item.id}:v1"
    assert payload["upstream_raw_item_id"] == str(item.id)
    assert payload["source"]["name"] == "Example"
    assert payload["source_url"] == "https://example.com/news"
    assert payload["title"] == "Raw item title"
    assert "[REDACTED]" in payload["original_content"]
    assert "abcdefghijklmnopqrstuvwxyz123456" not in payload["original_content"]
    assert "summary_zh" not in payload
    assert "summary_en" not in payload
    assert "full_translation_zh" not in payload
    assert "full_translation_en" not in payload
    assert payload["translations"] == [
        {
            "language": "zh-Hant",
            "summary": "中文摘要",
            "full_translation": "中文全文翻譯",
            "status": "completed",
            "is_truncated": False,
            "source_chars": 120,
            "translation_chars": 6,
        },
        {
            "language": "en",
            "summary": "English summary",
            "full_translation": "English full translation",
            "status": "completed",
            "is_truncated": False,
            "source_chars": 120,
            "translation_chars": 24,
        },
        {
            "language": "ja",
            "summary": "日本語要約",
            "full_translation": "日本語全文",
            "status": "completed",
            "is_truncated": False,
            "source_chars": 120,
            "translation_chars": 5,
        }
    ]
    assert payload["topic_tags"] == ["Fed", "Gold"]
    assert payload["classification"]["relevance_score"] == 88
    assert "raw_json" not in payload
    assert "text_raw" not in payload


def test_build_raw_item_payload_truncates_original_and_translation() -> None:
    item = make_raw_item()
    item.text_clean = "alpha " * 20
    item.translations[1].full_translation = "bravo " * 20

    payload = build_raw_item_payload(
        item,
        max_original_chars=20,
        max_translation_chars=25,
        sync_languages=("zh-Hant", "en", "ja"),
    )

    assert len(payload["original_content"]) == 20
    assert payload["original_content"].endswith("…")
    en_translation = next(translation for translation in payload["translations"] if translation["language"] == "en")
    assert len(en_translation["full_translation"]) <= 25
    assert en_translation["full_translation"].endswith("…")
    assert en_translation["is_truncated"] is True
    assert payload["scrub_metadata"]["original_content_truncated"] is True
    assert "full_translation_en_truncated" not in payload["scrub_metadata"]


def test_build_raw_item_payload_filters_non_http_url() -> None:
    item = make_raw_item()
    item.url = "ftp://example.com/file"

    payload = build_raw_item_payload(item, max_original_chars=4000, max_translation_chars=8000)

    assert payload["source_url"] is None
