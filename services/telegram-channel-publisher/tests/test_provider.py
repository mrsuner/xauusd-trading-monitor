from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from telegram_channel_publisher.models import PublicOutboxItem
from telegram_channel_publisher.providers import TelegramChannelProvider
from telegram_channel_publisher.settings import Settings


def make_item() -> PublicOutboxItem:
    return PublicOutboxItem.model_validate(
        {
            "id": uuid4(),
            "event_id": uuid4(),
            "public_title_zh": "Title",
            "public_summary_zh": "Summary",
            "public_source_links": [{"source_name": "Source", "url": "https://example.com"}],
            "severity": "A",
            "generated_at": datetime.now(timezone.utc),
        }
    )


@pytest.mark.asyncio
async def test_provider_sends_message() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 123}})

    settings = Settings(
        DATABASE_URL="postgresql://x:y@localhost/db",
        TELEGRAM_CHANNEL_BOT_TOKEN="token",
        TELEGRAM_CHANNEL_ID="@channel",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TelegramChannelProvider(settings=settings, client=client).send(make_item(), "<b>Hello</b>")

    assert result.success is True
    assert requests[0].url.path == "/bottoken/sendMessage"
    assert requests[0].read()


@pytest.mark.asyncio
async def test_provider_falls_back_to_plain_text_on_parse_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(400, json={"ok": False, "description": "Bad Request: can't parse entities"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 456}})

    settings = Settings(
        DATABASE_URL="postgresql://x:y@localhost/db",
        TELEGRAM_CHANNEL_BOT_TOKEN="token",
        TELEGRAM_CHANNEL_ID="@channel",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TelegramChannelProvider(settings=settings, client=client).send(make_item(), "<b>Broken")

    assert result.success is True
    assert calls == 2
    assert result.response_json["fallback"]["result"]["message_id"] == 456
