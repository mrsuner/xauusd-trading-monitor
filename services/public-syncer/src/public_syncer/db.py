from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import PublicOutboxItem, PublicRawItem
from .security_scrub import sanitize_provider_response, sanitize_text

logger = logging.getLogger(__name__)


def public_outbox_translations_select_sql(*, outbox_alias: str = "p", translation_alias: str = "pot", indent: str = "                  ") -> str:
    return f"""coalesce(
{indent}  (
{indent}    select jsonb_agg(
{indent}      jsonb_build_object(
{indent}        'language', {translation_alias}.language,
{indent}        'title', {translation_alias}.title,
{indent}        'summary', {translation_alias}.summary,
{indent}        'status', {translation_alias}.status
{indent}      )
{indent}      order by {translation_alias}.language
{indent}    )
{indent}    from public_outbox_translations {translation_alias}
{indent}    where {translation_alias}.public_outbox_id = {outbox_alias}.id
{indent}  ),
{indent}  '[]'::jsonb
{indent})"""


def raw_item_translations_select_sql(*, raw_alias: str = "r", translation_alias: str = "rit", indent: str = "                  ") -> str:
    return f"""coalesce(
{indent}  (
{indent}    select jsonb_agg(
{indent}      jsonb_build_object(
{indent}        'language', {translation_alias}.language,
{indent}        'summary', {translation_alias}.summary,
{indent}        'full_translation', {translation_alias}.full_translation,
{indent}        'status', {translation_alias}.status,
{indent}        'input_chars', {translation_alias}.input_chars
{indent}      )
{indent}      order by {translation_alias}.language
{indent}    )
{indent}    from raw_item_translations {translation_alias}
{indent}    where {translation_alias}.raw_item_id = {raw_alias}.id
{indent}      and {translation_alias}.status in ('completed', 'completed_truncated')
{indent}  ),
{indent}  '[]'::jsonb
{indent})"""


def raw_item_upstream_event_ids_sql(*, raw_alias: str = "r", processing_alias: str = "p", indent: str = "                  ") -> str:
    return f"""coalesce(
{indent}  (
{indent}    select array_agg(distinct event_id)
{indent}    from (
{indent}      select {processing_alias}.event_id
{indent}      where {processing_alias}.event_id is not null
{indent}      union
{indent}      select e.id
{indent}      from events e
{indent}      where {raw_alias}.id = any(e.raw_item_ids)
{indent}    ) event_refs
{indent}    where event_id is not null
{indent}  ),
{indent}  '{{}}'::uuid[]
{indent})"""


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
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.AsyncConnection[Any] | None = None

    async def connect(self) -> None:
        max_attempts = _positive_int_env("DB_CONNECT_MAX_ATTEMPTS", 10)
        delay_seconds = _positive_float_env("DB_CONNECT_INITIAL_BACKOFF_SECONDS", 1.0)
        max_delay_seconds = _positive_float_env("DB_CONNECT_MAX_BACKOFF_SECONDS", 30.0)

        for attempt in range(1, max_attempts + 1):
            try:
                self._conn = await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row)
                return
            except Exception:
                if attempt >= max_attempts:
                    logger.exception(
                        "database connection failed after retries",
                        extra={"attempt": attempt, "max_attempts": max_attempts},
                    )
                    raise
                logger.warning(
                    "database connection failed; retrying",
                    extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_in_seconds": delay_seconds,
                    },
                    exc_info=True,
                )
                await asyncio.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, max_delay_seconds)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> psycopg.AsyncConnection[Any]:
        if not self._conn:
            raise RuntimeError("database is not connected")
        return self._conn

    async def sent_count_last_minute(self) -> int:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select count(*) as count
                from public_outbox
                where publish_status_web = 'sent'
                  and published_web_at >= now() - interval '1 minute'
                """
            )
            row = await cur.fetchone()
        await self.conn.commit()
        return int(row["count"] or 0) if row else 0

    async def raw_item_sent_count_last_minute(self) -> int:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select count(*) as count
                from public_raw_item_sync_state
                where publish_status = 'sent'
                  and synced_at >= now() - interval '1 minute'
                """
            )
            row = await cur.fetchone()
        await self.conn.commit()
        return int(row["count"] or 0) if row else 0

    async def refresh_raw_item_sync_candidates(
        self,
        *,
        limit: int,
        min_relevance_score: int,
        backfill_enabled: bool,
    ) -> int:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                with candidates as (
                  select
                    r.id as raw_item_id,
                    greatest(
                      r.updated_at,
                      r.ingested_at,
                      coalesce(r.translation_updated_at, '-infinity'::timestamptz),
                      coalesce(p.updated_at, '-infinity'::timestamptz),
                      coalesce(translation_state.updated_at, '-infinity'::timestamptz)
                    ) as source_updated_at
                  from raw_items r
                  join sources s on s.id = r.source_id
                  left join raw_item_processing p on p.raw_item_id = r.id
                  left join lateral (
                    select max(updated_at) as updated_at
                    from raw_item_translations rit
                    where rit.raw_item_id = r.id
                      and rit.status in ('completed', 'completed_truncated')
                  ) translation_state on true
                  left join public_raw_item_sync_state state on state.raw_item_id = r.id
                  where coalesce(s.archived, false) = false
                    and (
                      nullif(btrim(coalesce(r.text_clean, '')), '') is not null
                      or (
                        nullif(btrim(coalesce(r.title, '')), '') is not null
                        and r.title !~* '^\\[no title\\]'
                      )
                    )
                    and (
                      r.translation_status in ('completed', 'completed_truncated', 'skipped')
                      or exists (
                        select 1
                        from raw_item_translations rit
                        where rit.raw_item_id = r.id
                          and rit.status in ('completed', 'completed_truncated')
                      )
                    )
                    and (
                      p.is_relevant is true
                      or p.relevance_score >= %(min_relevance_score)s
                    )
                    and (
                      %(backfill_enabled)s
                      or state.raw_item_id is not null
                      or r.ingested_at >= now() - interval '24 hours'
                      or r.translation_updated_at >= now() - interval '24 hours'
                      or p.updated_at >= now() - interval '24 hours'
                    )
                  order by coalesce(r.published_at, r.ingested_at) asc
                  limit %(limit)s
                )
                insert into public_raw_item_sync_state (
                  raw_item_id,
                  source_updated_at
                )
                select
                  raw_item_id,
                  source_updated_at
                from candidates
                on conflict (raw_item_id) do update
                set source_updated_at = excluded.source_updated_at,
                    publish_status = case
                      when public_raw_item_sync_state.source_updated_at is distinct from excluded.source_updated_at
                       and public_raw_item_sync_state.publish_status in ('sent', 'skipped', 'failed')
                      then 'pending'
                      else public_raw_item_sync_state.publish_status
                    end,
                    retry_count = case
                      when public_raw_item_sync_state.source_updated_at is distinct from excluded.source_updated_at
                       and public_raw_item_sync_state.publish_status in ('sent', 'skipped', 'failed')
                      then 0
                      else public_raw_item_sync_state.retry_count
                    end,
                    last_error = case
                      when public_raw_item_sync_state.source_updated_at is distinct from excluded.source_updated_at
                      then null
                      else public_raw_item_sync_state.last_error
                    end,
                    updated_at = now()
                where public_raw_item_sync_state.source_updated_at is distinct from excluded.source_updated_at
                returning raw_item_id
                """,
                {
                    "limit": limit,
                    "min_relevance_score": min_relevance_score,
                    "backfill_enabled": backfill_enabled,
                },
            )
            rows = await cur.fetchall()
        await self.conn.commit()
        return len(rows)

    async def claim_next_item(
        self,
        *,
        worker_id: str,
        lock_timeout_seconds: int,
        max_attempts: int,
    ) -> PublicOutboxItem | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                f"""
                with claimed as (
                  select id
                  from public_outbox
                  where approved_for_public = true
                    and publish_status_web in ('pending', 'retry')
                    and retry_count_web < %(max_attempts)s
                    and (next_retry_web_at is null or next_retry_web_at <= now())
                    and (
                      locked_at_web is null
                      or locked_at_web < now() - (%(lock_timeout_seconds)s * interval '1 second')
                    )
                  order by generated_at asc
                  for update skip locked
                  limit 1
                )
                update public_outbox p
                set publish_status_web = 'sending',
                    locked_by_web = %(worker_id)s,
                    locked_at_web = now(),
                    retry_count_web = p.retry_count_web + 1,
                    last_error_web = null
                from claimed, events e
                where p.id = claimed.id
                  and e.id = p.event_id
                returning
                  p.id,
                  p.event_id,
                  p.public_title_zh,
                  p.public_summary_zh,
                  p.public_title_en,
                  p.public_summary_en,
                  {public_outbox_translations_select_sql()} as translations,
                  p.public_source_links,
                  p.severity,
                  p.relevance_score,
                  p.confirmation_state,
                  p.topic_tags,
                  p.retry_count_web,
                  p.generated_at,
                  e.event_time
                """,
                {
                    "worker_id": worker_id,
                    "lock_timeout_seconds": lock_timeout_seconds,
                    "max_attempts": max_attempts,
                },
            )
            row = await cur.fetchone()
        await self.conn.commit()
        if not row:
            return None
        return PublicOutboxItem.model_validate(row)

    async def claim_next_raw_item(
        self,
        *,
        worker_id: str,
        lock_timeout_seconds: int,
        max_attempts: int,
    ) -> PublicRawItem | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                f"""
                with claimed as (
                  select raw_item_id
                  from public_raw_item_sync_state
                  where publish_status in ('pending', 'retry')
                    and retry_count < %(max_attempts)s
                    and (next_retry_at is null or next_retry_at <= now())
                    and (
                      locked_at is null
                      or locked_at < now() - (%(lock_timeout_seconds)s * interval '1 second')
                    )
                  order by source_updated_at asc
                  for update skip locked
                  limit 1
                )
                update public_raw_item_sync_state state
                set publish_status = 'sending',
                    locked_by = %(worker_id)s,
                    locked_at = now(),
                    retry_count = state.retry_count + 1,
                    last_error = null
                from claimed, raw_items r
                join sources s on s.id = r.source_id
                left join raw_item_processing p on p.raw_item_id = r.id
                where state.raw_item_id = claimed.raw_item_id
                  and r.id = claimed.raw_item_id
                returning
                  r.id,
                  r.source_id,
                  state.source_updated_at,
                  state.retry_count,
                  r.external_id,
                  r.published_at,
                  r.ingested_at,
                  r.edited_at,
                  r.title,
                  r.text_clean,
                  r.language,
                  r.url,
                  r.media_type,
                  r.summary_zh,
                  r.summary_en,
                  r.full_translation_zh,
                  r.full_translation_en,
                  {raw_item_translations_select_sql()} as translations,
                  r.translation_status,
                  r.translation_input_chars,
                  r.content_category,
                  coalesce(r.topic_tags, '[]'::jsonb) as topic_tags,
                  coalesce(r.mentioned_actors, '[]'::jsonb) as mentioned_actors,
                  s.name as source_name,
                  s.source_type,
                  s.source_group,
                  s.official_level,
                  s.priority,
                  p.stage as classification_stage,
                  p.status as classification_status,
                  p.is_relevant,
                  p.relevance_score,
                  p.filter_reason,
                  {raw_item_upstream_event_ids_sql()} as upstream_event_ids
                """,
                {
                    "worker_id": worker_id,
                    "lock_timeout_seconds": lock_timeout_seconds,
                    "max_attempts": max_attempts,
                },
            )
            row = await cur.fetchone()
        await self.conn.commit()
        if not row:
            return None
        return PublicRawItem.model_validate(row)

    async def mark_sent(self, *, item_id: Any, provider_response: dict[str, Any], external_web_id: str | None) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_outbox
                set publish_status_web = 'sent',
                    published_web_at = now(),
                    provider_response_web = %(provider_response)s,
                    external_web_id = %(external_web_id)s,
                    last_error_web = null,
                    next_retry_web_at = null,
                    locked_by_web = null,
                    locked_at_web = null,
                    updated_at = now()
                where id = %(item_id)s
                """,
                {
                    "item_id": item_id,
                    "provider_response": Jsonb(sanitize_provider_response(provider_response)),
                    "external_web_id": external_web_id,
                },
            )
        await self.conn.commit()

    async def mark_raw_item_sent(
        self,
        *,
        raw_item_id: Any,
        provider_response: dict[str, Any],
        external_web_id: str | None,
        payload_hash: str | None,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_raw_item_sync_state
                set publish_status = 'sent',
                    synced_at = now(),
                    provider_response = %(provider_response)s,
                    external_web_id = %(external_web_id)s,
                    last_payload_hash = %(payload_hash)s,
                    last_error = null,
                    next_retry_at = null,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where raw_item_id = %(raw_item_id)s
                """,
                {
                    "raw_item_id": raw_item_id,
                    "provider_response": Jsonb(sanitize_provider_response(provider_response)),
                    "external_web_id": external_web_id,
                    "payload_hash": payload_hash,
                },
            )
        await self.conn.commit()

    async def mark_skipped(
        self,
        *,
        item_id: Any,
        reason: str,
        provider_response: dict[str, Any] | None = None,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_outbox
                set publish_status_web = 'skipped',
                    provider_response_web = %(provider_response)s,
                    last_error_web = %(reason)s,
                    next_retry_web_at = null,
                    locked_by_web = null,
                    locked_at_web = null,
                    updated_at = now()
                where id = %(item_id)s
                """,
                {
                    "item_id": item_id,
                    "provider_response": Jsonb(sanitize_provider_response(provider_response or {})),
                    "reason": sanitize_text(reason),
                },
            )
        await self.conn.commit()

    async def mark_raw_item_skipped(
        self,
        *,
        raw_item_id: Any,
        reason: str,
        provider_response: dict[str, Any] | None = None,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_raw_item_sync_state
                set publish_status = 'skipped',
                    provider_response = %(provider_response)s,
                    last_error = %(reason)s,
                    next_retry_at = null,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where raw_item_id = %(raw_item_id)s
                """,
                {
                    "raw_item_id": raw_item_id,
                    "provider_response": Jsonb(sanitize_provider_response(provider_response or {})),
                    "reason": sanitize_text(reason),
                },
            )
        await self.conn.commit()

    async def mark_failed_or_retry(
        self,
        *,
        item: PublicOutboxItem,
        max_attempts: int,
        backoff_seconds: int,
        provider_response: dict[str, Any],
        error_message: str,
    ) -> None:
        status = "failed" if item.retry_count_web >= max_attempts else "retry"
        next_retry_at = None
        if status == "retry":
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_outbox
                set publish_status_web = %(status)s,
                    provider_response_web = %(provider_response)s,
                    last_error_web = %(error_message)s,
                    next_retry_web_at = %(next_retry_at)s,
                    locked_by_web = null,
                    locked_at_web = null,
                    updated_at = now()
                where id = %(item_id)s
                """,
                {
                    "item_id": item.id,
                    "status": status,
                    "provider_response": Jsonb(sanitize_provider_response(provider_response)),
                    "error_message": sanitize_text(error_message),
                    "next_retry_at": next_retry_at,
                },
            )
        await self.conn.commit()

    async def mark_raw_item_failed_or_retry(
        self,
        *,
        item: PublicRawItem,
        max_attempts: int,
        backoff_seconds: int,
        provider_response: dict[str, Any],
        error_message: str,
    ) -> None:
        status = "failed" if item.retry_count >= max_attempts else "retry"
        next_retry_at = None
        if status == "retry":
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_raw_item_sync_state
                set publish_status = %(status)s,
                    provider_response = %(provider_response)s,
                    last_error = %(error_message)s,
                    next_retry_at = %(next_retry_at)s,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where raw_item_id = %(raw_item_id)s
                """,
                {
                    "raw_item_id": item.id,
                    "status": status,
                    "provider_response": Jsonb(sanitize_provider_response(provider_response)),
                    "error_message": sanitize_text(error_message),
                    "next_retry_at": next_retry_at,
                },
            )
        await self.conn.commit()
