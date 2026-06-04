from __future__ import annotations

import asyncio
import logging
import socket
from uuid import uuid4

import httpx

from .db import Database
from .models import PublicOutboxItem
from .payload import build_payload, idempotency_key_for
from .providers import PublicApiProvider
from .security_scrub import sanitize_text
from .settings import Settings

logger = logging.getLogger(__name__)


class PublicSyncer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.worker_id = f"{settings.service_name}:{socket.gethostname()}:{uuid4()}"
        self.db = Database(settings.database_url)

    async def run(self) -> None:
        if not self.settings.enabled:
            logger.info("public_syncer_disabled")
            while True:
                await asyncio.sleep(3600)

        await self.db.connect()
        timeout = httpx.Timeout(self.settings.provider_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            provider = PublicApiProvider(settings=self.settings, client=client)
            logger.info(
                "public_syncer_started dry_run=%s auth_mode=%s target=%s",
                self.settings.dry_run,
                self.settings.auth_mode,
                self.settings.public_api_base_url,
            )
            try:
                while True:
                    await self.run_once(provider=provider)
                    await asyncio.sleep(self.settings.poll_interval_seconds)
            finally:
                await self.db.close()

    async def run_once_with_lifecycle(self) -> int:
        if not self.settings.enabled:
            logger.info("public_syncer_disabled_once")
            return 0
        await self.db.connect()
        timeout = httpx.Timeout(self.settings.provider_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                return await self.run_once(provider=PublicApiProvider(settings=self.settings, client=client))
            finally:
                await self.db.close()

    async def run_once(self, *, provider: PublicApiProvider) -> int:
        if not self.settings.enabled:
            logger.info("public_syncer_disabled_once")
            return 0

        synced = 0
        for _ in range(self.settings.batch_size):
            if self.settings.max_per_minute > 0 and await self.db.sent_count_last_minute() >= self.settings.max_per_minute:
                logger.info("public_syncer_rate_limit_reached max_per_minute=%s", self.settings.max_per_minute)
                break

            item = await self.db.claim_next_item(
                worker_id=self.worker_id,
                lock_timeout_seconds=self.settings.lock_timeout_seconds,
                max_attempts=self.settings.max_attempts,
            )
            if not item:
                break
            await self._sync_item(item, provider)
            synced += 1
        return synced

    async def _sync_item(self, item: PublicOutboxItem, provider: PublicApiProvider) -> None:
        payload = build_payload(item)
        idempotency_key = idempotency_key_for(item)

        if self.settings.dry_run:
            logger.info("dry_run_skip_public_sync item_id=%s event_id=%s", item.id, item.event_id)
            await self.db.mark_skipped(
                item_id=item.id,
                reason="dry_run",
                provider_response={
                    "dry_run": True,
                    "schema_version": payload.get("schema_version"),
                    "idempotency_key": idempotency_key,
                },
            )
            return

        result = await provider.send(payload, idempotency_key=idempotency_key)
        if result.success:
            await self.db.mark_sent(
                item_id=item.id,
                provider_response=result.response_json,
                external_web_id=result.public_event_id,
            )
            logger.info("public_item_synced item_id=%s event_id=%s duplicate=%s", item.id, item.event_id, result.is_duplicate)
            return

        backoff_seconds = result.retry_after_seconds or self.settings.retry_backoff_seconds
        max_attempts = self.settings.max_attempts if result.is_transient else item.retry_count_web
        await self.db.mark_failed_or_retry(
            item=item,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            provider_response=result.response_json,
            error_message=result.error_message or "public_sync_failed",
        )
        logger.warning(
            "public_item_sync_failed item_id=%s event_id=%s transient=%s status_code=%s error=%s",
            item.id,
            item.event_id,
            result.is_transient,
            result.status_code,
            sanitize_text(result.error_message or "public_sync_failed"),
        )
