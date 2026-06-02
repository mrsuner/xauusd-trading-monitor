from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import TelegramSource

logger = logging.getLogger(__name__)


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

    async def fetch_enabled_telegram_sources(self) -> list[TelegramSource]:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select
                  id,
                  name,
                  handle_or_url,
                  source_group,
                  official_level,
                  language,
                  priority,
                  source_config
                from sources
                where source_type = 'telegram'
                  and enabled = true
                order by
                  case priority
                    when 'P0' then 0
                    when 'P1' then 1
                    when 'P2' then 2
                    else 3
                  end,
                  name
                """
            )
            rows = await cur.fetchall()

        return [
            TelegramSource(
                id=row["id"],
                name=row["name"],
                handle_or_url=row["handle_or_url"],
                source_group=row["source_group"],
                official_level=row["official_level"],
                language=row["language"],
                priority=row["priority"],
                source_config=row["source_config"] or {},
            )
            for row in rows
        ]

    async def upsert_raw_item(self, values: dict[str, Any]) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                insert into raw_items (
                  source_id,
                  external_id,
                  published_at,
                  edited_at,
                  title,
                  text_raw,
                  text_clean,
                  language,
                  url,
                  media_type,
                  raw_json,
                  content_hash,
                  dedupe_key
                )
                values (
                  %(source_id)s,
                  %(external_id)s,
                  %(published_at)s,
                  %(edited_at)s,
                  %(title)s,
                  %(text_raw)s,
                  %(text_clean)s,
                  %(language)s,
                  %(url)s,
                  %(media_type)s,
                  %(raw_json)s,
                  %(content_hash)s,
                  %(dedupe_key)s
                )
                on conflict (dedupe_key) do update set
                  external_id = excluded.external_id,
                  published_at = excluded.published_at,
                  edited_at = excluded.edited_at,
                  title = excluded.title,
                  text_raw = excluded.text_raw,
                  text_clean = excluded.text_clean,
                  language = excluded.language,
                  url = excluded.url,
                  media_type = excluded.media_type,
                  raw_json = excluded.raw_json,
                  content_hash = excluded.content_hash,
                  updated_at = now()
                where raw_items.content_hash is distinct from excluded.content_hash
                   or raw_items.edited_at is distinct from excluded.edited_at
                   or raw_items.raw_json is distinct from excluded.raw_json
                """,
                {**values, "raw_json": Jsonb(values["raw_json"])},
            )
        await self.conn.commit()

    async def upsert_source_health(
        self,
        *,
        source_id: Any,
        service_name: str,
        status: str,
        last_seen_at: datetime | None = None,
        last_message_at: datetime | None = None,
        last_success_at: datetime | None = None,
        last_error_at: datetime | None = None,
        last_error_message: str | None = None,
        backfill_status: str | None = None,
        backfill_started_at: datetime | None = None,
        backfill_completed_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                insert into source_health (
                  source_id,
                  service_name,
                  status,
                  last_seen_at,
                  last_message_at,
                  last_success_at,
                  last_error_at,
                  last_error_message,
                  backfill_status,
                  backfill_started_at,
                  backfill_completed_at,
                  metadata
                )
                values (
                  %(source_id)s,
                  %(service_name)s,
                  %(status)s,
                  %(last_seen_at)s,
                  %(last_message_at)s,
                  %(last_success_at)s,
                  %(last_error_at)s,
                  %(last_error_message)s,
                  %(backfill_status)s,
                  %(backfill_started_at)s,
                  %(backfill_completed_at)s,
                  %(metadata)s
                )
                on conflict (source_id, service_name) do update set
                  status = excluded.status,
                  last_seen_at = coalesce(excluded.last_seen_at, source_health.last_seen_at),
                  last_message_at = coalesce(excluded.last_message_at, source_health.last_message_at),
                  last_success_at = coalesce(excluded.last_success_at, source_health.last_success_at),
                  last_error_at = coalesce(excluded.last_error_at, source_health.last_error_at),
                  last_error_message = coalesce(excluded.last_error_message, source_health.last_error_message),
                  backfill_status = coalesce(excluded.backfill_status, source_health.backfill_status),
                  backfill_started_at = coalesce(excluded.backfill_started_at, source_health.backfill_started_at),
                  backfill_completed_at = coalesce(excluded.backfill_completed_at, source_health.backfill_completed_at),
                  metadata = coalesce(excluded.metadata, source_health.metadata),
                  updated_at = now()
                """,
                {
                    "source_id": source_id,
                    "service_name": service_name,
                    "status": status,
                    "last_seen_at": last_seen_at,
                    "last_message_at": last_message_at,
                    "last_success_at": last_success_at,
                    "last_error_at": last_error_at,
                    "last_error_message": last_error_message,
                    "backfill_status": backfill_status,
                    "backfill_started_at": backfill_started_at,
                    "backfill_completed_at": backfill_completed_at,
                    "metadata": Jsonb(metadata or {}),
                },
            )
        await self.conn.commit()
