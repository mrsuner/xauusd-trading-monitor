from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from x_publisher.message import build_post, contains_trade_advice, contains_url, valid_public_url
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


def test_build_post_uses_public_payload_and_source_attribution_without_url() -> None:
    item = make_item()

    post = build_post(item, limit=260)

    assert post.startswith("[S] 伊朗強硬派否認 Trump")
    assert "來源：Tasnim" in post
    assert "狀態：部分確認" in post
    assert "Source:" not in post
    assert "Status:" not in post
    assert "https://example.com/news" not in post
    assert "http://" not in post
    assert "https://" not in post
    assert "#XAUUSD" in post
    assert len(post) <= 260


def test_build_post_truncates_to_limit() -> None:
    item = make_item(public_summary_zh="重大消息。" * 100)

    post = build_post(item, limit=180)

    assert len(post) <= 180
    assert "https://example.com/news" not in post


def test_build_post_strips_urls_from_public_text() -> None:
    item = make_item(
        public_title_zh="Fed headline https://example.com/title",
        public_summary_zh="Market watching https://example.com/body for confirmation.",
        public_source_links=[{"source_name": "Source https://example.com/source", "url": "https://example.com/news"}],
    )

    post = build_post(item, limit=260)

    assert "Fed headline" in post
    assert "Market watching for confirmation." in post
    assert "來源：Source" in post
    assert "http://" not in post
    assert "https://" not in post


def test_build_post_does_not_fallback_to_english_public_copy() -> None:
    item = make_item(
        public_title_zh=None,
        public_summary_zh=None,
        public_title_en="English nuclear headline",
        public_summary_en="Market is watching the headline.",
        translations=[{"language": "ja", "title": "Japanese website title", "summary": "Japanese website summary."}],
    )

    post = build_post(item, limit=260)

    assert "公開事件更新" in post
    assert "nuclear" not in post.lower()
    assert "market" not in post.lower()
    assert "Japanese website title" not in post
    assert "Japanese website summary" not in post


def test_invalid_source_url_is_not_used() -> None:
    item = make_item(public_source_links=[{"source_name": "internal", "url": "file:///tmp/private"}])

    post = build_post(item, limit=260)

    assert "file:///tmp/private" not in post
    assert not valid_public_url("file:///tmp/private")


def test_contains_url_detects_http_urls() -> None:
    assert contains_url("see https://example.com/news") is True
    assert contains_url("Source: Tasnim") is False


def test_trade_advice_guard_detects_direct_advice() -> None:
    assert contains_trade_advice("建議做多黃金") is True
    assert contains_trade_advice("market is watching gold volatility") is False
