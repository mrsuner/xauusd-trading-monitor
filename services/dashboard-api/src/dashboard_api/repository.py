from __future__ import annotations

from typing import Any
from uuid import UUID

from .db import Database
from .query import QueryBuilder, clamp_page_size, offset_for


class DashboardRepository:
    def __init__(self, db: Database, *, max_page_size: int) -> None:
        self._db = db
        self._max_page_size = max_page_size

    async def list_page(self, builder: QueryBuilder, *, page: int, page_size: int) -> dict[str, Any]:
        effective_page_size = clamp_page_size(page_size, self._max_page_size)
        params = dict(builder.params)
        params["limit"] = effective_page_size
        params["offset"] = offset_for(page, effective_page_size)

        items = await self._db.fetch_all(builder.list_sql(), params)
        count_row = await self._db.fetch_one(builder.count_sql(), builder.params)
        total = int(count_row["total"]) if count_row else 0

        return {
            "items": items,
            "page": max(page, 1),
            "page_size": effective_page_size,
            "total": total,
        }

    async def get_source(self, source_id: UUID) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            select *
            from sources
            where id = %(source_id)s
            """,
            {"source_id": source_id},
        )

    async def get_raw_item(self, raw_item_id: UUID) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            select
              r.*,
              s.name as source_name,
              s.handle_or_url,
              s.source_type,
              s.source_group,
              s.official_level,
              s.priority
            from raw_items r
            join sources s on s.id = r.source_id
            where r.id = %(raw_item_id)s
            """,
            {"raw_item_id": raw_item_id},
        )

    async def get_event(self, event_id: UUID) -> dict[str, Any] | None:
        event = await self._db.fetch_one(
            """
            select
              e.*,
              s.name as source_name,
              s.handle_or_url,
              s.official_level,
              s.priority
            from events e
            left join sources s on s.id = e.source_id
            where e.id = %(event_id)s
            """,
            {"event_id": event_id},
        )
        if not event:
            return None

        claims = await self._db.fetch_all(
            """
            select
              c.*,
              s.name as source_name,
              s.source_group,
              s.official_level
            from event_claims c
            left join sources s on s.id = c.source_id
            where c.event_id = %(event_id)s
            order by c.created_at
            """,
            {"event_id": event_id},
        )
        alerts = await self._db.fetch_all(
            """
            select *
            from alerts
            where event_id = %(event_id)s
            order by created_at desc
            """,
            {"event_id": event_id},
        )
        raw_items = await self._db.fetch_all(
            """
            select
              r.id,
              r.source_id,
              r.published_at,
              r.ingested_at,
              r.title,
              r.text_raw,
              r.text_clean,
              r.language,
              r.url,
              r.media_type,
              r.dedupe_key,
              s.name as source_name,
              s.source_group
            from raw_items r
            join sources s on s.id = r.source_id
            where r.id = any(%(raw_item_ids)s::uuid[])
            order by coalesce(r.published_at, r.ingested_at) desc
            """,
            {"raw_item_ids": event["raw_item_ids"] or []},
        )

        return {
            **event,
            "claims": claims,
            "alerts": alerts,
            "raw_items": raw_items,
        }

    async def overview_stats(self) -> dict[str, Any]:
        row = await self._db.fetch_one(
            """
            select
              (select count(*) from sources where enabled = true) as active_sources,
              (select count(*) from raw_items where ingested_at >= now() - interval '1 hour') as raw_items_1h,
              (select count(*) from raw_items where ingested_at >= now() - interval '24 hours') as raw_items_24h,
              (select count(*) from events where detected_at >= now() - interval '1 hour') as events_1h,
              (select count(*) from events where detected_at >= now() - interval '24 hours') as events_24h,
              (
                select count(*)
                from events
                where severity in ('S', 'A')
                  and detected_at >= now() - interval '24 hours'
              ) as high_impact_events_24h,
              (select count(*) from raw_item_processing where status = 'failed') as failed_processing,
              (select count(*) from alerts where delivery_status = 'failed') as failed_alerts
            """
        )
        return dict(row or {})


def build_sources_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          id,
          name,
          handle_or_url,
          source_type,
          source_group,
          official_level,
          stance,
          language,
          priority,
          reliability_score,
          latency_score,
          requires_confirmation,
          enabled,
          source_config,
          created_at,
          updated_at
        from sources
        """,
        base_count="select count(*) as total from sources",
        order_by="order by source_group, priority, name",
    )
    builder.add_equal("source_type", "source_type", filters.get("source_type"))
    builder.add_equal("source_group", "source_group", filters.get("source_group"))
    builder.add_equal("priority", "priority", filters.get("priority"))
    builder.add_equal("enabled", "enabled", filters.get("enabled"))
    return builder


def build_source_health_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          h.*,
          s.name as source_name,
          s.handle_or_url,
          s.source_type,
          s.source_group,
          s.priority,
          s.enabled
        from source_health h
        join sources s on s.id = h.source_id
        """,
        base_count="select count(*) as total from source_health h join sources s on s.id = h.source_id",
        order_by="order by h.updated_at desc",
    )
    builder.add_equal("h.service_name", "service_name", filters.get("service_name"))
    builder.add_equal("h.status", "status", filters.get("status"))
    builder.add_equal("s.source_type", "source_type", filters.get("source_type"))
    return builder


def build_raw_items_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          r.id,
          r.source_id,
          r.external_id,
          r.published_at,
          r.ingested_at,
          r.edited_at,
          r.title,
          r.text_clean,
          r.language,
          r.url,
          r.media_type,
          r.content_hash,
          r.dedupe_key,
          s.name as source_name,
          s.source_type,
          s.source_group,
          s.official_level,
          s.priority
        from raw_items r
        join sources s on s.id = r.source_id
        """,
        base_count="select count(*) as total from raw_items r join sources s on s.id = r.source_id",
        order_by="order by coalesce(r.published_at, r.ingested_at) desc",
    )
    builder.add_equal("r.source_id", "source_id", filters.get("source_id"))
    builder.add_equal("s.source_group", "source_group", filters.get("source_group"))
    builder.add_gte("r.published_at", "published_from", filters.get("published_from"))
    builder.add_lte("r.published_at", "published_to", filters.get("published_to"))
    builder.add_gte("r.ingested_at", "ingested_from", filters.get("ingested_from"))
    builder.add_lte("r.ingested_at", "ingested_to", filters.get("ingested_to"))
    builder.add_search(("r.title", "r.text_clean", "r.text_raw"), "q", filters.get("q"))
    return builder


def build_processing_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          p.*,
          r.title,
          r.published_at,
          r.ingested_at,
          s.name as source_name,
          s.source_group,
          s.priority
        from raw_item_processing p
        join raw_items r on r.id = p.raw_item_id
        join sources s on s.id = r.source_id
        """,
        base_count="""
        select count(*) as total
        from raw_item_processing p
        join raw_items r on r.id = p.raw_item_id
        join sources s on s.id = r.source_id
        """,
        order_by="order by p.updated_at desc",
    )
    builder.add_equal("p.status", "status", filters.get("status"))
    builder.add_equal("p.stage", "stage", filters.get("stage"))
    builder.add_equal("p.is_relevant", "is_relevant", filters.get("is_relevant"))
    builder.add_gte("p.relevance_score", "min_relevance_score", filters.get("min_relevance_score"))
    builder.add_equal("p.model_provider", "model_provider", filters.get("model_provider"))
    return builder


def build_events_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          e.*,
          s.name as source_name,
          s.handle_or_url,
          s.official_level,
          s.priority
        from events e
        left join sources s on s.id = e.source_id
        """,
        base_count="select count(*) as total from events e left join sources s on s.id = e.source_id",
        order_by="order by e.detected_at desc",
    )
    builder.add_equal("e.severity", "severity", filters.get("severity"))
    builder.add_equal("e.event_type", "event_type", filters.get("event_type"))
    builder.add_equal("e.source_group", "source_group", filters.get("source_group"))
    builder.add_gte("e.relevance_score", "min_relevance_score", filters.get("min_relevance_score"))
    builder.add_gte("e.created_at", "created_from", filters.get("created_from"))
    builder.add_lte("e.created_at", "created_to", filters.get("created_to"))
    return builder


def build_alerts_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          a.*,
          e.title as event_title,
          e.severity as event_severity,
          e.event_type
        from alerts a
        join events e on e.id = a.event_id
        """,
        base_count="select count(*) as total from alerts a join events e on e.id = a.event_id",
        order_by="order by a.created_at desc",
    )
    builder.add_equal("a.channel", "channel", filters.get("channel"))
    builder.add_equal("a.delivery_status", "delivery_status", filters.get("delivery_status"))
    builder.add_equal("a.priority", "priority", filters.get("priority"))
    builder.add_gte("a.created_at", "created_from", filters.get("created_from"))
    builder.add_lte("a.created_at", "created_to", filters.get("created_to"))
    return builder
