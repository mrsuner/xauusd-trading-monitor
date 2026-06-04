from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from telegram_channel_publisher.message import build_message, valid_public_url
from telegram_channel_publisher.models import PublicOutboxItem


def make_item(**overrides: object) -> PublicOutboxItem:
    data = {
        "id": uuid4(),
        "event_id": uuid4(),
        "public_title_zh": "伊朗強硬派否認 Trump 的核協議說法",
        "public_summary_zh": "市場先交易樂觀預期，但伊朗安全系統尚未確認，反轉風險升高。",
        "public_source_links": [{"source_name": "Tasnim", "url": "https://example.com/news"}],
        "severity": "S",
        "relevance_score": 92,
        "confirmation_state": "partially_confirmed",
        "topic_tags": ["iran", "trump", "xauusd"],
        "generated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return PublicOutboxItem.model_validate(data)


def test_build_html_message_escapes_content() -> None:
    item = make_item(public_title_zh="Deal <close> & unconfirmed")

    message = build_message(item, parse_mode="HTML", limit=3900)

    assert "<b>[S] Deal &lt;close&gt; &amp; unconfirmed</b>" in message
    assert '<a href="https://example.com/news">Tasnim</a>' in message
    assert "#iran #trump #xauusd" in message


def test_build_plain_message_includes_url() -> None:
    item = make_item()

    message = build_message(item, parse_mode="plain", limit=3900)

    assert "[S] 伊朗強硬派否認 Trump 的核協議說法" in message
    assert "1. Tasnim https://example.com/news" in message


def test_invalid_source_url_is_not_rendered() -> None:
    item = make_item(public_source_links=[{"source_name": "internal", "url": "file:///tmp/private"}])

    message = build_message(item, parse_mode="plain", limit=3900)

    assert "file:///tmp/private" not in message
    assert not valid_public_url("file:///tmp/private")
