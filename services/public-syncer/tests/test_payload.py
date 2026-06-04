from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from public_syncer.models import PublicOutboxItem
from public_syncer.payload import build_payload, clamp_text, idempotency_key_for, sanitize_source_links


def make_item() -> PublicOutboxItem:
    event_id = uuid4()
    return PublicOutboxItem(
        id=uuid4(),
        event_id=event_id,
        public_title_zh="標題",
        public_summary_zh="摘要",
        public_title_en="Title",
        public_summary_en="Summary",
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
    assert payload["public_summary_zh"] == "摘要"
    assert payload["public_source_links"] == [
        {"url": "https://example.com/news", "source_name": "Example", "label": "Example"}
    ]
    assert payload["route_metadata"]["public_outbox_id"] == str(item.id)


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
