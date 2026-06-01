from __future__ import annotations

import asyncio
import logging
import socket
from uuid import uuid4

import httpx

from .db import Database
from .message import build_message, summary_for
from .models import PublicOutboxItem
from .providers import TelegramChannelProvider
from .settings import Settings

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"C": 0, "B": 1, "A": 2, "S": 3}


class TelegramChannelPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.worker_id = f"{settings.service_name}:{socket.gethostname()}:{uuid4()}"
        self.db = Database(settings.database_url)

    async def run(self) -> None:
        if not self.settings.enabled:
            logger.info("telegram_channel_publisher_disabled")
            while True:
                await asyncio.sleep(3600)

        await self.db.connect()
        timeout = httpx.Timeout(self.settings.provider_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            provider = TelegramChannelProvider(settings=self.settings, client=client)
            logger.info(
                "telegram_channel_publisher_started dry_run=%s channel_configured=%s",
                self.settings.dry_run,
                bool(self.settings.channel_id and self.settings.bot_token),
            )
            try:
                while True:
                    await self.run_once(provider=provider)
                    await asyncio.sleep(self.settings.poll_interval_seconds)
            finally:
                await self.db.close()

    async def run_once(self, *, provider: TelegramChannelProvider | None = None) -> int:
        if not self.settings.enabled:
            logger.info("telegram_channel_publisher_disabled_once")
            return 0

        if provider is None:
            timeout = httpx.Timeout(self.settings.provider_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await self.run_once(provider=TelegramChannelProvider(settings=self.settings, client=client))

        delivered = 0
        for _ in range(self.settings.batch_size):
            if self.settings.max_per_hour > 0 and await self.db.sent_count_last_hour() >= self.settings.max_per_hour:
                logger.info("telegram_channel_rate_limit_reached max_per_hour=%s", self.settings.max_per_hour)
                break

            item = await self.db.claim_next_item(
                worker_id=self.worker_id,
                lock_timeout_seconds=self.settings.lock_timeout_seconds,
                max_attempts=self.settings.max_attempts,
            )
            if not item:
                break
            await self._publish_item(item, provider)
            delivered += 1
        return delivered

    async def _publish_item(self, item: PublicOutboxItem, provider: TelegramChannelProvider) -> None:
        skip_reason = self._skip_reason(item)
        if skip_reason:
            await self.db.mark_skipped(item_id=item.id, reason=skip_reason)
            logger.info("telegram_channel_public_item_skipped item_id=%s reason=%s", item.id, skip_reason)
            return

        message = build_message(item, parse_mode=self.settings.parse_mode, limit=self.settings.message_limit_chars)
        if self.settings.dry_run:
            logger.info("dry_run_skip_telegram_channel_item item_id=%s event_id=%s", item.id, item.event_id)
            await self.db.mark_skipped(
                item_id=item.id,
                reason="dry_run",
                provider_response={"dry_run": True, "message": message},
            )
            return

        result = await provider.send(item, message)
        if result.success:
            await self.db.mark_sent(item_id=item.id, provider_response=result.response_json)
            logger.info("telegram_channel_item_sent item_id=%s event_id=%s", item.id, item.event_id)
            return

        backoff_seconds = result.retry_after_seconds or self.settings.retry_backoff_seconds
        max_attempts = self.settings.max_attempts if result.is_transient else item.retry_count_telegram
        await self.db.mark_failed_or_retry(
            item=item,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            provider_response=result.response_json,
            error_message=result.error_message or "telegram_channel_send_failed",
        )
        logger.warning(
            "telegram_channel_item_send_failed item_id=%s event_id=%s transient=%s error=%s",
            item.id,
            item.event_id,
            result.is_transient,
            result.error_message,
        )

    def _skip_reason(self, item: PublicOutboxItem) -> str | None:
        if not summary_for(item).strip():
            return "missing_public_summary"
        if item.severity == "B" and self.settings.include_b_events:
            return None
        if SEVERITY_RANK.get(item.severity, -1) < SEVERITY_RANK[self.settings.min_severity]:
            return f"severity_below_min:{item.severity}"
        return None
