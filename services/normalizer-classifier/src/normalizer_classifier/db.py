from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import (
    AIModelCallUsage,
    AuxiliaryModelResponse,
    AuxiliaryTextResult,
    ClassificationResult,
    ModelResponse,
    NormalizedItem,
    ProcessingTask,
    RawItem,
    SourceMetadata,
)
from .normalization import severity_for
from .taxonomy import CategoryOption, TagOption, TaxonomyContext, normalize_actors, normalize_category, normalize_topic_tags

logger = logging.getLogger(__name__)

DEFAULT_RAW_ITEM_TRANSLATION_LANGUAGES = ("zh-Hant", "en")
RAW_ITEM_TRANSLATION_COMPLETED_STATUSES = {"completed", "completed_truncated"}


def aggregate_raw_item_translation_status(statuses: list[str]) -> str:
    if not statuses:
        return "pending"
    if all(status == "pending" for status in statuses):
        return "pending"
    if all(status == "skipped" for status in statuses):
        return "skipped"
    if all(status == "failed" for status in statuses):
        return "failed"
    if all(status in RAW_ITEM_TRANSLATION_COMPLETED_STATUSES for status in statuses):
        return "completed_truncated" if "completed_truncated" in statuses else "completed"
    if any(status in RAW_ITEM_TRANSLATION_COMPLETED_STATUSES for status in statuses):
        return "partial_completed"
    if "pending" in statuses:
        return "pending"
    if "failed" in statuses:
        return "failed"
    return "skipped"


def raw_item_translation_rows_for_result(
    result: AuxiliaryTextResult,
    *,
    status: str,
    model_provider: str | None,
    model: str | None,
    input_chars: int | None,
    languages: tuple[str, ...] = DEFAULT_RAW_ITEM_TRANSLATION_LANGUAGES,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_row(language: str, summary: str | None, full_translation: str | None) -> None:
        if not language or language in seen:
            return
        seen.add(language)
        rows.append(
            {
                "language": language,
                "summary": summary,
                "full_translation": full_translation,
                "status": status,
                "model_provider": model_provider,
                "model": model,
                "error": None,
                "input_chars": input_chars,
            }
        )

    for language in languages:
        translation = result.translation_for(language)
        if translation is None:
            continue
        append_row(
            language,
            translation.summary,
            translation.full_translation,
        )
    return rows


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("invalid integer environment value", extra={"env_name": name, "env_value": raw})
        return default
    return max(value, 1)


def _positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("invalid float environment value", extra={"env_name": name, "env_value": raw})
        return default
    return max(value, 0.1)


class Database:
    def __init__(
        self,
        database_url: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        translation_output_languages: tuple[str, ...] = DEFAULT_RAW_ITEM_TRANSLATION_LANGUAGES,
    ) -> None:
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._translation_output_languages = translation_output_languages
        self._pool = self._create_pool()

    def _create_pool(self) -> AsyncConnectionPool:
        return AsyncConnectionPool(
            self._database_url,
            min_size=self._min_size,
            max_size=self._max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    async def connect(self) -> None:
        max_attempts = _positive_int_env("DB_CONNECT_MAX_ATTEMPTS", 10)
        delay_seconds = _positive_float_env("DB_CONNECT_INITIAL_BACKOFF_SECONDS", 1.0)
        max_delay_seconds = _positive_float_env("DB_CONNECT_MAX_BACKOFF_SECONDS", 30.0)

        for attempt in range(1, max_attempts + 1):
            try:
                await self._pool.open(wait=True)
                return
            except Exception:
                with suppress(Exception):
                    await self._pool.close()
                if attempt >= max_attempts:
                    logger.exception(
                        "database pool connection failed after retries",
                        extra={"attempt": attempt, "max_attempts": max_attempts},
                    )
                    raise
                logger.warning(
                    "database pool connection failed; retrying",
                    extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_in_seconds": delay_seconds,
                    },
                    exc_info=True,
                )
                await asyncio.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, max_delay_seconds)
                self._pool = self._create_pool()

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def cursor(self) -> AsyncIterator[psycopg.AsyncCursor[Any]]:
        async with self._pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    yield cur

    async def claim_next_task(self, *, worker_id: str, stale_task_timeout_seconds: int) -> ProcessingTask | None:
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_item_processing
                set status = 'retry',
                    next_retry_at = now(),
                    locked_by = null,
                    locked_at = null,
                    error_message = coalesce(error_message, 'stale_running_task_recovered'),
                    updated_at = now()
                where status = 'running'
                  and locked_at is not null
                  and locked_at < now() - (%(stale_task_timeout_seconds)s * interval '1 second')
                """,
                {"stale_task_timeout_seconds": stale_task_timeout_seconds},
            )
            await cur.execute(
                """
                with claimed as (
                  select p.id
                  from raw_item_processing p
                  where p.status in ('pending', 'retry')
                    and (p.next_retry_at is null or p.next_retry_at <= now())
                  order by p.created_at
                  for update skip locked
                  limit 1
                )
                update raw_item_processing p
                set status = 'running',
                    stage = 'normalize',
                    locked_by = %(worker_id)s,
                    locked_at = now(),
                    attempt_count = p.attempt_count + 1,
                    error_message = null
                from claimed
                where p.id = claimed.id
                returning p.*
                """,
                {"worker_id": worker_id},
            )
            processing = await cur.fetchone()
            if not processing:
                return None

            await cur.execute(
                """
                select
                  r.*,
                  s.name as source_name,
                  s.handle_or_url,
                  s.source_type,
                  s.source_group,
                  s.official_level,
                  s.stance,
                  s.language as source_language,
                  s.priority,
                  s.reliability_score,
                  s.latency_score,
                  s.requires_confirmation,
                  s.translation_policy,
                  s.translation_priority,
                  s.translation_max_chars,
                  s.always_full_translate
                from raw_items r
                join sources s on s.id = r.source_id
                where r.id = %(raw_item_id)s
                """,
                {"raw_item_id": processing["raw_item_id"]},
            )
            row = await cur.fetchone()

        if not row:
            return None

        return ProcessingTask(
            id=processing["id"],
            attempt_count=processing["attempt_count"],
            raw_item=RawItem.model_validate(row),
            source=SourceMetadata(
                id=row["source_id"],
                name=row["source_name"],
                handle_or_url=row["handle_or_url"],
                source_type=row["source_type"],
                source_group=row["source_group"],
                official_level=row["official_level"],
                stance=row["stance"],
                language=row["source_language"],
                priority=row["priority"],
                reliability_score=row["reliability_score"],
                latency_score=row["latency_score"],
                requires_confirmation=row["requires_confirmation"],
                translation_policy=row["translation_policy"],
                translation_priority=row["translation_priority"],
                translation_max_chars=row["translation_max_chars"],
                always_full_translate=row["always_full_translate"],
            ),
        )

    async def insert_ai_model_call(
        self,
        *,
        usage: AIModelCallUsage,
        raw_item_id: Any | None = None,
        event_id: Any | None = None,
        source_id: Any | None = None,
    ) -> None:
        async with self.cursor() as cur:
            await cur.execute(
                """
                insert into ai_model_calls (
                  raw_item_id,
                  event_id,
                  source_id,
                  service_name,
                  ai_layer,
                  route_name,
                  provider,
                  model_name,
                  request_kind,
                  input_tokens,
                  output_tokens,
                  total_tokens,
                  estimated_cost_usd,
                  latency_ms,
                  success,
                  error_type,
                  error_message,
                  response_format,
                  usage_json,
                  request_hash
                )
                values (
                  %(raw_item_id)s,
                  %(event_id)s,
                  %(source_id)s,
                  %(service_name)s,
                  %(ai_layer)s,
                  %(route_name)s,
                  %(provider)s,
                  %(model_name)s,
                  %(request_kind)s,
                  %(input_tokens)s,
                  %(output_tokens)s,
                  %(total_tokens)s,
                  %(estimated_cost_usd)s,
                  %(latency_ms)s,
                  %(success)s,
                  %(error_type)s,
                  %(error_message)s,
                  %(response_format)s,
                  %(usage_json)s,
                  %(request_hash)s
                )
                """,
                {
                    **usage.model_dump(mode="python"),
                    "raw_item_id": raw_item_id,
                    "event_id": event_id,
                    "source_id": source_id,
                    "usage_json": Jsonb(usage.usage_json),
                },
            )

    async def get_taxonomy_context(self) -> TaxonomyContext:
        async with self.cursor() as cur:
            await cur.execute(
                """
                select key, label_en, description
                from content_categories
                where enabled = true
                order by sort_order, key
                """
            )
            category_rows = await cur.fetchall()
            await cur.execute(
                """
                select key, label, tag_type, aliases
                from tags
                where enabled = true
                order by is_system desc, usage_count desc, key
                limit 250
                """
            )
            tag_rows = await cur.fetchall()

        return TaxonomyContext(
            categories=[
                CategoryOption(key=row["key"], label_en=row["label_en"], description=row["description"])
                for row in category_rows
            ],
            tags=[
                TagOption(
                    key=row["key"],
                    label=row["label"],
                    tag_type=row["tag_type"],
                    aliases=tuple(row["aliases"] or []),
                )
                for row in tag_rows
            ],
        )

    async def update_normalized_item(self, *, raw_item_id: Any, normalized: NormalizedItem) -> None:
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_items
                set text_clean = %(text_clean)s,
                    language = %(language)s,
                    updated_at = now()
                where id = %(raw_item_id)s
                """,
                {
                    "raw_item_id": raw_item_id,
                    "text_clean": normalized.text_clean,
                    "language": normalized.language,
                },
            )

    async def defer_for_model_budget(self, *, processing_id: Any) -> None:
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_item_processing
                set status = 'retry',
                    next_retry_at = now() + interval '1 hour',
                    locked_by = null,
                    locked_at = null,
                    error_message = 'model_call_budget_reached',
                    updated_at = now()
                where id = %(processing_id)s
                """,
                {"processing_id": processing_id},
            )

    async def complete_skipped(self, *, processing_id: Any, normalized: NormalizedItem) -> None:
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_item_processing
                set stage = 'completed',
                    status = 'skipped',
                    is_relevant = false,
                    relevance_score = %(relevance_score)s,
                    filter_reason = %(filter_reason)s,
                    normalized_json = %(normalized_json)s,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where id = %(processing_id)s
                """,
                {
                    "processing_id": processing_id,
                    "relevance_score": normalized.keyword_score,
                    "filter_reason": normalized.filter_reason,
                    "normalized_json": Jsonb(normalized.model_dump(mode="json")),
                },
            )

    async def complete_processed(
        self,
        *,
        task: ProcessingTask,
        normalized: NormalizedItem,
        model_response: ModelResponse,
        relevance_threshold_event: int,
    ) -> Any | None:
        event_id = None
        result = model_response.result

        async with self.cursor() as cur:
            if result.is_relevant and result.relevance_score >= relevance_threshold_event:
                event_id, inserted = await self._insert_event(cur, task, normalized, model_response)
                if inserted:
                    await self._insert_event_translations(cur, event_id, result)
                if result.claim_text:
                    await self._insert_event_claim(cur, event_id, task, model_response)

            await cur.execute(
                """
                update raw_item_processing
                set stage = 'completed',
                    status = 'completed',
                    is_relevant = %(is_relevant)s,
                    relevance_score = %(relevance_score)s,
                    filter_reason = %(filter_reason)s,
                    model_provider = %(model_provider)s,
                    model_name = %(model_name)s,
                    model_output_json = %(model_output_json)s,
                    normalized_json = %(normalized_json)s,
                    event_id = %(event_id)s,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where id = %(processing_id)s
                """,
                {
                    "processing_id": task.id,
                    "is_relevant": result.is_relevant,
                    "relevance_score": result.relevance_score,
                    "filter_reason": None if result.is_relevant else result.reason or "model_not_relevant",
                    "model_provider": model_response.provider,
                    "model_name": model_response.model,
                    "model_output_json": Jsonb(result.model_dump(mode="json")),
                    "normalized_json": Jsonb(normalized.model_dump(mode="json")),
                    "event_id": event_id,
                },
            )
        return event_id

    async def update_translation_result(
        self,
        *,
        raw_item_id: Any,
        response: AuxiliaryModelResponse,
        status: str,
        input_chars: int,
        taxonomy_context: TaxonomyContext,
    ) -> None:
        result = response.result
        content_category = normalize_category(result.content_category, taxonomy_context)
        topic_tags = normalize_topic_tags(result.topic_tags, taxonomy_context)
        mentioned_actors = normalize_actors(result.mentioned_actors)
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_items
                set content_category = %(content_category)s,
                    topic_tags = %(topic_tags)s,
                    mentioned_actors = %(mentioned_actors)s,
                    translation_status = %(translation_status)s,
                    translation_model_provider = %(translation_model_provider)s,
                    translation_model = %(translation_model)s,
                    translation_error = null,
                    translation_input_chars = %(translation_input_chars)s,
                    translation_updated_at = now(),
                    updated_at = now()
                where id = %(raw_item_id)s
                """,
                {
                    "raw_item_id": raw_item_id,
                    "content_category": content_category,
                    "topic_tags": Jsonb(topic_tags),
                    "mentioned_actors": Jsonb(mentioned_actors),
                    "translation_status": status,
                    "translation_model_provider": response.provider,
                    "translation_model": response.model,
                    "translation_input_chars": input_chars,
                },
            )
            for translation_row in raw_item_translation_rows_for_result(
                result,
                status=status,
                model_provider=response.provider,
                model=response.model,
                input_chars=input_chars,
                languages=self._translation_output_languages,
            ):
                await self._upsert_raw_item_translation(cur, raw_item_id=raw_item_id, **translation_row)
            await self._refresh_raw_item_translation_status(cur, raw_item_id=raw_item_id)
            await cur.execute("delete from raw_item_tags where raw_item_id = %(raw_item_id)s", {"raw_item_id": raw_item_id})
            tag_ids: list[Any] = []
            for tag in topic_tags:
                await cur.execute(
                    """
                    insert into tags (key, label, tag_type, aliases, usage_count, enabled, is_system)
                    values (%(key)s, %(label)s, 'topic', '[]'::jsonb, 0, true, false)
                    on conflict (key) do update
                    set updated_at = now()
                    returning id
                    """,
                    {"key": tag, "label": tag},
                )
                tag_row = await cur.fetchone()
                if tag_row:
                    tag_ids.append(tag_row["id"])
                    await cur.execute(
                        """
                        insert into raw_item_tags (raw_item_id, tag_id, source, confidence)
                        values (%(raw_item_id)s, %(tag_id)s, 'ai_layer_1', null)
                        on conflict (raw_item_id, tag_id) do nothing
                        """,
                        {"raw_item_id": raw_item_id, "tag_id": tag_row["id"]},
                    )
            if tag_ids:
                await cur.execute(
                    """
                    update tags t
                    set usage_count = counts.usage_count,
                        updated_at = now()
                    from (
                      select tag_id, count(*)::integer as usage_count
                      from raw_item_tags
                      where tag_id = any(%(tag_ids)s::uuid[])
                      group by tag_id
                    ) counts
                    where t.id = counts.tag_id
                    """,
                    {"tag_ids": tag_ids},
                )

    async def update_translation_skipped(self, *, raw_item_id: Any, reason: str) -> None:
        error = reason[:2000]
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_items
                set translation_status = 'skipped',
                    translation_error = %(translation_error)s,
                    translation_updated_at = now(),
                    updated_at = now()
                where id = %(raw_item_id)s
                """,
                {"raw_item_id": raw_item_id, "translation_error": error},
            )
            for language in self._translation_output_languages:
                await self._upsert_raw_item_translation(
                    cur,
                    raw_item_id=raw_item_id,
                    language=language,
                    summary=None,
                    full_translation=None,
                    status="skipped",
                    model_provider=None,
                    model=None,
                    error=error,
                    input_chars=None,
                )
            await self._refresh_raw_item_translation_status(cur, raw_item_id=raw_item_id)

    async def update_translation_failed(
        self,
        *,
        raw_item_id: Any,
        provider: str | None,
        model: str | None,
        error_message: str,
    ) -> None:
        error = error_message[:2000]
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_items
                set translation_status = 'failed',
                    translation_model_provider = %(translation_model_provider)s,
                    translation_model = %(translation_model)s,
                    translation_error = %(translation_error)s,
                    translation_updated_at = now(),
                    updated_at = now()
                where id = %(raw_item_id)s
                """,
                {
                    "raw_item_id": raw_item_id,
                    "translation_model_provider": provider,
                    "translation_model": model,
                    "translation_error": error,
                },
            )
            for language in self._translation_output_languages:
                await self._upsert_raw_item_translation(
                    cur,
                    raw_item_id=raw_item_id,
                    language=language,
                    summary=None,
                    full_translation=None,
                    status="failed",
                    model_provider=provider,
                    model=model,
                    error=error,
                    input_chars=None,
                )
            await self._refresh_raw_item_translation_status(cur, raw_item_id=raw_item_id)

    async def _upsert_raw_item_translation(
        self,
        cur: psycopg.AsyncCursor[Any],
        *,
        raw_item_id: Any,
        language: str,
        summary: str | None,
        full_translation: str | None,
        status: str,
        model_provider: str | None,
        model: str | None,
        error: str | None,
        input_chars: int | None,
    ) -> None:
        await cur.execute(
            """
            insert into raw_item_translations (
              raw_item_id,
              language,
              summary,
              full_translation,
              status,
              model_provider,
              model,
              error,
              input_chars,
              updated_at
            )
            values (
              %(raw_item_id)s,
              %(language)s,
              %(summary)s,
              %(full_translation)s,
              %(status)s,
              %(model_provider)s,
              %(model)s,
              %(error)s,
              %(input_chars)s,
              now()
            )
            on conflict (raw_item_id, language) do update
            set summary = excluded.summary,
                full_translation = excluded.full_translation,
                status = excluded.status,
                model_provider = excluded.model_provider,
                model = excluded.model,
                error = excluded.error,
                input_chars = excluded.input_chars,
                updated_at = now()
            """,
            {
                "raw_item_id": raw_item_id,
                "language": language,
                "summary": summary,
                "full_translation": full_translation,
                "status": status,
                "model_provider": model_provider,
                "model": model,
                "error": error,
                "input_chars": input_chars,
            },
        )

    async def _refresh_raw_item_translation_status(self, cur: psycopg.AsyncCursor[Any], *, raw_item_id: Any) -> None:
        await cur.execute(
            """
            with translation_stats as (
              select
                count(*)::integer as row_count,
                bool_and(status = 'pending') as all_pending,
                bool_and(status = 'skipped') as all_skipped,
                bool_and(status = 'failed') as all_failed,
                bool_and(status in ('completed', 'completed_truncated')) as all_completed,
                bool_or(status in ('completed', 'completed_truncated')) as has_completed,
                bool_or(status = 'completed_truncated') as has_truncated,
                bool_or(status = 'pending') as has_pending,
                bool_or(status = 'failed') as has_failed,
                max(updated_at) as latest_updated_at,
                string_agg(nullif(error, ''), '; ') filter (where status = 'failed') as failed_errors
              from raw_item_translations
              where raw_item_id = %(raw_item_id)s
            ),
            aggregate_status as (
              select
                case
                  when row_count = 0 then 'pending'
                  when all_pending then 'pending'
                  when all_skipped then 'skipped'
                  when all_failed then 'failed'
                  when all_completed then
                    case when has_truncated then 'completed_truncated' else 'completed' end
                  when has_completed then 'partial_completed'
                  when has_pending then 'pending'
                  when has_failed then 'failed'
                  else 'skipped'
                end as status,
                latest_updated_at,
                failed_errors
              from translation_stats
            )
            update raw_items
            set translation_status = aggregate_status.status,
                translation_error = case
                  when aggregate_status.status in ('failed', 'partial_completed')
                    then coalesce(aggregate_status.failed_errors, raw_items.translation_error)
                  when aggregate_status.status in ('completed', 'completed_truncated')
                    then null
                  else raw_items.translation_error
                end,
                translation_updated_at = coalesce(aggregate_status.latest_updated_at, raw_items.translation_updated_at, now()),
                updated_at = now()
            from aggregate_status
            where raw_items.id = %(raw_item_id)s
            """,
            {"raw_item_id": raw_item_id},
        )

    async def mark_failed(self, *, processing_id: Any, attempt_count: int, max_attempts: int, error_message: str) -> None:
        status = "failed" if attempt_count >= max_attempts else "retry"
        next_retry_at = None if status == "failed" else datetime.now(timezone.utc) + timedelta(seconds=30 * attempt_count)
        async with self.cursor() as cur:
            await cur.execute(
                """
                update raw_item_processing
                set status = %(status)s,
                    next_retry_at = %(next_retry_at)s,
                    locked_by = null,
                    locked_at = null,
                    error_message = %(error_message)s,
                    updated_at = now()
                where id = %(processing_id)s
                """,
                {
                    "processing_id": processing_id,
                    "status": status,
                    "next_retry_at": next_retry_at,
                    "error_message": error_message[:2000],
                },
            )

    async def _insert_event(
        self,
        cur: psycopg.AsyncCursor[Any],
        task: ProcessingTask,
        normalized: NormalizedItem,
        model_response: ModelResponse,
    ) -> tuple[Any, bool]:
        result = model_response.result
        event_dedupe_key = f"raw-item:{task.raw_item.dedupe_key}"
        severity = severity_for(result.relevance_score, task.source)
        await cur.execute(
            """
            insert into events (
              event_time,
              event_type,
              region,
              primary_actor,
              secondary_actor,
              source_id,
              source_group,
              severity,
              relevance_score,
              confidence,
              confirmation_state,
              title,
              market_relevance,
              xauusd_impact_channel,
              requires_confirmation,
              raw_item_ids,
              processing_id,
              model_provider,
              model_name,
              model_output_json,
              dedupe_key
            )
            values (
              %(event_time)s,
              %(event_type)s,
              %(region)s,
              %(primary_actor)s,
              %(secondary_actor)s,
              %(source_id)s,
              %(source_group)s,
              %(severity)s,
              %(relevance_score)s,
              %(confidence)s,
              %(confirmation_state)s,
              %(title)s,
              %(market_relevance)s,
              %(xauusd_impact_channel)s,
              %(requires_confirmation)s,
              %(raw_item_ids)s,
              %(processing_id)s,
              %(model_provider)s,
              %(model_name)s,
              %(model_output_json)s,
              %(dedupe_key)s
            )
            on conflict (dedupe_key) where dedupe_key is not null
            do update set updated_at = now()
            returning id, (xmax = 0) as inserted
            """,
            {
                "event_time": task.raw_item.published_at or task.raw_item.ingested_at,
                "event_type": result.event_type,
                "region": result.region,
                "primary_actor": result.primary_actor or (result.actors[0] if result.actors else None),
                "secondary_actor": result.secondary_actor,
                "source_id": task.source.id,
                "source_group": task.source.source_group,
                "severity": severity,
                "relevance_score": result.relevance_score,
                "confidence": result.confidence,
                "confirmation_state": "unconfirmed",
                "title": task.raw_item.title,
                "market_relevance": result.market_relevance,
                "xauusd_impact_channel": result.xauusd_impact_channel,
                "requires_confirmation": result.requires_confirmation,
                "raw_item_ids": [task.raw_item.id],
                "processing_id": task.id,
                "model_provider": model_response.provider,
                "model_name": model_response.model,
                "model_output_json": Jsonb(result.model_dump(mode="json")),
                "dedupe_key": event_dedupe_key,
            },
        )
        row = await cur.fetchone()
        return row["id"], bool(row["inserted"])

    async def _insert_event_translations(
        self,
        cur: psycopg.AsyncCursor[Any],
        event_id: Any,
        result: ClassificationResult,
    ) -> None:
        rows = [
            {"event_id": event_id, "language": item.language, "summary": item.summary}
            for item in result.summaries
            if item.summary.strip()
        ]
        if not rows:
            return
        await cur.executemany(
            """
            insert into event_translations (event_id, language, summary)
            values (%(event_id)s, %(language)s, %(summary)s)
            on conflict (event_id, language) do nothing
            """,
            rows,
        )

    async def _insert_event_claim(
        self,
        cur: psycopg.AsyncCursor[Any],
        event_id: Any,
        task: ProcessingTask,
        model_response: ModelResponse,
    ) -> None:
        result = model_response.result
        await cur.execute(
            """
            insert into event_claims (
              event_id,
              source_id,
              raw_item_id,
              claim_group_id,
              claim_text,
              claim_direction,
              stance,
              confidence,
              model_provider,
              model_name,
              model_output_json
            )
            values (
              %(event_id)s,
              %(source_id)s,
              %(raw_item_id)s,
              %(claim_group_id)s,
              %(claim_text)s,
              %(claim_direction)s,
              %(stance)s,
              %(confidence)s,
              %(model_provider)s,
              %(model_name)s,
              %(model_output_json)s
            )
            """,
            {
                "event_id": event_id,
                "source_id": task.source.id,
                "raw_item_id": task.raw_item.id,
                "claim_group_id": result.event_type,
                "claim_text": result.claim_text,
                "claim_direction": result.claim_direction,
                "stance": result.source_stance or task.source.stance,
                "confidence": result.confidence,
                "model_provider": model_response.provider,
                "model_name": model_response.model,
                "model_output_json": Jsonb(result.model_dump(mode="json")),
            },
        )
