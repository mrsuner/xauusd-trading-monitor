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

    async def sent_count_last_hour(self) -> int:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select count(*) as count
                from public_outbox
                where publish_status_x = 'sent'
                  and published_x_at >= now() - interval '1 hour'
                """
            )
            row = await cur.fetchone()
        await self.conn.commit()
        return int(row["count"] or 0) if row else 0

    async def sent_count_last_day(self) -> int:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select count(*) as count
                from public_outbox
                where publish_status_x = 'sent'
                  and published_x_at >= now() - interval '24 hours'
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
                    and publish_status_x in ('pending', 'retry')
                    and retry_count_x < %(max_attempts)s
                    and (next_retry_x_at is null or next_retry_x_at <= now())
                    and (
                      locked_at_x is null
                      or locked_at_x < now() - (%(lock_timeout_seconds)s * interval '1 second')
                    )
                  order by generated_at asc
                  for update skip locked
                  limit 1
                )
                update public_outbox p
                set publish_status_x = 'sending',
                    locked_by_x = %(worker_id)s,
                    locked_at_x = now(),
                    retry_count_x = p.retry_count_x + 1,
                    last_error_x = null
                from claimed
                where p.id = claimed.id
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
                  p.retry_count_x,
                  p.generated_at
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

    async def mark_sent(self, *, item_id: Any, provider_response: dict[str, Any]) -> None:
        post_id = _x_post_id(provider_response)
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_outbox
                set publish_status_x = 'sent',
                    published_x_at = now(),
                    provider_response_x = %(provider_response)s,
                    external_x_post_id = %(post_id)s,
                    last_error_x = null,
                    next_retry_x_at = null,
                    locked_by_x = null,
                    locked_at_x = null,
                    updated_at = now()
                where id = %(item_id)s
                """,
                {
                    "item_id": item_id,
                    "provider_response": Jsonb(provider_response),
                    "post_id": post_id,
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
                set publish_status_x = 'skipped',
                    provider_response_x = %(provider_response)s,
                    last_error_x = %(reason)s,
                    next_retry_x_at = null,
                    locked_by_x = null,
                    locked_at_x = null,
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
        status = "failed" if item.retry_count_x >= max_attempts else "retry"
        next_retry_at = None
        if status == "retry":
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update public_outbox
                set publish_status_x = %(status)s,
                    provider_response_x = %(provider_response)s,
                    last_error_x = %(error_message)s,
                    next_retry_x_at = %(next_retry_at)s,
                    locked_by_x = null,
                    locked_at_x = null,
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


def _x_post_id(provider_response: dict[str, Any]) -> str | None:
    data = provider_response.get("data")
    if isinstance(data, dict) and data.get("id") is not None:
        return str(data["id"])
    return None
