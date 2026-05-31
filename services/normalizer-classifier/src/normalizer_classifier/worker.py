from __future__ import annotations

import asyncio
import logging
import socket
from uuid import uuid4

from .db import Database
from .model_client import OpenAIStyleModelClient
from .normalization import normalize_item
from .settings import Settings

logger = logging.getLogger(__name__)


class NormalizerClassifierWorker:
    def __init__(self, settings: Settings, db: Database, model_client: OpenAIStyleModelClient) -> None:
        self.settings = settings
        self.db = db
        self.model_client = model_client
        self.worker_id = f"{socket.gethostname()}-{uuid4()}"
        self._stop_event = asyncio.Event()
        self._model_call_count = 0
        self._model_call_lock = asyncio.Lock()

    async def run(self) -> None:
        await self.db.connect()
        logger.info("normalizer-classifier started worker_id=%s", self.worker_id)
        tasks = [asyncio.create_task(self._loop(i)) for i in range(self.settings.worker_concurrency)]
        try:
            await self._stop_event.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.db.close()

    async def _loop(self, worker_index: int) -> None:
        while not self._stop_event.is_set():
            if await self._model_budget_exhausted():
                await asyncio.sleep(self.settings.poll_interval_seconds)
                continue

            task = await self.db.claim_next_task(worker_id=f"{self.worker_id}-{worker_index}")
            if not task:
                await asyncio.sleep(self.settings.poll_interval_seconds)
                continue

            try:
                normalized = normalize_item(task.raw_item, task.source)
                await self.db.update_normalized_item(raw_item_id=task.raw_item.id, normalized=normalized)

                if not normalized.prefilter_passed:
                    await self.db.complete_skipped(processing_id=task.id, normalized=normalized)
                    logger.info("skipped raw_item_id=%s reason=%s", task.raw_item.id, normalized.filter_reason)
                    continue

                if not await self._reserve_model_call():
                    await self.db.defer_for_model_budget(processing_id=task.id)
                    logger.info("deferred raw_item_id=%s reason=model_call_budget_reached", task.raw_item.id)
                    continue

                model_response = await self.model_client.classify(task.raw_item, task.source, normalized)
                event_id = await self.db.complete_processed(
                    task=task,
                    normalized=normalized,
                    model_response=model_response,
                    relevance_threshold_event=self.settings.relevance_threshold_event,
                )
                logger.info(
                    "processed raw_item_id=%s relevant=%s score=%s event_id=%s",
                    task.raw_item.id,
                    model_response.result.is_relevant,
                    model_response.result.relevance_score,
                    event_id,
                )
            except Exception as exc:
                logger.exception("failed raw_item_id=%s", task.raw_item.id)
                await self.db.mark_failed(
                    processing_id=task.id,
                    attempt_count=task.attempt_count,
                    max_attempts=self.settings.max_attempts,
                    error_message=str(exc),
                )

    async def _model_budget_exhausted(self) -> bool:
        limit = self.settings.max_model_calls_per_run
        if limit == 0:
            return False
        async with self._model_call_lock:
            return self._model_call_count >= limit

    async def _reserve_model_call(self) -> bool:
        limit = self.settings.max_model_calls_per_run
        if limit == 0:
            return True
        async with self._model_call_lock:
            if self._model_call_count >= limit:
                return False
            self._model_call_count += 1
            return True
