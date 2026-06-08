from __future__ import annotations

import json

import httpx
import pytest

from tickbase_anomaly_consumer.feed_client import FeedClient
from tickbase_anomaly_consumer.settings import Settings

SETTINGS = Settings(
    DATABASE_URL="postgresql://localhost/test",
    TICKBASE_API_BASE_URL="https://api.example.test",
    TICKBASE_API_KEY="tb_live_secret",
)


def _event_json(event_id: int) -> dict:
    return {
        "id": event_id,
        "rule_id": "gold-1m-10usd",
        "asset_class": "metal",
        "base": "XAU",
        "quote": "USD",
        "direction": "up",
        "metric": "abs",
        "window_secs": 60,
        "threshold": 10.0,
        "change_abs": 15.0,
        "change_pct": 0.6,
        "value_start": 2400.0,
        "value_end": 2415.0,
        "obs_count": 5,
        "window_start": "2026-01-01T00:00:00Z",
        "triggered_at": "2026-01-01T00:01:00Z",
    }


async def test_fetch_page_parses_events_and_sends_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["since"] = request.url.params.get("since")
        return httpx.Response(200, json={"events": [_event_json(3), _event_json(4)]})

    client = FeedClient(SETTINGS)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        events = await client.fetch_page(http, since=2)

    assert [e.id for e in events] == [3, 4]
    assert seen["auth"] == "Bearer tb_live_secret"
    assert seen["since"] == "2"


async def test_stream_parses_frames_and_skips_heartbeats():
    body = (
        ": ping\n\n"
        f"id: 5\nevent: anomaly\ndata: {json.dumps(_event_json(5))}\n\n"
        ": ping\n\n"
        f"id: 6\nevent: anomaly\ndata: {json.dumps(_event_json(6))}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("last-event-id") == "4"
        return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

    client = FeedClient(SETTINGS)
    received = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async for event in client.stream(http, last_event_id=4):
            received.append(event.id)

    assert received == [5, 6]


async def test_stream_ignores_malformed_frame():
    body = "data: not-json\n\n" f"data: {json.dumps(_event_json(9))}\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode())

    client = FeedClient(SETTINGS)
    received = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async for event in client.stream(http, last_event_id=None):
            received.append(event.id)

    assert received == [9]


@pytest.mark.parametrize("status", [401, 500])
async def test_stream_raises_on_http_error(status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=b"")

    client = FeedClient(SETTINGS)
    with pytest.raises(httpx.HTTPStatusError):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async for _ in client.stream(http, last_event_id=None):
                pass
