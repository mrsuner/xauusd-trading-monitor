from __future__ import annotations

from typing import Any

from .models import PublicOutboxItem


def build_payload(item: PublicOutboxItem) -> dict[str, Any]:
    return {
        "schema_version": "public_event.v1",
        "idempotency_key": idempotency_key_for(item),
        "upstream_event_id": str(item.event_id),
        "event_time": item.event_time.isoformat() if item.event_time else None,
        "generated_at": item.generated_at.isoformat(),
        "severity": item.severity,
        "relevance_score": item.relevance_score,
        "confirmation_state": item.confirmation_state,
        "public_title_zh": item.public_title_zh,
        "public_summary_zh": item.public_summary_zh,
        "public_title_en": item.public_title_en,
        "public_summary_en": item.public_summary_en,
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
