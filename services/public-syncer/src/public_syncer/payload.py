from __future__ import annotations

from typing import Any

from .models import PublicOutboxItem, PublicRawItem
from .security_scrub import sanitize_text

MAX_PUBLIC_TITLE_CHARS = 500
PUBLIC_LANGUAGE_ZH_HANT = "zh-Hant"
PUBLIC_LANGUAGE_EN = "en"


def build_payload(
    item: PublicOutboxItem,
    *,
    sync_languages: tuple[str, ...] = (PUBLIC_LANGUAGE_ZH_HANT, PUBLIC_LANGUAGE_EN),
) -> dict[str, Any]:
    return {
        "schema_version": "public_event.v1",
        "idempotency_key": idempotency_key_for(item),
        "upstream_event_id": str(item.event_id),
        "event_time": item.event_time.isoformat() if item.event_time else None,
        "generated_at": item.generated_at.isoformat(),
        "severity": item.severity,
        "relevance_score": item.relevance_score,
        "confirmation_state": item.confirmation_state,
        "public_title_zh": clamp_text(item.public_title_zh, max_chars=MAX_PUBLIC_TITLE_CHARS),
        "public_summary_zh": item.public_summary_zh,
        "public_title_en": clamp_text(item.public_title_en, max_chars=MAX_PUBLIC_TITLE_CHARS),
        "public_summary_en": item.public_summary_en,
        "translations": public_translation_rows(item, sync_languages=sync_languages),
        "public_source_links": sanitize_source_links(item.public_source_links),
        "topic_tags": item.topic_tags,
        "content_category": None,
        "mentioned_actors": [],
        "route_metadata": {
            "source": "public_outbox",
            "public_outbox_id": str(item.id),
        },
    }


def idempotency_key_for(item: PublicOutboxItem) -> str:
    return f"event:{item.event_id}:v1"


def build_raw_item_payload(
    item: PublicRawItem,
    *,
    max_original_chars: int,
    max_translation_chars: int,
    sync_languages: tuple[str, ...] = (PUBLIC_LANGUAGE_ZH_HANT, PUBLIC_LANGUAGE_EN),
) -> dict[str, Any]:
    original_content, original_truncated, source_text_chars = clamp_public_text(
        item.text_clean,
        max_chars=max_original_chars,
    )
    full_translation_zh, full_translation_zh_truncated, _ = clamp_public_text(
        item.full_translation_zh,
        max_chars=max_translation_chars,
    )
    full_translation_en, full_translation_en_truncated, _ = clamp_public_text(
        item.full_translation_en,
        max_chars=max_translation_chars,
    )
    return {
        "schema_version": "public_raw_item.v1",
        "idempotency_key": raw_item_idempotency_key_for(item),
        "upstream_raw_item_id": str(item.id),
        "source": {
            "name": clamp_text(item.source_name, max_chars=120),
            "source_type": clamp_text(item.source_type, max_chars=80),
            "source_group": clamp_text(item.source_group, max_chars=80),
            "official_level": clamp_text(item.official_level, max_chars=80),
            "priority": clamp_text(item.priority, max_chars=20),
        },
        "source_url": sanitize_public_url(item.url),
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "ingested_at": item.ingested_at.isoformat(),
        "edited_at": item.edited_at.isoformat() if item.edited_at else None,
        "title": clamp_text(item.title, max_chars=MAX_PUBLIC_TITLE_CHARS),
        "original_content": original_content,
        "language": clamp_text(item.language, max_chars=35),
        "media_type": clamp_text(item.media_type, max_chars=40),
        "summary_zh": item.summary_zh,
        "summary_en": item.summary_en,
        "full_translation_zh": full_translation_zh,
        "full_translation_en": full_translation_en,
        "translations": raw_item_translation_rows(
            item,
            max_translation_chars=max_translation_chars,
            sync_languages=sync_languages,
        ),
        "classification": {
            "is_relevant": item.is_relevant,
            "relevance_score": item.relevance_score,
            "filter_reason": clamp_text(item.filter_reason, max_chars=500),
            "stage": clamp_text(item.classification_stage, max_chars=80),
            "status": clamp_text(item.classification_status, max_chars=80),
        },
        "content_category": clamp_text(item.content_category, max_chars=80),
        "topic_tags": normalize_text_list(item.topic_tags),
        "mentioned_actors": normalize_text_list(item.mentioned_actors),
        "upstream_event_ids": [str(event_id) for event_id in item.upstream_event_ids],
        "scrub_metadata": {
            "source": "raw_items",
            "source_updated_at": item.source_updated_at.isoformat(),
            "original_content_truncated": original_truncated,
            "full_translation_zh_truncated": full_translation_zh_truncated,
            "full_translation_en_truncated": full_translation_en_truncated,
            "source_text_chars": source_text_chars,
            "max_original_content_chars": max_original_chars,
            "max_full_translation_chars": max_translation_chars,
        },
    }


def raw_item_idempotency_key_for(item: PublicRawItem) -> str:
    return f"raw_item:{item.id}:v1"


def public_translation_rows(
    item: PublicOutboxItem,
    *,
    sync_languages: tuple[str, ...] = (PUBLIC_LANGUAGE_ZH_HANT, PUBLIC_LANGUAGE_EN),
) -> list[dict[str, str | None]]:
    allowed_languages = set(sync_languages)
    has_allowed_translation_rows = any(
        translation.language
        and translation.language in allowed_languages
        and (translation.title or translation.summary)
        for translation in item.translations
    )
    rows = [
        {
            "language": translation.language,
            "title": clamp_text(translation.title, max_chars=MAX_PUBLIC_TITLE_CHARS),
            "summary": translation.summary,
        }
        for translation in item.translations
        if translation.language
        and translation.language in allowed_languages
        and (translation.title or translation.summary)
        and (translation.status is None or translation.status == "approved")
    ]
    if rows or has_allowed_translation_rows:
        return rows

    fallback_rows: list[dict[str, str | None]] = []
    for language in sync_languages:
        if language == PUBLIC_LANGUAGE_ZH_HANT:
            add_public_translation_row(
                fallback_rows,
                language=PUBLIC_LANGUAGE_ZH_HANT,
                title=item.public_title_zh,
                summary=item.public_summary_zh,
            )
        elif language == PUBLIC_LANGUAGE_EN:
            add_public_translation_row(
                fallback_rows,
                language=PUBLIC_LANGUAGE_EN,
                title=item.public_title_en,
                summary=item.public_summary_en,
            )
    return fallback_rows


def add_public_translation_row(
    rows: list[dict[str, str | None]],
    *,
    language: str,
    title: str | None,
    summary: str | None,
) -> None:
    if not title and not summary:
        return
    rows.append(
        {
            "language": language,
            "title": clamp_text(title, max_chars=MAX_PUBLIC_TITLE_CHARS),
            "summary": summary,
        }
    )


def clamp_text(value: str | None, *, max_chars: int) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def clamp_public_text(value: str | None, *, max_chars: int) -> tuple[str | None, bool, int | None]:
    if value is None:
        return None, False, None
    text = sanitize_text(" ".join(value.split()), limit=max(len(value), max_chars + 1))
    source_chars = len(text)
    if len(text) <= max_chars:
        return text or None, False, source_chars
    return text[: max_chars - 1].rstrip() + "…", True, source_chars


def raw_item_translation_rows(
    item: PublicRawItem,
    *,
    max_translation_chars: int,
    sync_languages: tuple[str, ...] = (PUBLIC_LANGUAGE_ZH_HANT, PUBLIC_LANGUAGE_EN),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed_languages = set(sync_languages)
    for translation in item.translations:
        if not translation.language or translation.language in seen or translation.language not in allowed_languages:
            continue
        summary = translation.summary.strip() if translation.summary else None
        full_translation, truncated, translation_chars = clamp_public_text(
            translation.full_translation,
            max_chars=max_translation_chars,
        )
        if not summary and not full_translation:
            continue
        rows.append(
            {
                "language": translation.language,
                "summary": summary,
                "full_translation": full_translation,
                "status": translation.status,
                "is_truncated": truncated or translation.status == "completed_truncated",
                "source_chars": translation.input_chars,
                "translation_chars": translation_chars,
            }
        )
        seen.add(translation.language)
    return rows[:10]


def sanitize_public_url(value: str | None) -> str | None:
    url = str(value or "").strip()
    if not url.startswith(("https://", "http://")):
        return None
    return url[:1000]


def normalize_text_list(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized[:80])
    return result[:30]


def sanitize_source_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for link in links:
        url = str(link.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        result.append(
            {
                "url": url,
                "source_name": str(link.get("source_name") or link.get("label") or "").strip()[:120] or None,
                "label": str(link.get("label") or link.get("source_name") or "").strip()[:120] or None,
            }
        )
    return result[:10]
