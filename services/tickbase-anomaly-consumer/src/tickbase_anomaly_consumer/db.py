from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .mapping import MappedAnomaly
from .models import AnomalyEvent

logger = logging.getLogger(__name__)

# Must match the source seeded in migration 0016.
TICKBASE_SOURCE_URL = "https://api.thetickbase.com/v1/anomaly-events"
ANOMALY_EVENT_TYPE = "market_anomaly"


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return max(int(raw), 1)
    except ValueError:
        logger.warning("invalid integer environment value", extra={"env_name": name, "env_value": raw})
        return default


def _positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return max(float(raw), 0.1)
    except ValueError:
        logger.warning("invalid float environment value", extra={"env_name": name, "env_value": raw})
        return default


class Database:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.AsyncConnection[Any] | None = None
        self._source_id: Any | None = None

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
                    extra={"attempt": attempt, "max_attempts": max_attempts, "retry_in_seconds": delay_seconds},
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

    async def current_cursor(self) -> int:
        """Highest processed tickbase id; 0 when nothing ingested yet."""
        async with self.conn.cursor() as cur:
            await cur.execute("select coalesce(max(tickbase_id), 0) as cursor from tickbase_anomaly_ingest")
            row = await cur.fetchone()
        await self.conn.commit()
        return int(row["cursor"]) if row else 0

    async def _source_id_cached(self) -> Any:
        if self._source_id is not None:
            return self._source_id
        async with self.conn.cursor() as cur:
            await cur.execute(
                "select id from sources where source_type = 'api' and lower(handle_or_url) = lower(%s)",
                (TICKBASE_SOURCE_URL,),
            )
            row = await cur.fetchone()
        await self.conn.commit()
        if not row:
            raise RuntimeError("tickbase anomaly source missing; run migration 0016")
        self._source_id = row["id"]
        return self._source_id

    async def ingest(self, event: AnomalyEvent, mapped: MappedAnomaly) -> bool:
        """Atomically record one anomaly + its routing outputs.

        Returns True if this is the first time we see `event.id` (rows written),
        False if it was already ingested (idempotent no-op).
        """
        source_id = await self._source_id_cached()
        async with self.conn.cursor() as cur:
            # 1) synthetic event row (event_type discriminates anomaly vs news).
            #    Inserted first so the mirror's event_id FK is satisfiable; if the
            #    anomaly turns out to be a duplicate (tickbase_id conflict below),
            #    the whole transaction is rolled back and this event disappears.
            await cur.execute(
                """
                insert into events (
                    event_time, event_type, source_id, source_group, severity,
                    relevance_score, confirmation_state, title, summary_zh,
                    requires_confirmation, raw_item_ids
                ) values (
                    %(event_time)s, %(event_type)s, %(source_id)s, 'market_anomaly',
                    %(severity)s, %(relevance_score)s, 'confirmed', %(title)s,
                    %(summary_zh)s, false, '{}'::uuid[]
                )
                returning id
                """,
                {
                    "event_time": event.triggered_at,
                    "event_type": ANOMALY_EVENT_TYPE,
                    "source_id": source_id,
                    "severity": mapped.severity,
                    "relevance_score": mapped.relevance_score,
                    "title": mapped.title_zh,
                    "summary_zh": mapped.summary_zh,
                },
            )
            event_row = await cur.fetchone()
            event_uuid = event_row["id"]

            # 2) claim the anomaly via the tickbase_id PK; a conflict means we have
            #    already processed it, so roll back (discarding the event above).
            await cur.execute(
                """
                insert into tickbase_anomaly_ingest (
                    tickbase_id, event_id, rule_id, asset_class, base, quote,
                    direction, metric, triggered_at, raw
                ) values (
                    %(tickbase_id)s, %(event_id)s, %(rule_id)s, %(asset_class)s,
                    %(base)s, %(quote)s, %(direction)s, %(metric)s, %(triggered_at)s, %(raw)s
                )
                on conflict (tickbase_id) do nothing
                returning tickbase_id
                """,
                {
                    "tickbase_id": event.id,
                    "event_id": event_uuid,
                    "rule_id": event.rule_id,
                    "asset_class": event.asset_class,
                    "base": event.base,
                    "quote": event.quote,
                    "direction": event.direction,
                    "metric": event.metric,
                    "triggered_at": event.triggered_at,
                    "raw": Jsonb(event.model_dump(mode="json")),
                },
            )
            claimed = await cur.fetchone()
            if claimed is None:
                await self.conn.rollback()
                return False

            # 3) private telegram alert (all severities).
            await cur.execute(
                """
                insert into alerts (event_id, channel, priority, dedupe_key, message, delivery_status)
                values (%(event_id)s, 'telegram', %(priority)s, %(dedupe_key)s, %(message)s, 'pending')
                on conflict do nothing
                """,
                {
                    "event_id": event_uuid,
                    "priority": "high" if mapped.severity == "S" else "normal",
                    "dedupe_key": f"anomaly:{event.id}:telegram",
                    "message": mapped.alert_message,
                },
            )

            # 4) public Telegram channel (S/A only).
            if mapped.to_public:
                await cur.execute(
                    """
                    insert into public_outbox (
                        event_id, public_title_zh, public_summary_zh, severity,
                        relevance_score, confirmation_state, topic_tags,
                        approved_for_public, publish_status_telegram,
                        publish_status_web, publish_status_x
                    ) values (
                        %(event_id)s, %(title)s, %(summary)s, %(severity)s,
                        %(relevance_score)s, 'confirmed', %(topic_tags)s,
                        true, 'pending', 'skipped', 'skipped'
                    )
                    on conflict (event_id) do nothing
                    """,
                    {
                        "event_id": event_uuid,
                        "title": mapped.title_zh,
                        "summary": mapped.summary_zh,
                        "severity": mapped.severity,
                        "relevance_score": mapped.relevance_score,
                        "topic_tags": mapped.topic_tags,
                    },
                )

        await self.conn.commit()
        return True
