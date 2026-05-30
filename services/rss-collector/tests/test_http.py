from __future__ import annotations

from uuid import uuid4

from rss_collector.http import request_headers
from rss_collector.models import PollingSource


def test_request_headers_use_conditional_fetch_metadata() -> None:
    source = PollingSource(
        id=uuid4(),
        name="Feed",
        handle_or_url="https://example.com/feed.xml",
        source_type="rss",
        source_group="us_fed",
        official_level="official",
        language="en",
        priority="P0",
        source_config={"etag": '"abc"', "last_modified": "Sat, 30 May 2026 10:15:00 GMT"},
    )

    headers = request_headers(source, "TestAgent/1.0")

    assert headers["User-Agent"] == "TestAgent/1.0"
    assert headers["If-None-Match"] == '"abc"'
    assert headers["If-Modified-Since"] == "Sat, 30 May 2026 10:15:00 GMT"
