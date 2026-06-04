from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import (
    AlertChannelStats,
    AlertDecision,
    EventClaimContext,
    EventContext,
    PublicOutboxDraft,
    RawItemContext,
    RouteDecision,
    SourceContext,
)

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

    async def unrouted_event_ids(self, *, since: datetime, limit: int) -> list[Any]:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                select e.id
                from events e
                where e.created_at >= %(since)s
                  and (
                    select count(*)
                    from event_route_decisions d
                    where d.event_id = e.id
                      and d.route_key in (
                        'private.telegram',
                        'private.pushover',
                        'public.telegram_channel',
                        'public.website',
                        'public.x'
                      )
                  ) < 5
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
                """
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
                  r.summary_zh as raw_item_summary_zh,
                  r.summary_en as raw_item_summary_en,
                  r.text_clean as raw_item_text_clean,
                  r.text_raw as raw_item_text_raw,
                  coalesce(
                    array_agg(distinct t.key) filter (where t.key is not null),
                    '{}'::text[]
                  ) as topic_tags
                from events e
                left join sources s on s.id = e.source_id
                left join lateral (
                  select raw.*
                  from raw_items raw
                  where raw.id = any(e.raw_item_ids)
                  order by array_position(e.raw_item_ids, raw.id)
                  limit 1
                ) r on true
                left join raw_item_tags rit on rit.raw_item_id = r.id
                left join tags t on t.id = rit.tag_id
                where e.id = %(event_id)s
                group by
                  e.id,
                  s.id,
                  r.id,
                  r.title,
                  r.url,
                  r.summary_zh,
                  r.summary_en,
                  r.text_clean,
                  r.text_raw
                """,
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
                limit 10
                """,
                {"event_id": event_id},
            )
            claim_rows = await cur.fetchall()

        await self.conn.commit()

        event = EventContext(
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
            topic_tags=list(row["topic_tags"] or []),
        )
        return event

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

    async def create_alert(self, alert: AlertDecision) -> Any | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                insert into alerts (
                  event_id,
                  channel,
                  priority,
                  dedupe_key,
                  message,
                  delivery_status,
                  alert_score
                )
                values (
                  %(event_id)s,
                  %(channel)s,
                  %(priority)s,
                  %(dedupe_key)s,
                  %(message)s,
                  'pending',
                  %(alert_score)s
                )
                on conflict (dedupe_key) do update
                set message = excluded.message,
                    priority = excluded.priority,
                    alert_score = excluded.alert_score,
                    delivery_status = case
                      when alerts.delivery_status = 'skipped' then 'pending'
                      else alerts.delivery_status
                    end,
                    error_message = null,
                    updated_at = now()
                returning id
                """,
                alert.model_dump(mode="python"),
            )
            row = await cur.fetchone()
        await self.conn.commit()
        return row["id"] if row else None

    async def upsert_public_outbox(self, draft: PublicOutboxDraft) -> Any | None:
        payload = draft.model_dump(mode="python")
        payload["public_source_links"] = Jsonb(payload["public_source_links"])
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                insert into public_outbox (
                  event_id,
                  public_title_zh,
                  public_summary_zh,
                  public_title_en,
                  public_summary_en,
                  public_source_links,
                  severity,
                  relevance_score,
                  confirmation_state,
                  topic_tags,
                  approved_for_public,
                  publish_status_web,
                  publish_status_telegram,
                  publish_status_x
                )
                values (
                  %(event_id)s,
                  %(public_title_zh)s,
                  %(public_summary_zh)s,
                  %(public_title_en)s,
                  %(public_summary_en)s,
                  %(public_source_links)s,
                  %(severity)s,
                  %(relevance_score)s,
                  %(confirmation_state)s,
                  %(topic_tags)s,
                  %(approved_for_public)s,
                  %(publish_status_web)s,
                  %(publish_status_telegram)s,
                  %(publish_status_x)s
                )
                on conflict (event_id) do update
                set public_title_zh = coalesce(excluded.public_title_zh, public_outbox.public_title_zh),
                    public_summary_zh = coalesce(excluded.public_summary_zh, public_outbox.public_summary_zh),
                    public_title_en = coalesce(excluded.public_title_en, public_outbox.public_title_en),
                    public_summary_en = coalesce(excluded.public_summary_en, public_outbox.public_summary_en),
                    public_source_links = case
                      when jsonb_array_length(excluded.public_source_links) > 0
                      then excluded.public_source_links
                      else public_outbox.public_source_links
                    end,
                    severity = excluded.severity,
                    relevance_score = excluded.relevance_score,
                    confirmation_state = excluded.confirmation_state,
                    topic_tags = excluded.topic_tags,
                    approved_for_public = public_outbox.approved_for_public or excluded.approved_for_public,
                    publish_status_web = case
                      when excluded.publish_status_web = 'pending'
                           and public_outbox.publish_status_web in ('skipped', 'failed')
                      then 'pending'
                      else public_outbox.publish_status_web
                    end,
                    publish_status_telegram = case
                      when excluded.publish_status_telegram = 'pending'
                           and public_outbox.publish_status_telegram in ('skipped', 'failed')
                      then 'pending'
                      else public_outbox.publish_status_telegram
                    end,
                    publish_status_x = case
                      when excluded.publish_status_x = 'pending'
                           and public_outbox.publish_status_x in ('skipped', 'failed')
                      then 'pending'
                      else public_outbox.publish_status_x
                    end,
                    updated_at = now()
                returning id
                """,
                payload,
            )
            row = await cur.fetchone()
        await self.conn.commit()
        return row["id"] if row else None

    async def upsert_route_decision(self, decision: RouteDecision) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                insert into event_route_decisions (
                  event_id,
                  route_key,
                  decision_status,
                  route_score,
                  reason,
                  payload_table,
                  payload_id
                )
                values (
                  %(event_id)s,
                  %(route_key)s,
                  %(decision_status)s,
                  %(route_score)s,
                  %(reason)s,
                  %(payload_table)s,
                  %(payload_id)s
                )
                on conflict (event_id, route_key) do update
                set decision_status = excluded.decision_status,
                    route_score = excluded.route_score,
                    reason = excluded.reason,
                    payload_table = excluded.payload_table,
                    payload_id = excluded.payload_id,
                    updated_at = now()
                """,
                decision.model_dump(mode="python"),
            )
        await self.conn.commit()
