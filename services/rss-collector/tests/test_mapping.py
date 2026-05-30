from __future__ import annotations

from uuid import uuid4

from rss_collector.mapping import parse_feed_items
from rss_collector.mapping import parse_html_items
from rss_collector.mapping import parse_datetime
from rss_collector.models import PollingSource


def source(source_type: str = "rss", config: dict[str, object] | None = None) -> PollingSource:
    return PollingSource(
        id=uuid4(),
        name="Test Source",
        handle_or_url="https://example.com/feed.xml",
        source_type=source_type,
        source_group="international_media",
        official_level="official",
        language="en",
        priority="P1",
        source_config=config or {},
    )


def test_parse_datetime_rfc822() -> None:
    parsed = parse_datetime("Sat, 30 May 2026 10:15:00 GMT")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.tzinfo is not None


def test_parse_feed_items() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Example Feed</title>
        <language>en</language>
        <item>
          <guid>item-1</guid>
          <title>Fed statement released</title>
          <link>https://example.com/news/item-1</link>
          <pubDate>Sat, 30 May 2026 10:15:00 GMT</pubDate>
          <description>Policy remains restrictive.</description>
        </item>
      </channel>
    </rss>
    """

    items = parse_feed_items(source(), body)

    assert len(items) == 1
    assert items[0]["external_id"] == "item-1"
    assert items[0]["title"] == "Fed statement released"
    assert items[0]["text_raw"] == "Policy remains restrictive."
    assert items[0]["url"] == "https://example.com/news/item-1"
    assert str(items[0]["dedupe_key"]).startswith("rss:")


def test_parse_html_items() -> None:
    html_source = source(
        "html_polling",
        {
            "list_selector": ".item",
            "title_selector": "a",
            "url_selector": "a",
            "published_selector": "time",
        },
    )
    body = b"""
    <html>
      <body>
        <div class="item">
          <a href="/recent-actions/test">OFAC sanctions update</a>
          <time>Sat, 30 May 2026 10:15:00 GMT</time>
        </div>
      </body>
    </html>
    """

    items = parse_html_items(html_source, body)

    assert len(items) == 1
    assert items[0]["title"] == "OFAC sanctions update"
    assert items[0]["url"] == "https://example.com/recent-actions/test"
    assert str(items[0]["dedupe_key"]).startswith("html:")
