from __future__ import annotations

import asyncio
import logging
import socket
from uuid import uuid4

import httpx

from .db import Database
from .models import AlertDelivery
from .providers import AlertProvider, build_providers
from .security import sanitize_text
from .settings import Settings

logger = logging.getLogger(__name__)


class AlertDispatcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.worker_id = f"{settings.service_name}:{socket.gethostname()}:{uuid4()}"
        self.db = Database(settings.database_url)
        self._handled_count = 0

    async def run(self) -> None:
        await self.db.connect()
        timeout = httpx.Timeout(self.settings.provider_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            providers = build_providers(self.settings, client)
            logger.info(
                "alert_dispatcher_started dry_run=%s dispatch_existing=%s providers=%s",
                self.settings.alert_dry_run,
                self.settings.dispatch_existing_events_on_start,
                sorted(providers.keys()),
            )
            try:
                while True:
                    await self.run_once(providers=providers)
                    if self._budget_reached():
                        logger.info("max alerts per run reached; stopping dispatcher")
                        return
                    await asyncio.sleep(self.settings.poll_interval_seconds)
            finally:
                await self.db.close()

    async def run_once(self, *, providers: dict[str, AlertProvider] | None = None) -> int:
        if providers is None:
            timeout = httpx.Timeout(self.settings.provider_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await self.run_once(providers=build_providers(self.settings, client))

        delivered = 0
        for _ in range(self.settings.alert_batch_size):
            if self._budget_reached():
                break
            alert = await self.db.claim_next_alert(worker_id=self.worker_id)
            if not alert:
                break
            await self._deliver_alert(alert, providers)
            delivered += 1
            self._handled_count += 1
        return delivered

    async def _deliver_alert(self, alert: AlertDelivery, providers: dict[str, AlertProvider]) -> None:
        if self.settings.alert_dry_run:
            logger.info("dry_run_skip_alert alert_id=%s channel=%s event_id=%s", alert.id, alert.channel, alert.event_id)
            await self.db.mark_skipped(
                alert_id=alert.id,
                reason="dry_run",
                provider_response={"dry_run": True, "channel": alert.channel, "message_chars": len(alert.message)},
            )
            return

        provider = providers.get(alert.channel)
        if not provider:
            await self.db.mark_skipped(alert_id=alert.id, reason=f"{alert.channel}_disabled")
            return

        result = await provider.send(alert)
        if result.success:
            await self.db.mark_sent(alert_id=alert.id, provider_response=result.response_json)
            logger.info("alert_sent alert_id=%s channel=%s event_id=%s", alert.id, alert.channel, alert.event_id)
            return

        backoff_seconds = self._backoff_seconds(alert, result.retry_after_seconds)
        max_attempts = self.settings.max_attempts if result.is_transient else alert.attempt_count
        await self.db.mark_failed_or_retry(
            alert=alert,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            provider_response=result.response_json,
            error_message=result.error_message or "provider_send_failed",
        )
        logger.warning(
            "alert_send_failed alert_id=%s channel=%s event_id=%s transient=%s error=%s",
            alert.id,
            alert.channel,
            alert.event_id,
            result.is_transient,
            sanitize_text(result.error_message or "provider_send_failed"),
        )

    def _backoff_seconds(self, alert: AlertDelivery, retry_after_seconds: int | None) -> int:
        if retry_after_seconds is not None:
            return min(self.settings.max_backoff_seconds, retry_after_seconds)
        exponent = max(0, alert.attempt_count - 1)
        return min(self.settings.max_backoff_seconds, self.settings.initial_backoff_seconds * (2**exponent))

    def _budget_reached(self) -> bool:
        return self.settings.max_alerts_per_run > 0 and self._handled_count >= self.settings.max_alerts_per_run
