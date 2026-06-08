from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from .db import Database
from .public_outbox_translation_sql import (
    public_outbox_translation_json_lateral_sql,
    public_outbox_translation_search_lateral_sql,
)
from .query import QueryBuilder, clamp_page_size, offset_for
from .raw_item_translation_sql import (
    raw_item_translation_full_translation_select_sql,
    raw_item_translation_join_sql,
    raw_item_translation_json_lateral_sql,
    raw_item_translation_search_lateral_sql,
    raw_item_translation_summary_select_sql,
)


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

    async def source_exists(self, *, source_type: str, handle_or_url: str, exclude_source_id: UUID | None = None) -> bool:
        row = await self._db.fetch_one(
            """
            select 1
            from sources
            where source_type = %(source_type)s
              and lower(handle_or_url) = lower(%(handle_or_url)s)
              and (%(exclude_source_id)s::uuid is null or id <> %(exclude_source_id)s::uuid)
            limit 1
            """,
            {
                "source_type": source_type,
                "handle_or_url": handle_or_url,
                "exclude_source_id": exclude_source_id,
            },
        )
        return bool(row)

    async def create_source(self, values: dict[str, Any]) -> dict[str, Any]:
        params = dict(values)
        params["source_config"] = json.dumps(params.get("source_config") or {})
        return await self._db.fetch_one(
            """
            insert into sources (
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
              translation_policy,
              translation_priority,
              translation_max_chars,
              always_full_translate,
              telegram_alert_enabled,
              pushover_alert_enabled,
              telegram_min_severity,
              pushover_min_severity,
              alert_weight,
              alert_rate_limit_per_hour,
              alert_cooldown_minutes,
              enabled,
              source_config
            )
            values (
              %(name)s,
              %(handle_or_url)s,
              %(source_type)s,
              %(source_group)s,
              %(official_level)s,
              %(stance)s,
              %(language)s,
              %(priority)s,
              %(reliability_score)s,
              %(latency_score)s,
              %(requires_confirmation)s,
              %(translation_policy)s,
              %(translation_priority)s,
              %(translation_max_chars)s,
              %(always_full_translate)s,
              %(telegram_alert_enabled)s,
              %(pushover_alert_enabled)s,
              %(telegram_min_severity)s,
              %(pushover_min_severity)s,
              %(alert_weight)s,
              %(alert_rate_limit_per_hour)s,
              %(alert_cooldown_minutes)s,
              %(enabled)s,
              %(source_config)s::jsonb
            )
            returning *
            """,
            params,
        ) or {}

    async def update_source(self, source_id: UUID, values: dict[str, Any]) -> dict[str, Any] | None:
        if not values:
            return await self.get_source(source_id)

        allowed_columns = {
            "name",
            "handle_or_url",
            "source_type",
            "source_group",
            "official_level",
            "stance",
            "language",
            "priority",
            "reliability_score",
            "latency_score",
            "requires_confirmation",
            "translation_policy",
            "translation_priority",
            "translation_max_chars",
            "always_full_translate",
            "telegram_alert_enabled",
            "pushover_alert_enabled",
            "telegram_min_severity",
            "pushover_min_severity",
            "alert_weight",
            "alert_rate_limit_per_hour",
            "alert_cooldown_minutes",
            "enabled",
            "source_config",
        }
        params: dict[str, Any] = {"source_id": source_id}
        assignments: list[str] = []
        for key, value in values.items():
            if key not in allowed_columns:
                continue
            params[key] = json.dumps(value or {}) if key == "source_config" else value
            cast = "::jsonb" if key == "source_config" else ""
            assignments.append(f"{key} = %({key})s{cast}")

        if not assignments:
            return await self.get_source(source_id)

        if "enabled" in values:
            assignments.append("archived_at = case when %(enabled)s then null else archived_at end")
        assignments.append("updated_at = now()")
        return await self._db.fetch_one(
            f"""
            update sources
            set {", ".join(assignments)}
            where id = %(source_id)s
            returning *
            """,
            params,
        )

    async def set_source_enabled(self, source_id: UUID, *, enabled: bool) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            update sources
            set enabled = %(enabled)s,
                archived_at = case when %(enabled)s then null else archived_at end,
                updated_at = now()
            where id = %(source_id)s
            returning *
            """,
            {"source_id": source_id, "enabled": enabled},
        )

    async def archive_source(self, source_id: UUID) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            update sources
            set enabled = false,
                archived_at = coalesce(archived_at, now()),
                updated_at = now()
            where id = %(source_id)s
            returning *
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

    async def get_raw_item_filter_options(self) -> dict[str, Any]:
        row = await self._db.fetch_one(
            """
            select
              coalesce(
                jsonb_agg(distinct r.content_category)
                  filter (where r.content_category is not null and btrim(r.content_category) <> ''),
                '[]'::jsonb
              ) as content_categories,
              coalesce(
                (
                  select jsonb_agg(tag order by tag)
                  from (
                    select distinct btrim(value #>> '{}') as tag
                    from raw_items ri
                    cross join lateral jsonb_array_elements(ri.topic_tags) as tags(value)
                    where jsonb_typeof(ri.topic_tags) = 'array'
                      and btrim(value #>> '{}') <> ''
                    limit 500
                  ) distinct_tags
                ),
                '[]'::jsonb
              ) as topic_tags,
              coalesce(
                (
                  select jsonb_agg(actor order by actor)
                  from (
                    select distinct btrim(value #>> '{}') as actor
                    from raw_items ri
                    cross join lateral jsonb_array_elements(ri.mentioned_actors) as actors(value)
                    where jsonb_typeof(ri.mentioned_actors) = 'array'
                      and btrim(value #>> '{}') <> ''
                    limit 500
                  ) distinct_actors
                ),
                '[]'::jsonb
              ) as mentioned_actors
            from raw_items r
            """,
        )
        return row or {"content_categories": [], "topic_tags": [], "mentioned_actors": []}

    async def list_content_categories(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            select
              key,
              label_zh,
              label_en,
              description,
              sort_order,
              enabled,
              is_system
            from content_categories
            where enabled = true
            order by sort_order, key
            """
        )

    async def list_tags(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            select
              key,
              label,
              tag_type,
              aliases,
              usage_count,
              enabled,
              is_system
            from tags
            where enabled = true
            order by usage_count desc, is_system desc, key
            limit 500
            """
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
            f"""
            select
              r.id,
              r.source_id,
              r.published_at,
              r.ingested_at,
              r.title,
              r.text_raw,
              r.text_clean,
{raw_item_translation_summary_select_sql(indent="              ")}
{raw_item_translation_full_translation_select_sql(indent="              ")}
              coalesce(translations.items, '[]'::jsonb) as translations,
              r.translation_status,
              r.translation_model_provider,
              r.translation_model,
              r.translation_error,
              r.translation_input_chars,
              r.translation_updated_at,
              r.language,
              r.url,
              r.media_type,
              r.dedupe_key,
              s.name as source_name,
              s.source_type,
              s.source_group,
              s.official_level,
              s.priority
            from raw_items r
            join sources s on s.id = r.source_id
{raw_item_translation_join_sql(indent="            ")}
{raw_item_translation_json_lateral_sql(indent="            ")}
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

    async def ai_usage_stats(self, *, hours: int = 24) -> dict[str, Any]:
        params = {"hours": max(hours, 1)}
        totals = await self._db.fetch_one(
            """
            select
              count(*) as call_count,
              count(*) filter (where success = true) as success_count,
              count(*) filter (where success = false) as failure_count,
              coalesce(sum(input_tokens), 0) as input_tokens,
              coalesce(sum(output_tokens), 0) as output_tokens,
              coalesce(sum(total_tokens), 0) as total_tokens,
              coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd,
              round(avg(latency_ms))::integer as avg_latency_ms
            from ai_model_calls
            where created_at >= now() - (%(hours)s * interval '1 hour')
            """,
            params,
        )
        by_model = await self._db.fetch_all(
            """
            select
              provider,
              model_name,
              route_name,
              count(*) as call_count,
              count(*) filter (where success = false) as failure_count,
              coalesce(sum(input_tokens), 0) as input_tokens,
              coalesce(sum(output_tokens), 0) as output_tokens,
              coalesce(sum(total_tokens), 0) as total_tokens,
              coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd,
              round(avg(latency_ms))::integer as avg_latency_ms
            from ai_model_calls
            where created_at >= now() - (%(hours)s * interval '1 hour')
            group by provider, model_name, route_name
            order by estimated_cost_usd desc, total_tokens desc, call_count desc
            """,
            params,
        )
        by_layer = await self._db.fetch_all(
            """
            select
              ai_layer,
              count(*) as call_count,
              count(*) filter (where success = false) as failure_count,
              coalesce(sum(input_tokens), 0) as input_tokens,
              coalesce(sum(output_tokens), 0) as output_tokens,
              coalesce(sum(total_tokens), 0) as total_tokens,
              coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd,
              round(avg(latency_ms))::integer as avg_latency_ms
            from ai_model_calls
            where created_at >= now() - (%(hours)s * interval '1 hour')
            group by ai_layer
            order by estimated_cost_usd desc, total_tokens desc, call_count desc
            """,
            params,
        )
        by_source = await self._db.fetch_all(
            """
            select
              c.source_id,
              s.name as source_name,
              s.source_type,
              s.source_group,
              s.priority,
              count(*) as call_count,
              count(*) filter (where c.success = false) as failure_count,
              coalesce(sum(c.input_tokens), 0) as input_tokens,
              coalesce(sum(c.output_tokens), 0) as output_tokens,
              coalesce(sum(c.total_tokens), 0) as total_tokens,
              coalesce(sum(c.estimated_cost_usd), 0) as estimated_cost_usd,
              round(avg(c.latency_ms))::integer as avg_latency_ms
            from ai_model_calls c
            left join sources s on s.id = c.source_id
            where c.created_at >= now() - (%(hours)s * interval '1 hour')
            group by c.source_id, s.name, s.source_type, s.source_group, s.priority
            order by estimated_cost_usd desc, total_tokens desc, call_count desc
            limit 20
            """,
            params,
        )
        return {
            "hours": params["hours"],
            "totals": dict(totals or {}),
            "by_model": by_model,
            "by_layer": by_layer,
            "by_source": by_source,
        }


def build_sources_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select="""
        select
          s.id,
          s.name,
          s.handle_or_url,
          s.source_type,
          s.source_group,
          s.official_level,
          s.stance,
          s.language,
          s.priority,
          s.reliability_score,
          s.latency_score,
          s.requires_confirmation,
          s.translation_policy,
          s.translation_priority,
          s.translation_max_chars,
          s.always_full_translate,
          s.telegram_alert_enabled,
          s.pushover_alert_enabled,
          s.telegram_min_severity,
          s.pushover_min_severity,
          s.alert_weight,
          s.alert_rate_limit_per_hour,
          s.alert_cooldown_minutes,
          s.enabled,
          s.archived_at,
          s.source_config,
          s.created_at,
          s.updated_at,
          stats.last_raw_item_at,
          coalesce(stats.raw_items_24h, 0) as raw_items_24h,
          coalesce(event_stats.events_24h, 0) as events_24h
        from sources s
        left join lateral (
          select
            max(r.ingested_at) as last_raw_item_at,
            count(*) filter (where r.ingested_at >= now() - interval '24 hours') as raw_items_24h
          from raw_items r
          where r.source_id = s.id
        ) stats on true
        left join lateral (
          select count(*) as events_24h
          from events e
          where e.source_id = s.id
            and e.detected_at >= now() - interval '24 hours'
        ) event_stats on true
        """,
        base_count="select count(*) as total from sources s",
        order_by="order by s.source_group, s.priority, s.name",
    )
    builder.add_equal("s.source_type", "source_type", filters.get("source_type"))
    builder.add_equal("s.source_group", "source_group", filters.get("source_group"))
    builder.add_equal("s.priority", "priority", filters.get("priority"))
    builder.add_equal("s.enabled", "enabled", filters.get("enabled"))
    archived = filters.get("archived")
    if archived is not None:
        builder.where.append("s.archived_at is not null" if archived else "s.archived_at is null")
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
        base_select=f"""
        select
          r.id,
          r.source_id,
          r.external_id,
          r.published_at,
          r.ingested_at,
          r.edited_at,
          r.title,
          r.text_raw,
          r.text_clean,
{raw_item_translation_summary_select_sql()}
{raw_item_translation_full_translation_select_sql()}
          coalesce(translations.items, '[]'::jsonb) as translations,
          r.content_category,
          r.topic_tags,
          r.mentioned_actors,
          r.translation_status,
          r.translation_model_provider,
          r.translation_model,
          r.translation_error,
          r.translation_input_chars,
          r.translation_updated_at,
          r.language,
          r.url,
          r.media_type,
          r.content_hash,
          r.dedupe_key,
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
          p.model_provider as classification_model_provider,
          p.model_name as classification_model_name,
          p.updated_at as classification_updated_at,
          e.id as event_id,
          e.severity as event_severity,
          e.confidence as event_confidence,
          e.relevance_score as event_relevance_score,
          e.title as event_title,
          (e.id is not null) as has_event
        from raw_items r
        join sources s on s.id = r.source_id
        left join raw_item_processing p on p.raw_item_id = r.id
        left join events e on e.id = p.event_id
{raw_item_translation_join_sql()}
{raw_item_translation_json_lateral_sql()}
{raw_item_translation_search_lateral_sql()}
        """,
        base_count=f"""
        select count(*) as total
        from raw_items r
        join sources s on s.id = r.source_id
        left join raw_item_processing p on p.raw_item_id = r.id
        left join events e on e.id = p.event_id
{raw_item_translation_search_lateral_sql()}
        """,
        order_by="order by coalesce(r.published_at, r.ingested_at) desc",
    )
    builder.add_equal("r.source_id", "source_id", filters.get("source_id"))
    builder.add_equal("s.source_type", "source_type", filters.get("source_type"))
    builder.add_equal("s.source_group", "source_group", filters.get("source_group"))
    builder.add_equal("s.priority", "priority", filters.get("priority"))
    builder.add_equal("r.content_category", "content_category", filters.get("content_category"))
    builder.add_equal("p.status", "classification_status", filters.get("classification_status"))
    builder.add_equal("p.is_relevant", "is_relevant", filters.get("is_relevant"))
    builder.add_gte("p.relevance_score", "min_relevance_score", filters.get("min_relevance_score"))
    builder.add_gte("r.published_at", "published_from", filters.get("published_from"))
    builder.add_lte("r.published_at", "published_to", filters.get("published_to"))
    builder.add_gte("r.ingested_at", "ingested_from", filters.get("ingested_from"))
    builder.add_lte("r.ingested_at", "ingested_to", filters.get("ingested_to"))
    builder.add_search(
        (
            "r.title",
            "r.text_clean",
            "r.summary_zh",
            "r.summary_en",
            "r.full_translation_zh",
            "r.full_translation_en",
            "translation_search.search_text",
            "r.text_raw",
            "r.topic_tags::text",
            "r.mentioned_actors::text",
        ),
        "q",
        filters.get("q"),
    )
    if filters.get("topic_tag"):
        builder.where.append("r.topic_tags ? %(topic_tag)s")
        builder.params["topic_tag"] = filters["topic_tag"]
    if filters.get("actor"):
        builder.where.append("r.mentioned_actors ? %(actor)s")
        builder.params["actor"] = filters["actor"]
    if filters.get("has_event") is True:
        builder.where.append("e.id is not null")
    elif filters.get("has_event") is False:
        builder.where.append("e.id is null")
    if not filters.get("include_empty_text"):
        builder.where.append(
            """
            (
              nullif(btrim(regexp_replace(coalesce(r.text_clean, ''), '<[^>]+>', ' ', 'g')), '') is not null
              or nullif(btrim(regexp_replace(coalesce(r.text_raw, ''), '<[^>]+>', ' ', 'g')), '') is not null
              or (
                nullif(btrim(coalesce(r.title, '')), '') is not null
                and r.title !~* '^\\[no title\\]'
              )
            )
            """
        )
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


def build_processing_pipeline_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select=f"""
        select
          r.id as raw_item_id,
          r.source_id,
          r.title,
          r.language,
          r.url,
          r.published_at,
          r.ingested_at,
{raw_item_translation_summary_select_sql()}
          coalesce(translations.items, '[]'::jsonb) as translations,
          r.translation_status,
          r.translation_model_provider,
          r.translation_model,
          r.translation_error,
          r.translation_input_chars,
          r.translation_updated_at,
          coalesce(translation_usage.call_count, 0) as translation_call_count,
          coalesce(translation_usage.input_tokens, 0) as translation_input_tokens,
          coalesce(translation_usage.output_tokens, 0) as translation_output_tokens,
          coalesce(translation_usage.total_tokens, 0) as translation_total_tokens,
          coalesce(translation_usage.estimated_cost_usd, 0) as translation_estimated_cost_usd,
          s.name as source_name,
          s.source_type,
          s.source_group,
          s.priority,
          s.official_level,
          p.id as classification_processing_id,
          p.stage as classification_stage,
          p.status as classification_status,
          p.is_relevant,
          p.relevance_score,
          p.filter_reason,
          p.model_provider as classification_model_provider,
          p.model_name as classification_model_name,
          p.attempt_count as classification_attempt_count,
          p.locked_at as classification_locked_at,
          p.error_message as classification_error,
          p.updated_at as classification_updated_at,
          coalesce(classification_usage.call_count, 0) as classification_call_count,
          coalesce(classification_usage.input_tokens, 0) as classification_input_tokens,
          coalesce(classification_usage.output_tokens, 0) as classification_output_tokens,
          coalesce(classification_usage.total_tokens, 0) as classification_total_tokens,
          coalesce(classification_usage.estimated_cost_usd, 0) as classification_estimated_cost_usd,
          greatest(
            coalesce(r.translation_updated_at, '-infinity'::timestamptz),
            coalesce(p.updated_at, '-infinity'::timestamptz),
            r.ingested_at
          ) as pipeline_updated_at
        from raw_items r
        join sources s on s.id = r.source_id
        left join raw_item_processing p on p.raw_item_id = r.id
{raw_item_translation_join_sql()}
{raw_item_translation_json_lateral_sql()}
{raw_item_translation_search_lateral_sql()}
        left join lateral (
          select
            count(*) as call_count,
            coalesce(sum(input_tokens), 0) as input_tokens,
            coalesce(sum(output_tokens), 0) as output_tokens,
            coalesce(sum(total_tokens), 0) as total_tokens,
            coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd
          from ai_model_calls c
          where c.raw_item_id = r.id
            and c.ai_layer = 'translation_summary'
        ) translation_usage on true
        left join lateral (
          select
            count(*) as call_count,
            coalesce(sum(input_tokens), 0) as input_tokens,
            coalesce(sum(output_tokens), 0) as output_tokens,
            coalesce(sum(total_tokens), 0) as total_tokens,
            coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd
          from ai_model_calls c
          where c.raw_item_id = r.id
            and c.ai_layer = 'classification_reasoning'
        ) classification_usage on true
        """,
        base_count=f"""
        select count(*) as total
        from raw_items r
        join sources s on s.id = r.source_id
        left join raw_item_processing p on p.raw_item_id = r.id
{raw_item_translation_search_lateral_sql()}
        """,
        order_by="""
        order by greatest(
          coalesce(r.translation_updated_at, '-infinity'::timestamptz),
          coalesce(p.updated_at, '-infinity'::timestamptz),
          r.ingested_at
        ) desc
        """,
    )
    builder.add_equal("r.translation_status", "translation_status", filters.get("translation_status"))
    builder.add_equal("p.status", "classification_status", filters.get("classification_status"))
    builder.add_equal("p.stage", "classification_stage", filters.get("classification_stage"))
    builder.add_equal("p.is_relevant", "is_relevant", filters.get("is_relevant"))
    builder.add_gte("p.relevance_score", "min_relevance_score", filters.get("min_relevance_score"))
    builder.add_equal("p.model_provider", "classification_model_provider", filters.get("classification_model_provider"))
    builder.add_equal("r.source_id", "source_id", filters.get("source_id"))
    builder.add_equal("s.source_type", "source_type", filters.get("source_type"))
    builder.add_equal("s.source_group", "source_group", filters.get("source_group"))
    builder.add_equal("s.priority", "priority", filters.get("priority"))
    builder.add_search(
        ("r.title", "r.text_clean", "r.summary_zh", "r.summary_en", "translation_search.search_text", "r.text_raw", "s.name"),
        "q",
        filters.get("q"),
    )
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


def build_public_outbox_query(filters: dict[str, Any]) -> QueryBuilder:
    builder = QueryBuilder(
        base_select=f"""
        select
          p.id,
          p.event_id,
          p.public_title_zh,
          p.public_summary_zh,
          p.public_title_en,
          p.public_summary_en,
          coalesce(translations.items, '[]'::jsonb) as translations,
          p.public_source_links,
          p.severity,
          p.relevance_score,
          p.confirmation_state,
          p.topic_tags,
          p.approved_for_public,
          p.publish_status_web,
          p.publish_status_telegram,
          p.publish_status_x,
          p.retry_count_web,
          p.retry_count_telegram,
          p.retry_count_x,
          p.last_error_web,
          p.last_error_telegram,
          p.last_error_x,
          p.external_telegram_message_id,
          p.external_x_post_id,
          p.external_web_id,
          p.next_retry_telegram_at,
          p.next_retry_x_at,
          p.next_retry_web_at,
          p.generated_at,
          p.published_web_at,
          p.published_telegram_at,
          p.published_x_at,
          p.created_at,
          p.updated_at,
          e.title as event_title,
          e.summary_zh as event_summary_zh,
          e.event_type,
          e.detected_at as event_detected_at
        from public_outbox p
        join events e on e.id = p.event_id
{public_outbox_translation_json_lateral_sql(indent="        ")}
{public_outbox_translation_search_lateral_sql(indent="        ")}
        """,
        base_count=f"""
        select count(*) as total
        from public_outbox p
        join events e on e.id = p.event_id
{public_outbox_translation_search_lateral_sql(indent="        ")}
        """,
        order_by="order by p.generated_at desc, p.created_at desc",
    )
    builder.add_equal("p.approved_for_public", "approved_for_public", filters.get("approved_for_public"))
    builder.add_equal("p.severity", "severity", filters.get("severity"))
    builder.add_gte("p.created_at", "created_from", filters.get("created_from"))
    builder.add_lte("p.created_at", "created_to", filters.get("created_to"))
    builder.add_search(
        (
            "p.public_title_zh",
            "p.public_summary_zh",
            "p.public_title_en",
            "p.public_summary_en",
            "translation_search.search_text",
            "e.title",
            "e.summary_zh",
            "p.topic_tags::text",
        ),
        "q",
        filters.get("q"),
    )

    channel = filters.get("channel")
    publish_status = filters.get("publish_status")
    status_columns = {
        "web": "p.publish_status_web",
        "telegram": "p.publish_status_telegram",
        "telegram_channel": "p.publish_status_telegram",
        "x": "p.publish_status_x",
    }
    if channel and publish_status:
        status_column = status_columns.get(str(channel))
        if status_column:
            builder.add_equal(status_column, "publish_status", publish_status)
    elif publish_status:
        builder.where.append(
            """
            (
              p.publish_status_web = %(publish_status)s
              or p.publish_status_telegram = %(publish_status)s
              or p.publish_status_x = %(publish_status)s
            )
            """
        )
        builder.params["publish_status"] = publish_status

    return builder
