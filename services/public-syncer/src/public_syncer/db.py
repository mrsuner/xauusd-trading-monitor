from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import PublicOutboxItem


class Database:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.AsyncConnection[Any] | None = None

    async def connect(self) -> None:
        self._conn = await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row)

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

    async def claim_next_item(
        self,
        *,
        worker_id: str,
        lock_timeout_seconds: int,
        max_attempts: int,
    ) -> PublicOutboxItem | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
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
                    "provider_response": Jsonb(provider_response),
                    "external_web_id": external_web_id,
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
                    "provider_response": Jsonb(provider_response or {}),
                    "reason": reason[:2000],
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
                    "provider_response": Jsonb(provider_response),
                    "error_message": error_message[:2000],
                    "next_retry_at": next_retry_at,
                },
            )
        await self.conn.commit()
