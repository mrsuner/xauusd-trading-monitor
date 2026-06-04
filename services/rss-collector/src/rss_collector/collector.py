from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx

from .db import Database
from .http import fetch_source
from .mapping import parse_feed_items
from .mapping import parse_html_items
from .models import PollingSource
from .settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class SourceState:
    source: PollingSource
    next_poll_at: datetime
    failure_count: int = 0


class RssCollector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.psycopg_database_url())
        self._states: dict[str, SourceState] = {}
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        await self.db.connect()
        timeout = httpx.Timeout(self.settings.default_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await self.refresh_sources()
            refresh_task = asyncio.create_task(self.refresh_loop(), name="rss-source-refresh")
            try:
                logger.info("rss collector started", extra={"sources": len(self._states)})
                await self.poll_loop(client)
            finally:
                self._stop_event.set()
                refresh_task.cancel()
                await self.db.close()

    async def refresh_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self.settings.source_refresh_interval_seconds)
            await self.refresh_sources()

    async def refresh_sources(self) -> None:
        sources = await self.db.fetch_enabled_sources()
        active_ids = {str(source.id) for source in sources}
        now = datetime.now(UTC)

        for source in sources:
            source_id = str(source.id)
            existing = self._states.get(source_id)
            if existing:
                existing.source = source
            else:
                self._states[source_id] = SourceState(source=source, next_poll_at=now)

        for source_id in list(self._states):
            if source_id not in active_ids:
                self._states.pop(source_id, None)

    async def poll_loop(self, client: httpx.AsyncClient) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(UTC)
            due_states = [state for state in self._states.values() if state.next_poll_at <= now]
            if not due_states:
                await asyncio.sleep(1)
                continue

            await asyncio.gather(*(self.poll_source(client, state) for state in due_states))

    async def poll_source(self, client: httpx.AsyncClient, state: SourceState) -> None:
        source = state.source
        now = datetime.now(UTC)

        try:
            result = await fetch_source(
                client,
                source,
                self.settings.user_agent,
                source.request_timeout_seconds(self.settings.default_request_timeout_seconds),
            )

            await self.db.update_source_poll_metadata(
                source_id=source.id,
                etag=result.etag,
                last_modified=result.last_modified,
                last_polled_at=now,
            )

            if result.status_code == 304:
                await self.db.upsert_source_health(
                    source_id=source.id,
                    service_name=self.settings.service_name,
                    status="healthy",
                    last_polled_at=now,
                    last_success_at=now,
                    metadata={"http_status": result.status_code, "parsed_items": 0, "ingested_items": 0},
                )
                state.failure_count = 0
                state.next_poll_at = self.next_poll_time(source, 0)
                return

            if result.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {result.status_code}",
                    request=httpx.Request("GET", source.handle_or_url),
                    response=httpx.Response(result.status_code),
                )

            raw_items = self.parse_source_items(source, result.body)
            for raw_item in raw_items:
                await self.db.upsert_raw_item(raw_item)

            await self.db.upsert_source_health(
                source_id=source.id,
                service_name=self.settings.service_name,
                status="healthy",
                last_polled_at=now,
                last_success_at=datetime.now(UTC),
                metadata={
                    "http_status": result.status_code,
                    "parsed_items": len(raw_items),
                    "ingested_items": len(raw_items),
                },
            )
            state.failure_count = 0
            state.next_poll_at = self.next_poll_time(source, 0)
            logger.info("source polled", extra={"source": source.name, "items": len(raw_items), "status": result.status_code})
        except Exception as exc:
            state.failure_count += 1
            backoff = self.backoff_seconds(state.failure_count)
            state.next_poll_at = datetime.now(UTC) + timedelta(seconds=backoff)
            logger.exception("source poll failed", extra={"source": source.name, "backoff_seconds": backoff})
            await self.db.upsert_source_health(
                source_id=source.id,
                service_name=self.settings.service_name,
                status="degraded",
                last_polled_at=now,
                last_error_at=datetime.now(UTC),
                last_error_message=str(exc),
                metadata={"failure_count": state.failure_count, "next_backoff_seconds": backoff},
            )

    def parse_source_items(self, source: PollingSource, body: bytes) -> list[dict[str, object]]:
        if source.source_type in ("rss", "atom"):
            return parse_feed_items(source, body)
        if source.source_type == "html_polling":
            return parse_html_items(source, body)
        raise ValueError(f"unsupported source_type: {source.source_type}")

    def next_poll_time(self, source: PollingSource, jitter_seconds: int = 5) -> datetime:
        interval = source.poll_interval_seconds(self.settings.default_poll_interval_seconds)
        jitter = random.randint(0, jitter_seconds) if jitter_seconds > 0 else 0
        return datetime.now(UTC) + timedelta(seconds=interval + jitter)

    @staticmethod
    def backoff_seconds(failure_count: int) -> int:
        base = min(300, 5 * (2 ** max(0, failure_count - 1)))
        return base + random.randint(0, min(30, base))
