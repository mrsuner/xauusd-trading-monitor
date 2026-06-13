from __future__ import annotations

import json
from uuid import uuid4

import httpx

from public_syncer.providers import PublicApiProvider
from public_syncer.settings import Settings


async def test_provider_sends_raw_items_to_raw_ingest_path(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "https://news.example.com")
    monkeypatch.setenv("PUBLIC_SYNC_AUTH_MODE", "bearer")
    monkeypatch.setenv("PUBLIC_SYNC_API_KEY", "secret-token")
    public_raw_item_id = str(uuid4())
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            202,
            json={
                "status": "accepted",
                "public_raw_item_id": public_raw_item_id,
                "idempotency_key": "raw_item:1:v1",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PublicApiProvider(settings=Settings(), client=client)
        result = await provider.send(
            {"schema_version": "public_raw_item.v1", "idempotency_key": "raw_item:1:v1"},
            idempotency_key="raw_item:1:v1",
            ingest_path="/ingest/raw-items",
        )

    assert result.success is True
    assert result.public_raw_item_id == public_raw_item_id
    assert result.public_event_id is None
    assert requests[0].url == "https://news.example.com/ingest/raw-items"
    assert requests[0].headers["Authorization"] == "Bearer secret-token"
    assert json.loads(requests[0].content) == {
        "idempotency_key": "raw_item:1:v1",
        "schema_version": "public_raw_item.v1",
    }
