from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from x_publisher.message import build_post, contains_trade_advice, valid_public_url
from x_publisher.models import PublicOutboxItem


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


def test_build_post_uses_public_payload_and_source_link() -> None:
    item = make_item()

    post = build_post(item, limit=260)

    assert post.startswith("[S] 伊朗強硬派否認 Trump")
    assert "Source: Tasnim" in post
    assert "https://example.com/news" in post
    assert "#XAUUSD" in post
    assert len(post) <= 260


def test_build_post_truncates_to_limit() -> None:
    item = make_item(public_summary_zh="重大消息。" * 100)

    post = build_post(item, limit=180)

    assert len(post) <= 180
    assert "https://example.com/news" in post


def test_invalid_source_url_is_not_used() -> None:
    item = make_item(public_source_links=[{"source_name": "internal", "url": "file:///tmp/private"}])

    post = build_post(item, limit=260)

    assert "file:///tmp/private" not in post
    assert not valid_public_url("file:///tmp/private")


def test_trade_advice_guard_detects_direct_advice() -> None:
    assert contains_trade_advice("建議做多黃金") is True
    assert contains_trade_advice("market is watching gold volatility") is False
