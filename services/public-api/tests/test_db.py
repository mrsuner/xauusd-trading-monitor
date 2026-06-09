from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from public_api.db import (
    _build_filters,
    normalize_public_language,
    public_event_translation_rows,
    public_event_translation_search_exists_sql,
    public_event_translations_select_sql,
    shape_public_event,
)
from public_api.models import PublicEventIngestRequest


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
        "public_title_zh": "中文標題",
        "public_summary_zh": "中文摘要",
        "public_title_en": "English title",
        "public_summary_en": "English summary",
        "public_source_links": [],
        "topic_tags": ["fed"],
        "content_category": "macro_policy",
        "mentioned_actors": ["Federal Reserve"],
        "route_metadata": {},
        "translations": [],
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
    assert event["public_title_zh"] == "中文標題"


def test_shape_public_event_selects_chinese() -> None:
    event = shape_public_event(event_row(), lang="zh-Hant")

    assert event["title"] == "中文標題"
    assert event["summary"] == "中文摘要"
    assert event["language"] == "zh-Hant"
    assert event["available_languages"] == ["en", "zh-Hant"]


def test_shape_public_event_falls_back_to_chinese_when_english_missing() -> None:
    event = shape_public_event(
        event_row(public_title_en=None, public_summary_en=None),
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
    assert event["available_languages"] == ["en", "zh-Hant", "ja"]


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
    assert event["available_languages"] == ["en", "zh-Hant", "ja"]


def test_shape_public_event_falls_back_to_available_language_when_english_missing() -> None:
    event = shape_public_event(
        event_row(
            public_title_en=None,
            public_summary_en=None,
            public_title_zh=None,
            public_summary_zh=None,
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


def test_public_event_translation_rows_use_legacy_fields() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "public_title_zh": "中文標題",
            "public_summary_zh": "中文摘要",
            "public_title_en": "English title",
            "public_summary_en": "English summary",
        }
    )

    rows = public_event_translation_rows(payload)

    assert [(row["language"], row["title"], row["summary"]) for row in rows] == [
        ("zh-Hant", "中文標題", "中文摘要"),
        ("en", "English title", "English summary"),
    ]


def test_public_event_translation_rows_prefer_payload_translations() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "public_title_en": "Legacy English title",
            "public_summary_en": "Legacy English summary",
            "translations": [
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
