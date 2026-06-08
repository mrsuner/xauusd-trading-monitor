from __future__ import annotations

import asyncio
import logging

import httpx

from .db import Database
from .feed_client import FeedClient
from .mapping import SeverityThresholds, map_anomaly
from .models import AnomalyEvent
from .settings import Settings

logger = logging.getLogger(__name__)


class AnomalyConsumer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.database_url)
        self.feed = FeedClient(settings)
        self.thresholds = SeverityThresholds(
            s_multiplier=settings.severity_s_multiplier,
            a_multiplier=settings.severity_a_multiplier,
            b_multiplier=settings.severity_b_multiplier,
        )

    async def run(self) -> None:
        if not self.settings.enabled:
            logger.info("anomaly_consumer_disabled")
            while True:
                await asyncio.sleep(3600)

        await self.db.connect()
        timeout = httpx.Timeout(self.settings.request_timeout_seconds, read=None)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                await self._consume_forever(client)
        finally:
            await self.db.close()

    async def run_once(self, client: httpx.AsyncClient) -> int:
        """Single REST catch-up pass from the persisted cursor (used in tests / `once`)."""
        cursor = await self.db.current_cursor()
        start = cursor if cursor > 0 else (self.settings.start_id or 0)
        new_cursor = await self._catch_up(client, since=start)
        return new_cursor - start if new_cursor > start else 0

    async def _initial_resume(self) -> tuple[int | None, bool]:
        cursor = await self.db.current_cursor()
        if cursor > 0:
            return cursor, True
        if self.settings.start_mode == "tail":
            return None, False  # connect fresh at the stream head, no history replay
        if self.settings.start_mode == "earliest":
            return 0, True
        return self.settings.start_id, True

    async def _consume_forever(self, client: httpx.AsyncClient) -> None:
        resume_id, allow_catchup = await self._initial_resume()
        backoff = self.settings.reconnect_initial_backoff_seconds
        logger.info(
            "anomaly_consumer_started start_mode=%s resume_id=%s",
            self.settings.start_mode,
            resume_id,
        )

        while True:
            try:
                if allow_catchup and resume_id is not None:
                    resume_id = await self._catch_up(client, since=resume_id)
                async for event in self.feed.stream(client, last_event_id=resume_id):
                    await self._handle(event)
                    resume_id = event.id
                    allow_catchup = True
                # Stream closed by server without error -> reconnect immediately.
                backoff = self.settings.reconnect_initial_backoff_seconds
            except (httpx.HTTPError, OSError) as exc:
                logger.warning(
                    "anomaly_stream_disconnected error=%s retry_in_seconds=%s",
                    exc.__class__.__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.settings.reconnect_max_backoff_seconds)
                allow_catchup = True
                if resume_id is None:
                    persisted = await self.db.current_cursor()
                    resume_id = persisted if persisted > 0 else None

    async def _catch_up(self, client: httpx.AsyncClient, *, since: int) -> int:
        cursor = since
        while True:
            page = await self.feed.fetch_page(client, since=cursor)
            if not page:
                return cursor
            for event in page:
                await self._handle(event)
                cursor = max(cursor, event.id)

    async def _handle(self, event: AnomalyEvent) -> None:
        mapped = map_anomaly(event, self.thresholds)
        recorded = await self.db.ingest(event, mapped)
        if recorded:
            logger.info(
                "anomaly_ingested tickbase_id=%s severity=%s public=%s rule=%s",
                event.id,
                mapped.severity,
                mapped.to_public,
                event.rule_id,
            )
        else:
            logger.debug("anomaly_duplicate_skipped tickbase_id=%s", event.id)
