from __future__ import annotations

import asyncio
import logging
import socket
from uuid import uuid4

from .db import Database
from .model_client import ModelClientError, OpenAIStyleModelClient
from .normalization import normalize_item
from .settings import Settings

logger = logging.getLogger(__name__)


class NormalizerClassifierWorker:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        model_client: OpenAIStyleModelClient,
        translation_model_clients: list[OpenAIStyleModelClient] | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.model_client = model_client
        self.translation_model_clients = translation_model_clients or []
        self.worker_id = f"{socket.gethostname()}-{uuid4()}"
        self._stop_event = asyncio.Event()
        self._classification_call_count = 0
        self._translation_call_count = 0
        self._translation_paid_fallback_call_count = 0
        self._budget_lock = asyncio.Lock()

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
            if await self._classification_budget_exhausted():
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
                    await self.db.update_translation_skipped(raw_item_id=task.raw_item.id, reason="prefilter_skipped")
                    await self.db.complete_skipped(processing_id=task.id, normalized=normalized)
                    logger.info("skipped raw_item_id=%s reason=%s", task.raw_item.id, normalized.filter_reason)
                    continue

                if not await self._reserve_classification_call():
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
                await self.db.insert_ai_model_call(
                    usage=model_response.usage,
                    raw_item_id=task.raw_item.id,
                    event_id=event_id,
                    source_id=task.source.id,
                )
                await self._run_translation_summary(task, normalized)
                logger.info(
                    "processed raw_item_id=%s relevant=%s score=%s event_id=%s",
                    task.raw_item.id,
                    model_response.result.is_relevant,
                    model_response.result.relevance_score,
                    event_id,
                )
            except Exception as exc:
                logger.exception("failed raw_item_id=%s", task.raw_item.id)
                if isinstance(exc, ModelClientError) and exc.usage:
                    await self.db.insert_ai_model_call(
                        usage=exc.usage,
                        raw_item_id=task.raw_item.id,
                        source_id=task.source.id,
                    )
                await self.db.mark_failed(
                    processing_id=task.id,
                    attempt_count=task.attempt_count,
                    max_attempts=self.settings.max_attempts,
                    error_message=str(exc),
                )

    async def _classification_budget_exhausted(self) -> bool:
        limit = self._classification_call_limit()
        if limit == 0:
            return False
        async with self._budget_lock:
            return self._classification_call_count >= limit

    async def _reserve_classification_call(self) -> bool:
        limit = self._classification_call_limit()
        if limit == 0:
            return True
        async with self._budget_lock:
            if self._classification_call_count >= limit:
                return False
            self._classification_call_count += 1
            return True

    def _classification_call_limit(self) -> int:
        return self.settings.max_classification_calls_per_run or self.settings.max_model_calls_per_run

    async def _reserve_translation_call(self) -> bool:
        limit = self.settings.max_translation_calls_per_run
        if limit == 0:
            return True
        async with self._budget_lock:
            if self._translation_call_count >= limit:
                return False
            self._translation_call_count += 1
            return True

    async def _reserve_translation_paid_fallback_call(self) -> bool:
        limit = self.settings.max_translation_paid_fallback_calls_per_run
        if limit == 0:
            return True
        async with self._budget_lock:
            if self._translation_paid_fallback_call_count >= limit:
                return False
            self._translation_paid_fallback_call_count += 1
            return True

    async def _run_translation_summary(self, task, normalized: object) -> None:  # noqa: ANN001
        if not self.translation_model_clients:
            await self.db.update_translation_skipped(raw_item_id=task.raw_item.id, reason="translation_model_disabled")
            return
        if task.source.translation_policy == "disabled":
            await self.db.update_translation_skipped(raw_item_id=task.raw_item.id, reason="source_translation_disabled")
            return

        text, truncated = self._translation_input_text(task.source, normalized.text_clean)
        full_translation_required = task.source.translation_policy == "full" or task.source.always_full_translate
        last_error = None

        for index, client in enumerate(self.translation_model_clients):
            is_paid_fallback = index > 0
            if is_paid_fallback and not await self._reserve_translation_paid_fallback_call():
                last_error = "translation_paid_fallback_budget_reached"
                break
            if not await self._reserve_translation_call():
                last_error = "translation_call_budget_reached"
                break
            try:
                response = await client.summarize_and_translate(
                    task.raw_item,
                    task.source,
                    normalized,
                    full_translation_required=full_translation_required,
                    input_text=text,
                    truncated=truncated,
                )
                await self.db.update_translation_result(
                    raw_item_id=task.raw_item.id,
                    response=response,
                    status="completed_truncated" if truncated else "completed",
                    input_chars=len(text),
                )
                await self.db.insert_ai_model_call(
                    usage=response.usage,
                    raw_item_id=task.raw_item.id,
                    source_id=task.source.id,
                )
                logger.info(
                    "translation summary raw_item_id=%s provider=%s model=%s truncated=%s",
                    task.raw_item.id,
                    response.provider,
                    response.model,
                    truncated,
                )
                return
            except Exception as exc:
                last_error = str(exc)
                if isinstance(exc, ModelClientError) and exc.usage:
                    await self.db.insert_ai_model_call(
                        usage=exc.usage,
                        raw_item_id=task.raw_item.id,
                        source_id=task.source.id,
                    )
                logger.warning(
                    "translation summary failed raw_item_id=%s provider=%s model=%s error=%s",
                    task.raw_item.id,
                    client.provider,
                    client.model,
                    exc,
                )

        await self.db.update_translation_failed(
            raw_item_id=task.raw_item.id,
            provider=self.translation_model_clients[-1].provider,
            model=self.translation_model_clients[-1].model,
            error_message=last_error or "translation_failed",
        )

    def _translation_input_text(self, source, text: str) -> tuple[str, bool]:  # noqa: ANN001
        source_limit = source.translation_max_chars
        if source_limit is None:
            if source.always_full_translate or source.translation_priority == "high" or source.priority in {"P0", "P1"}:
                source_limit = self.settings.translation_high_priority_max_chars
            else:
                source_limit = self.settings.translation_default_max_chars

        effective_limit = min(source_limit, self.settings.translation_single_call_max_chars)
        if effective_limit <= 0:
            return "", bool(text)
        if len(text) <= effective_limit:
            return text, False
        return text[:effective_limit], True
