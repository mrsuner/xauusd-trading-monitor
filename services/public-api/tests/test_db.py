from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from public_api.db import (
    _build_filters,
    _build_raw_item_filters,
    normalize_public_language,
    public_event_translation_rows,
    public_event_translation_search_exists_sql,
    public_event_translations_select_sql,
    public_raw_item_translation_rows,
    public_raw_item_translation_search_exists_sql,
    public_raw_item_translations_select_sql,
    shape_public_event,
    shape_public_raw_item,
)
from public_api.models import PublicEventIngestRequest, PublicRawItemIngestRequest


def event_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": uuid4(),
        "upstream_event_id": uuid4(),
        "idempotency_key": "event:1:v1",
        "schema_version": "public_event.v1",
        "event_time": None,
        "generated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "received_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "severity": "A",
        "relevance_score": 88,
        "confirmation_state": "confirmed",
        "public_source_links": [],
        "topic_tags": ["fed"],
        "content_category": "macro_policy",
        "mentioned_actors": ["Federal Reserve"],
        "route_metadata": {},
        "translations": [
            {"language": "en", "title": "English title", "summary": "English summary"},
            {"language": "zh-Hant", "title": "中文標題", "summary": "中文摘要"},
        ],
    }
    row.update(overrides)
    return row


def raw_item_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": uuid4(),
        "upstream_raw_item_id": uuid4(),
        "idempotency_key": "raw_item:1:v1",
        "schema_version": "public_raw_item.v1",
        "source_name": "Example",
        "source_type": "telegram",
        "source_group": "macro",
        "official_level": "official",
        "priority": "P1",
        "source_url": "https://example.com/news",
        "published_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "ingested_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "edited_at": None,
        "received_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "title": "Raw item title",
        "original_content": "Original content",
        "source_language": "en",
        "media_type": "none",
        "content_category": "macro_policy",
        "topic_tags": ["fed"],
        "mentioned_actors": ["Federal Reserve"],
        "upstream_event_ids": [uuid4()],
        "is_relevant": True,
        "relevance_score": 88,
        "filter_reason": None,
        "classification_stage": "completed",
        "classification_status": "completed",
        "is_truncated": False,
        "source_text_chars": 100,
        "translation_chars": 120,
        "scrub_metadata": {},
        "translations": [
            {
                "language": "en",
                "summary": "English summary",
                "full_translation": "English full translation",
                "status": None,
                "is_truncated": False,
                "source_chars": 100,
                "translation_chars": 120,
            },
            {
                "language": "zh-Hant",
                "summary": "中文摘要",
                "full_translation": "中文全文翻譯",
                "status": None,
                "is_truncated": False,
                "source_chars": 100,
                "translation_chars": 120,
            },
        ],
    }
    row.update(overrides)
    return row


def test_normalize_public_language_defaults_to_english() -> None:
    assert normalize_public_language(None) == "en"
    assert normalize_public_language("fr") == "fr"
    assert normalize_public_language(" ja ") == "ja"
    assert normalize_public_language("not a language") == "en"
    assert normalize_public_language("en") == "en"
    assert normalize_public_language("zh-Hant") == "zh-Hant"
    assert normalize_public_language("bad language", default_language="zh-Hant") == "zh-Hant"


def test_shape_public_event_defaults_to_english() -> None:
    event = shape_public_event(event_row(), lang=None)

    assert event["title"] == "English title"
    assert event["summary"] == "English summary"
    assert event["language"] == "en"
    assert event["available_languages"] == ["en", "zh-Hant"]
    assert event["translations"] == [
        {"language": "en", "title": "English title", "summary": "English summary"},
        {"language": "zh-Hant", "title": "中文標題", "summary": "中文摘要"},
    ]


def test_shape_public_event_selects_chinese() -> None:
    event = shape_public_event(event_row(), lang="zh-Hant")

    assert event["title"] == "中文標題"
    assert event["summary"] == "中文摘要"
    assert event["language"] == "zh-Hant"
    assert event["available_languages"] == ["en", "zh-Hant"]


def test_shape_public_event_falls_back_to_chinese_when_english_missing() -> None:
    event = shape_public_event(
        event_row(translations=[{"language": "zh-Hant", "title": "中文標題", "summary": "中文摘要"}]),
        lang="en",
    )

    assert event["title"] == "中文標題"
    assert event["summary"] == "中文摘要"
    assert event["language"] == "zh-Hant"
    assert event["available_languages"] == ["zh-Hant"]


def test_shape_public_event_invalid_language_uses_english() -> None:
    event = shape_public_event(event_row(), lang="zh")

    assert event["title"] == "English title"
    assert event["summary"] == "English summary"
    assert event["language"] == "en"


def test_shape_public_event_selects_arbitrary_translation_language() -> None:
    event = shape_public_event(
        event_row(
            translations=[
                {"language": "en", "title": "English row title", "summary": "English row summary"},
                {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
            ]
        ),
        lang="ja",
    )

    assert event["title"] == "日本語タイトル"
    assert event["summary"] == "日本語要約"
    assert event["language"] == "ja"
    assert event["available_languages"] == ["en", "ja"]


def test_shape_public_event_falls_back_to_english_when_requested_missing() -> None:
    event = shape_public_event(
        event_row(
            translations=[
                {"language": "en", "title": "English row title", "summary": "English row summary"},
                {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
            ]
        ),
        lang="fr",
    )

    assert event["title"] == "English row title"
    assert event["summary"] == "English row summary"
    assert event["language"] == "en"
    assert event["available_languages"] == ["en", "ja"]


def test_shape_public_event_falls_back_to_available_language_when_english_missing() -> None:
    event = shape_public_event(
        event_row(
            translations=[
                {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
            ],
        ),
        lang="fr",
    )

    assert event["title"] == "日本語タイトル"
    assert event["summary"] == "日本語要約"
    assert event["language"] == "ja"
    assert event["available_languages"] == ["ja"]


def test_shape_public_event_uses_configured_default_language_and_priority() -> None:
    event = shape_public_event(
        event_row(
            translations=[
                {"language": "zh-Hant", "title": "中文標題", "summary": "中文摘要"},
                {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
                {"language": "th", "title": "หัวข้อภาษาไทย", "summary": "สรุปภาษาไทย"},
            ]
        ),
        lang=None,
        default_language="zh-Hant",
        language_priority=("zh-Hant", "en", "th", "ja"),
    )

    assert event["title"] == "中文標題"
    assert event["summary"] == "中文摘要"
    assert event["language"] == "zh-Hant"
    assert event["available_languages"] == ["zh-Hant", "th", "ja"]


def test_shape_public_event_falls_back_per_field() -> None:
    event = shape_public_event(
        event_row(
            translations=[
                {"language": "en", "title": "English row title", "summary": "English row summary"},
                {"language": "ja", "summary": "日本語要約"},
            ]
        ),
        lang="ja",
    )

    assert event["title"] == "English row title"
    assert event["summary"] == "日本語要約"
    assert event["language"] == "ja"


def test_public_event_translations_select_sql_reads_translation_rows() -> None:
    sql = " ".join(public_event_translations_select_sql(event_alias="pe").split())

    assert "from public_events_translations pet" in sql
    assert "where pet.public_event_id = pe.id" in sql
    assert "'language', pet.language" in sql
    assert "'title', pet.title" in sql
    assert "'summary', pet.summary" in sql


def test_public_event_translation_search_exists_sql_reads_translation_rows() -> None:
    sql = " ".join(public_event_translation_search_exists_sql(event_alias="pe").split())

    assert "from public_events_translations pet_search" in sql
    assert "where pet_search.public_event_id = pe.id" in sql
    assert "pet_search.title ilike %(q)s" in sql
    assert "pet_search.summary ilike %(q)s" in sql


def test_build_filters_searches_translation_rows() -> None:
    where, params = _build_filters(q="日本語")

    assert "public_events_translations pet_search" in where
    assert "pet_search.title ilike %(q)s" in where
    assert params["q"] == "%日本語%"


def test_public_event_translation_rows_use_payload_translations() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "translations": [
                {"language": "zh-Hant", "title": "中文標題", "summary": "中文摘要"},
                {"language": "en", "title": "English title", "summary": "English summary"},
            ],
        }
    )

    rows = public_event_translation_rows(payload)

    assert [(row["language"], row["title"], row["summary"]) for row in rows] == [
        ("zh-Hant", "中文標題", "中文摘要"),
        ("en", "English title", "English summary"),
    ]


def test_public_event_translation_rows_deduplicate_by_language() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "translations": [
                {"language": "en", "title": "Initial English title", "summary": "Initial English summary"},
                {"language": "en", "title": "Updated English title", "summary": "Updated English summary"},
                {"language": "ja", "title": "日本語タイトル", "summary": "日本語要約"},
            ],
        }
    )

    rows = public_event_translation_rows(payload)

    assert [(row["language"], row["title"], row["summary"]) for row in rows] == [
        ("en", "Updated English title", "Updated English summary"),
        ("ja", "日本語タイトル", "日本語要約"),
    ]


def test_shape_public_raw_item_defaults_to_english() -> None:
    item = shape_public_raw_item(raw_item_row(), lang=None)

    assert item["summary"] == "English summary"
    assert item["full_translation"] == "English full translation"
    assert item["language"] == "en"
    assert item["available_languages"] == ["en", "zh-Hant"]
    assert item["translations"] == [
        {
            "language": "en",
            "summary": "English summary",
            "full_translation": "English full translation",
            "status": None,
            "is_truncated": False,
            "source_chars": 100,
            "translation_chars": 120,
        },
        {
            "language": "zh-Hant",
            "summary": "中文摘要",
            "full_translation": "中文全文翻譯",
            "status": None,
            "is_truncated": False,
            "source_chars": 100,
            "translation_chars": 120,
        },
    ]


def test_shape_public_raw_item_selects_arbitrary_translation_language() -> None:
    item = shape_public_raw_item(
        raw_item_row(
            translations=[
                {
                    "language": "ja",
                    "summary": "日本語要約",
                    "full_translation": "日本語全文",
                    "status": "completed",
                    "is_truncated": False,
                    "source_chars": 200,
                    "translation_chars": 120,
                }
            ]
        ),
        lang="ja",
    )

    assert item["summary"] == "日本語要約"
    assert item["full_translation"] == "日本語全文"
    assert item["language"] == "ja"
    assert item["available_languages"] == ["ja"]


def test_public_raw_item_translations_select_sql_reads_translation_rows() -> None:
    sql = " ".join(public_raw_item_translations_select_sql(raw_item_alias="pri").split())

    assert "from public_raw_item_translations prit" in sql
    assert "where prit.public_raw_item_id = pri.id" in sql
    assert "'language', prit.language" in sql
    assert "'summary', prit.summary" in sql
    assert "'full_translation', prit.full_translation" in sql


def test_public_raw_item_translation_search_exists_sql_reads_translation_rows() -> None:
    sql = " ".join(public_raw_item_translation_search_exists_sql(raw_item_alias="pri").split())

    assert "from public_raw_item_translations prit_search" in sql
    assert "where prit_search.public_raw_item_id = pri.id" in sql
    assert "prit_search.summary ilike %(q)s" in sql
    assert "prit_search.full_translation ilike %(q)s" in sql


def test_build_raw_item_filters_searches_translation_rows_and_event_link() -> None:
    event_id = str(uuid4())
    where, params = _build_raw_item_filters(q="日本語", event_id=event_id, min_relevance_score=50)

    assert "public_raw_item_translations prit_search" in where
    assert "prit_search.full_translation ilike %(q)s" in where
    assert "from public_events pe" in where
    assert "pe.upstream_event_id = any(public_raw_items.upstream_event_ids)" in where
    assert params["q"] == "%日本語%"
    assert params["event_id"] == event_id
    assert params["min_relevance_score"] == 50


def test_public_raw_item_translation_rows_use_payload_translations() -> None:
    payload = PublicRawItemIngestRequest.model_validate(
        {
            "schema_version": "public_raw_item.v1",
            "idempotency_key": "raw_item:1:v1",
            "upstream_raw_item_id": str(uuid4()),
            "title": "Title",
            "translations": [
                {
                    "language": "zh-Hant",
                    "summary": "中文摘要",
                    "source_chars": 300,
                },
                {
                    "language": "en",
                    "summary": "English summary",
                    "full_translation": "English full translation",
                    "source_chars": 300,
                },
            ],
        }
    )

    rows = public_raw_item_translation_rows(payload)

    assert [(row["language"], row["summary"], row["full_translation"], row["source_chars"]) for row in rows] == [
        ("zh-Hant", "中文摘要", None, 300),
        ("en", "English summary", "English full translation", 300),
    ]


def test_public_raw_item_translation_rows_prefer_payload_translations() -> None:
    payload = PublicRawItemIngestRequest.model_validate(
        {
            "schema_version": "public_raw_item.v1",
            "idempotency_key": "raw_item:1:v1",
            "upstream_raw_item_id": str(uuid4()),
            "title": "Title",
            "translations": [
                {
                    "language": "en",
                    "summary": "Updated English summary",
                    "full_translation": "Updated English full translation",
                    "status": "completed",
                    "translation_chars": 32,
                },
                {"language": "ja", "summary": "日本語要約", "full_translation": "日本語全文"},
            ],
        }
    )

    rows = public_raw_item_translation_rows(payload)

    assert [(row["language"], row["summary"], row["full_translation"], row["status"]) for row in rows] == [
        ("en", "Updated English summary", "Updated English full translation", "completed"),
        ("ja", "日本語要約", "日本語全文", None),
    ]
