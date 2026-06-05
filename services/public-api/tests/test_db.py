from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from public_api.db import normalize_public_language, shape_public_event


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
    }
    row.update(overrides)
    return row


def test_normalize_public_language_defaults_to_english() -> None:
    assert normalize_public_language(None) == "en"
    assert normalize_public_language("fr") == "en"
    assert normalize_public_language("en") == "en"
    assert normalize_public_language("zh-Hant") == "zh-Hant"


def test_shape_public_event_defaults_to_english() -> None:
    event = shape_public_event(event_row(), lang=None)

    assert event["title"] == "English title"
    assert event["summary"] == "English summary"
    assert event["language"] == "en"
    assert event["available_languages"] == ["en", "zh-Hant"]
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
