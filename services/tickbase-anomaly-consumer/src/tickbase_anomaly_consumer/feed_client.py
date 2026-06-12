from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from .models import AnomalyEvent
from .settings import Settings

logger = logging.getLogger(__name__)


class FeedClient:
    """HTTP client for the tickbase anomaly feed (REST catch-up + SSE stream)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        base = settings.api_base_url.rstrip("/")
        self._rest_url = f"{base}/v1/anomaly-events"
        self._stream_url = f"{base}/v1/anomaly-events/stream"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers

    async def fetch_page(self, client: httpx.AsyncClient, *, since: int) -> list[AnomalyEvent]:
        """Fetch one cursor page of events with id > `since` (ascending)."""
        resp = await client.get(
            self._rest_url,
            params={"since": since, "limit": self.settings.rest_page_size},
            headers=self._headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        raw_events = body.get("events", []) if isinstance(body, dict) else body
        return [AnomalyEvent.model_validate(item) for item in raw_events]

    async def stream(
        self, client: httpx.AsyncClient, *, last_event_id: int | None
    ) -> AsyncIterator[AnomalyEvent]:
        """Yield events from the SSE stream, resuming after `last_event_id`."""
        headers = self._headers()
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)

        timeout = httpx.Timeout(
            self.settings.request_timeout_seconds,
            read=self.settings.sse_read_timeout_seconds,
        )
        async with client.stream("GET", self._stream_url, headers=headers, timeout=timeout) as resp:
            resp.raise_for_status()
            data_lines: list[str] = []
            async for line in resp.aiter_lines():
                if line == "":
                    event = self._dispatch(data_lines)
                    data_lines = []
                    if event is not None:
                        yield event
                    continue
                if line.startswith(":"):
                    # SSE comment / heartbeat (": ping")
                    continue
                field, _, value = line.partition(":")
                if value.startswith(" "):
                    value = value[1:]
                if field == "data":
                    data_lines.append(value)
                # `id:`, `event:`, `retry:` carry no payload we rely on; the
                # authoritative id lives inside the JSON data.

    @staticmethod
    def _dispatch(data_lines: list[str]) -> AnomalyEvent | None:
        if not data_lines:
            return None
        payload = "\n".join(data_lines)
        try:
            return AnomalyEvent.model_validate(json.loads(payload))
        except (json.JSONDecodeError, ValueError):
            logger.warning("skipping unparseable sse frame", extra={"frame_chars": len(payload)})
            return None
