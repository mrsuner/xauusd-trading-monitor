from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import AlertChannelStats, AlertDecision, AlertDelivery, EventClaimContext, EventContext, RawItemContext, SourceContext
from .security import sanitize_provider_response, sanitize_text

logger = logging.getLogger(__name__)

RAW_ITEM_ZH_LANGUAGE = "zh-Hant"
RAW_ITEM_EN_LANGUAGE = "en"

RAW_ITEM_TRANSLATION_SUMMARY_SELECT_SQL = f"""
                  coalesce(tr_zh.summary, r.summary_zh) as raw_item_summary_zh,
                  coalesce(tr_en.summary, r.summary_en) as raw_item_summary_en,
"""

RAW_ITEM_TRANSLATION_JOIN_SQL = f"""
                left join raw_item_translations tr_zh
                  on tr_zh.raw_item_id = r.id
                 and tr_zh.language = '{RAW_ITEM_ZH_LANGUAGE}'
                left join raw_item_translations tr_en
                  on tr_en.raw_item_id = r.id
                 and tr_en.language = '{RAW_ITEM_EN_LANGUAGE}'
"""


def _event_context_query() -> str:
    return f"""
                select
                  e.*,
                  s.id as source_context_id,
                  s.name as source_name,
                  s.handle_or_url,
                  s.source_type,
                  s.source_group as source_context_group,
                  s.official_level,
                  s.priority as source_priority,
                  s.requires_confirmation as source_requires_confirmation,
                  s.telegram_alert_enabled,
                  s.pushover_alert_enabled,
                  s.telegram_min_severity,
                  s.pushover_min_severity,
                  s.alert_weight,
                  s.alert_rate_limit_per_hour,
                  s.alert_cooldown_minutes,
                  r.id as raw_item_id,
                  r.title as raw_item_title,
                  r.url as raw_item_url,
{RAW_ITEM_TRANSLATION_SUMMARY_SELECT_SQL}
                  r.text_clean as raw_item_text_clean,
                  r.text_raw as raw_item_text_raw
                from events e
                left join sources s on s.id = e.source_id
                left join lateral (
                  select raw.*
                  from raw_items raw
                  where raw.id = any(e.raw_item_ids)
                  order by array_position(e.raw_item_ids, raw.id)
                  limit 1
                ) r on true
{RAW_ITEM_TRANSLATION_JOIN_SQL}
                where e.id = %(event_id)s
                """


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

    async def event_ids_without_alerts(self, *, since: datetime, limit: int) -> list[Any]:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select e.id
                from events e
                where e.created_at >= %(since)s
                  and not exists (
                    select 1
                    from alerts a
                    where a.event_id = e.id
                  )
                order by e.created_at asc
                limit %(limit)s
                """,
                {"since": since, "limit": limit},
            )
            rows = await cur.fetchall()
        await self.conn.commit()
        return [row["id"] for row in rows]

    async def get_event_context(self, *, event_id: Any) -> EventContext | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                _event_context_query(),
                {"event_id": event_id},
            )
            row = await cur.fetchone()
            if not row:
                await self.conn.commit()
                return None

            await cur.execute(
                """
                select claim_text, claim_direction, stance, confidence
                from event_claims
                where event_id = %(event_id)s
                order by created_at asc
                limit 5
                """,
                {"event_id": event_id},
            )
            claim_rows = await cur.fetchall()

        await self.conn.commit()

        return EventContext(
            id=row["id"],
            event_time=row["event_time"],
            detected_at=row["detected_at"],
            created_at=row["created_at"],
            event_type=row["event_type"],
            severity=row["severity"],
            relevance_score=row["relevance_score"],
            confidence=row["confidence"],
            confirmation_state=row["confirmation_state"],
            title=row["title"],
            summary_zh=row["summary_zh"],
            summary_en=row["summary_en"],
            market_relevance=row["market_relevance"],
            xauusd_impact_channel=row["xauusd_impact_channel"] or [],
            requires_confirmation=row["requires_confirmation"],
            source_group=row["source_group"],
            source=SourceContext(
                id=row["source_context_id"],
                name=row["source_name"],
                handle_or_url=row["handle_or_url"],
                source_type=row["source_type"],
                source_group=row["source_context_group"],
                official_level=row["official_level"],
                priority=row["source_priority"],
                requires_confirmation=row["source_requires_confirmation"],
                telegram_alert_enabled=row["telegram_alert_enabled"] if row["telegram_alert_enabled"] is not None else True,
                pushover_alert_enabled=row["pushover_alert_enabled"] if row["pushover_alert_enabled"] is not None else False,
                telegram_min_severity=row["telegram_min_severity"] or "B",
                pushover_min_severity=row["pushover_min_severity"] or "S",
                alert_weight=row["alert_weight"] if row["alert_weight"] is not None else 50,
                alert_rate_limit_per_hour=row["alert_rate_limit_per_hour"],
                alert_cooldown_minutes=row["alert_cooldown_minutes"],
            ),
            raw_item=RawItemContext(
                id=row["raw_item_id"],
                title=row["raw_item_title"],
                url=row["raw_item_url"],
                summary_zh=row["raw_item_summary_zh"],
                summary_en=row["raw_item_summary_en"],
                text_clean=row["raw_item_text_clean"],
                text_raw=row["raw_item_text_raw"],
            ),
            claims=[EventClaimContext.model_validate(claim) for claim in claim_rows],
        )

    async def alert_channel_stats(self, *, source_id: Any, channel: str) -> AlertChannelStats:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select
                  count(*) filter (
                    where a.created_at >= now() - interval '1 hour'
                      and a.delivery_status in ('pending', 'sent', 'retry')
                  ) as sent_or_pending_1h,
                  max(a.created_at) filter (
                    where a.delivery_status in ('pending', 'sent', 'retry')
                  ) as last_alert_at
                from alerts a
                join events e on e.id = a.event_id
                where e.source_id = %(source_id)s
                  and a.channel = %(channel)s
                """,
                {"source_id": source_id, "channel": channel},
            )
            row = await cur.fetchone()
        await self.conn.commit()
        return AlertChannelStats(
            sent_or_pending_1h=int(row["sent_or_pending_1h"] or 0) if row else 0,
            last_alert_at=row["last_alert_at"] if row else None,
        )

    async def create_alert_decisions(self, decisions: list[AlertDecision]) -> None:
        if not decisions:
            return
        async with self.conn.cursor() as cur:
            for decision in decisions:
                await cur.execute(
                    """
                    insert into alerts (
                      event_id,
                      channel,
                      priority,
                      dedupe_key,
                      message,
                      delivery_status,
                      alert_score,
                      error_message
                    )
                    values (
                      %(event_id)s,
                      %(channel)s,
                      %(priority)s,
                      %(dedupe_key)s,
                      %(message)s,
                      %(delivery_status)s,
                      %(alert_score)s,
                      %(error_message)s
                    )
                    on conflict (dedupe_key) do nothing
                    """,
                    decision.model_dump(mode="python"),
                )
        await self.conn.commit()

    async def claim_next_alert(self, *, worker_id: str, lock_timeout_seconds: int = 300) -> AlertDelivery | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                with claimed as (
                  select id
                  from alerts
                  where delivery_status in ('pending', 'retry')
                    and (next_retry_at is null or next_retry_at <= now())
                    and (
                      locked_at is null
                      or locked_at < now() - (%(lock_timeout_seconds)s * interval '1 second')
                    )
                  order by created_at asc
                  for update skip locked
                  limit 1
                )
                update alerts a
                set locked_by = %(worker_id)s,
                    locked_at = now(),
                    attempt_count = a.attempt_count + 1,
                    error_message = null
                from claimed
                where a.id = claimed.id
                returning a.id, a.event_id, a.channel, a.priority, a.message, a.attempt_count
                """,
                {"worker_id": worker_id, "lock_timeout_seconds": lock_timeout_seconds},
            )
            row = await cur.fetchone()
        await self.conn.commit()
        if not row:
            return None
        return AlertDelivery.model_validate(row)

    async def mark_sent(self, *, alert_id: Any, provider_response: dict[str, Any]) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update alerts
                set delivery_status = 'sent',
                    sent_at = now(),
                    provider_response_json = %(provider_response_json)s,
                    error_message = null,
                    next_retry_at = null,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where id = %(alert_id)s
                """,
                {"alert_id": alert_id, "provider_response_json": Jsonb(sanitize_provider_response(provider_response))},
            )
        await self.conn.commit()

    async def mark_skipped(self, *, alert_id: Any, reason: str, provider_response: dict[str, Any] | None = None) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update alerts
                set delivery_status = 'skipped',
                    provider_response_json = %(provider_response_json)s,
                    error_message = %(error_message)s,
                    next_retry_at = null,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where id = %(alert_id)s
                """,
                {
                    "alert_id": alert_id,
                    "provider_response_json": Jsonb(sanitize_provider_response(provider_response or {})),
                    "error_message": sanitize_text(reason),
                },
            )
        await self.conn.commit()

    async def mark_failed_or_retry(
        self,
        *,
        alert: AlertDelivery,
        max_attempts: int,
        backoff_seconds: int,
        provider_response: dict[str, Any],
        error_message: str,
    ) -> None:
        status = "failed" if alert.attempt_count >= max_attempts else "retry"
        next_retry_at = None
        if status == "retry":
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                update alerts
                set delivery_status = %(delivery_status)s,
                    provider_response_json = %(provider_response_json)s,
                    error_message = %(error_message)s,
                    next_retry_at = %(next_retry_at)s,
                    locked_by = null,
                    locked_at = null,
                    updated_at = now()
                where id = %(alert_id)s
                """,
                {
                    "alert_id": alert.id,
                    "delivery_status": status,
                    "provider_response_json": Jsonb(sanitize_provider_response(provider_response)),
                    "error_message": sanitize_text(error_message),
                    "next_retry_at": next_retry_at,
                },
            )
        await self.conn.commit()
