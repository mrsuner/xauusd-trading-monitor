from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .db import Database
from .models import RouteDecision, RoutePolicyRuntime, RouteResult
from .policy import route_results
from .settings import Settings

logger = logging.getLogger(__name__)


class EventRouter:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.worker_id = f"{settings.service_name}:{socket.gethostname()}:{uuid4()}"
        self._startup_cutoff = datetime.now(timezone.utc)
        self._handled_count = 0

    async def run(self) -> None:
        await self.db.connect()
        logger.info(
            "event_router_started dispatch_existing=%s routes=%s",
            self.settings.dispatch_existing_events_on_start,
            {
                "private.telegram": self.settings.enable_private_telegram_route,
                "private.pushover": self.settings.enable_private_pushover_route,
                "public.telegram_channel": self.settings.enable_public_telegram_channel_route,
                "public.website": self.settings.enable_public_website_route,
                "public.x": self.settings.enable_public_x_route,
            },
        )
        try:
            while True:
                await self.run_once()
                if self._budget_reached():
                    logger.info("max events per run reached; stopping event router")
                    return
                await asyncio.sleep(self.settings.poll_interval_seconds)
        finally:
            await self.db.close()

    async def run_once(self) -> int:
        since = self._event_scan_cutoff()
        event_ids = await self.db.unrouted_event_ids(since=since, limit=self.settings.event_batch_size)
        routed = 0
        for event_id in event_ids:
            if self._budget_reached():
                break
            event = await self.db.get_event_context(event_id=event_id)
            if not event:
                continue
            runtime = RoutePolicyRuntime(
                backfill_mode=self.settings.backfill_mode,
                is_backfill=bool(event.created_at and event.created_at < self._startup_cutoff),
            )
            if event.source.id:
                runtime.telegram_stats = await self.db.alert_channel_stats(source_id=event.source.id, channel="telegram")
                runtime.pushover_stats = await self.db.alert_channel_stats(source_id=event.source.id, channel="pushover")

            for result in route_results(event, runtime, self.settings):
                await self._apply_route_result(result)

            routed += 1
            self._handled_count += 1
            logger.info("event_routed event_id=%s", event.id)
        if self.settings.public_outbox_translation_enrichment_enabled and self.settings.enable_public_website_route:
            enriched_count, requeued_count = await self.db.enrich_public_outbox_translations(
                languages=self.settings.public_outbox_languages,
                limit=self.settings.public_outbox_translation_enrichment_batch_size,
                lookback_hours=self.settings.public_outbox_translation_enrichment_lookback_hours,
            )
            if enriched_count:
                logger.info(
                    "public_outbox_translations_enriched enriched_count=%s requeued_count=%s",
                    enriched_count,
                    requeued_count,
                )
        return routed

    async def _apply_route_result(self, result: RouteResult) -> None:
        payload_table = "none"
        payload_id = None
        if result.queued and result.alert:
            payload_table = "alerts"
            payload_id = await self.db.create_alert(result.alert)
        elif result.queued and result.public_outbox:
            payload_table = "public_outbox"
            payload_id = await self.db.upsert_public_outbox(result.public_outbox)

        await self.db.upsert_route_decision(
            RouteDecision(
                event_id=result.event_id,
                route_key=result.route_key,
                decision_status="queued" if result.queued else "skipped",
                route_score=result.route_score,
                reason=result.reason,
                payload_table=payload_table,
                payload_id=payload_id,
            )
        )

    def _event_scan_cutoff(self) -> datetime:
        if self.settings.dispatch_existing_events_on_start:
            return datetime.now(timezone.utc) - timedelta(minutes=self.settings.event_lookback_minutes)
        return self._startup_cutoff

    def _budget_reached(self) -> bool:
        return self.settings.max_events_per_run > 0 and self._handled_count >= self.settings.max_events_per_run
