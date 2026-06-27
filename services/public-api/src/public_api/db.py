from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import LANGUAGE_CODE_RE, PublicEventIngestRequest, PublicRawItemIngestRequest
from .security import body_sha256

logger = logging.getLogger(__name__)

DEFAULT_PUBLIC_LANGUAGE = "en"
PUBLIC_LANGUAGE_ZH_HANT = "zh-Hant"
PUBLIC_LANGUAGE_EN = "en"


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

    async def ping(self) -> bool:
        try:
            async with self.conn.cursor() as cur:
                await cur.execute("select 1")
                await cur.fetchone()
            await self.conn.commit()
            return True
        except Exception:
            await self.conn.rollback()
            return False


class PublicRepository:
    def __init__(
        self,
        db: Database,
        *,
        max_page_size: int,
        default_language: str = DEFAULT_PUBLIC_LANGUAGE,
        language_priority: tuple[str, ...] = (PUBLIC_LANGUAGE_EN, PUBLIC_LANGUAGE_ZH_HANT),
    ) -> None:
        self.db = db
        self.max_page_size = max_page_size
        self.default_language = default_language
        self.language_priority = language_priority

    async def nonce_seen(self, *, key_id: str | None, nonce: str | None) -> bool:
        if not key_id or not nonce:
            return False
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                select 1
                from public_ingest_requests
                where key_id = %(key_id)s and nonce = %(nonce)s
                limit 1
                """,
                {"key_id": key_id, "nonce": nonce},
            )
            row = await cur.fetchone()
        await self.db.conn.commit()
        return row is not None

    async def ingest_event(
        self,
        payload: PublicEventIngestRequest,
        *,
        raw_body: bytes,
        key_id: str | None,
        nonce: str | None,
    ) -> dict[str, Any]:
        translation_rows = public_event_translation_rows(payload)
        params = {
            "upstream_event_id": payload.upstream_event_id,
            "idempotency_key": payload.idempotency_key,
            "schema_version": payload.schema_version,
            "event_time": payload.event_time,
            "generated_at": payload.generated_at,
            "severity": payload.severity,
            "relevance_score": payload.relevance_score,
            "confirmation_state": payload.confirmation_state,
            "public_source_links": Jsonb([link.model_dump(mode="json") for link in payload.public_source_links]),
            "topic_tags": payload.topic_tags,
            "content_category": payload.content_category,
            "mentioned_actors": payload.mentioned_actors,
            "route_metadata": Jsonb(payload.route_metadata),
        }
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                insert into public_events (
                  upstream_event_id,
                  idempotency_key,
                  schema_version,
                  event_time,
                  generated_at,
                  severity,
                  relevance_score,
                  confirmation_state,
                  public_source_links,
                  topic_tags,
                  content_category,
                  mentioned_actors,
                  route_metadata
                )
                values (
                  %(upstream_event_id)s,
                  %(idempotency_key)s,
                  %(schema_version)s,
                  %(event_time)s,
                  %(generated_at)s,
                  %(severity)s,
                  %(relevance_score)s,
                  %(confirmation_state)s,
                  %(public_source_links)s,
                  %(topic_tags)s,
                  %(content_category)s,
                  %(mentioned_actors)s,
                  %(route_metadata)s
                )
                on conflict (idempotency_key) do update
                set upstream_event_id = excluded.upstream_event_id,
                    schema_version = excluded.schema_version,
                    event_time = excluded.event_time,
                    generated_at = excluded.generated_at,
                    severity = excluded.severity,
                    relevance_score = excluded.relevance_score,
                    confirmation_state = excluded.confirmation_state,
                    public_source_links = excluded.public_source_links,
                    topic_tags = excluded.topic_tags,
                    content_category = excluded.content_category,
                    mentioned_actors = excluded.mentioned_actors,
                    route_metadata = excluded.route_metadata,
                    updated_at = now()
                returning id, (xmax = 0) as inserted
                """,
                params,
            )
            row = await cur.fetchone()
            status = "accepted" if row and row["inserted"] else "duplicate"
            if row and translation_rows:
                for translation in translation_rows:
                    translation["public_event_id"] = row["id"]
                await cur.executemany(
                    """
                    insert into public_events_translations (
                      public_event_id,
                      language,
                      title,
                      summary
                    )
                    values (
                      %(public_event_id)s,
                      %(language)s,
                      %(title)s,
                      %(summary)s
                    )
                    on conflict (public_event_id, language) do update
                    set title = excluded.title,
                        summary = excluded.summary,
                        updated_at = now()
                    """,
                    translation_rows,
                )
            await cur.execute(
                """
                insert into public_ingest_requests (
                  ingest_kind,
                  idempotency_key,
                  upstream_event_id,
                  public_event_id,
                  request_hash,
                  key_id,
                  nonce,
                  status
                )
                values (
                  'event',
                  %(idempotency_key)s,
                  %(upstream_event_id)s,
                  %(public_event_id)s,
                  %(request_hash)s,
                  %(key_id)s,
                  %(nonce)s,
                  %(status)s
                )
                """,
                {
                    "idempotency_key": payload.idempotency_key,
                    "upstream_event_id": payload.upstream_event_id,
                    "public_event_id": row["id"],
                    "request_hash": body_sha256(raw_body),
                    "key_id": key_id,
                    "nonce": nonce,
                    "status": status,
                },
            )
        await self.db.conn.commit()
        return {"status": status, "public_event_id": row["id"], "idempotency_key": payload.idempotency_key}

    async def ingest_raw_item(
        self,
        payload: PublicRawItemIngestRequest,
        *,
        raw_body: bytes,
        key_id: str | None,
        nonce: str | None,
    ) -> dict[str, Any]:
        translation_rows = public_raw_item_translation_rows(payload)
        params = {
            "upstream_raw_item_id": payload.upstream_raw_item_id,
            "idempotency_key": payload.idempotency_key,
            "schema_version": payload.schema_version,
            "source_name": payload.source.name,
            "source_type": payload.source.source_type,
            "source_group": payload.source.source_group,
            "official_level": payload.source.official_level,
            "priority": payload.source.priority,
            "source_url": str(payload.source_url) if payload.source_url else None,
            "published_at": payload.published_at,
            "ingested_at": payload.ingested_at,
            "edited_at": payload.edited_at,
            "title": payload.title,
            "original_content": payload.original_content,
            "language": payload.language,
            "media_type": payload.media_type,
            "content_category": payload.content_category,
            "topic_tags": payload.topic_tags,
            "mentioned_actors": payload.mentioned_actors,
            "upstream_event_ids": payload.upstream_event_ids,
            "is_relevant": payload.classification.is_relevant,
            "relevance_score": payload.classification.relevance_score,
            "filter_reason": payload.classification.filter_reason,
            "classification_stage": payload.classification.stage,
            "classification_status": payload.classification.status,
            "is_truncated": bool(
                payload.scrub_metadata.get("original_content_truncated")
                or any(translation.is_truncated for translation in payload.translations)
            ),
            "source_text_chars": _optional_int(payload.scrub_metadata.get("source_text_chars")),
            "translation_chars": _max_translation_chars(payload),
            "scrub_metadata": Jsonb(payload.scrub_metadata),
        }
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                insert into public_raw_items (
                  upstream_raw_item_id,
                  idempotency_key,
                  schema_version,
                  source_name,
                  source_type,
                  source_group,
                  official_level,
                  priority,
                  source_url,
                  published_at,
                  ingested_at,
                  edited_at,
                  title,
                  original_content,
                  language,
                  media_type,
                  content_category,
                  topic_tags,
                  mentioned_actors,
                  upstream_event_ids,
                  is_relevant,
                  relevance_score,
                  filter_reason,
                  classification_stage,
                  classification_status,
                  is_truncated,
                  source_text_chars,
                  translation_chars,
                  scrub_metadata
                )
                values (
                  %(upstream_raw_item_id)s,
                  %(idempotency_key)s,
                  %(schema_version)s,
                  %(source_name)s,
                  %(source_type)s,
                  %(source_group)s,
                  %(official_level)s,
                  %(priority)s,
                  %(source_url)s,
                  %(published_at)s,
                  %(ingested_at)s,
                  %(edited_at)s,
                  %(title)s,
                  %(original_content)s,
                  %(language)s,
                  %(media_type)s,
                  %(content_category)s,
                  %(topic_tags)s,
                  %(mentioned_actors)s,
                  %(upstream_event_ids)s,
                  %(is_relevant)s,
                  %(relevance_score)s,
                  %(filter_reason)s,
                  %(classification_stage)s,
                  %(classification_status)s,
                  %(is_truncated)s,
                  %(source_text_chars)s,
                  %(translation_chars)s,
                  %(scrub_metadata)s
                )
                on conflict (idempotency_key) do update
                set upstream_raw_item_id = excluded.upstream_raw_item_id,
                    schema_version = excluded.schema_version,
                    source_name = excluded.source_name,
                    source_type = excluded.source_type,
                    source_group = excluded.source_group,
                    official_level = excluded.official_level,
                    priority = excluded.priority,
                    source_url = excluded.source_url,
                    published_at = excluded.published_at,
                    ingested_at = excluded.ingested_at,
                    edited_at = excluded.edited_at,
                    title = excluded.title,
                    original_content = excluded.original_content,
                    language = excluded.language,
                    media_type = excluded.media_type,
                    content_category = excluded.content_category,
                    topic_tags = excluded.topic_tags,
                    mentioned_actors = excluded.mentioned_actors,
                    upstream_event_ids = excluded.upstream_event_ids,
                    is_relevant = excluded.is_relevant,
                    relevance_score = excluded.relevance_score,
                    filter_reason = excluded.filter_reason,
                    classification_stage = excluded.classification_stage,
                    classification_status = excluded.classification_status,
                    is_truncated = excluded.is_truncated,
                    source_text_chars = excluded.source_text_chars,
                    translation_chars = excluded.translation_chars,
                    scrub_metadata = excluded.scrub_metadata,
                    updated_at = now()
                returning id, (xmax = 0) as inserted
                """,
                params,
            )
            row = await cur.fetchone()
            status = "accepted" if row and row["inserted"] else "duplicate"
            if row and translation_rows:
                for translation in translation_rows:
                    translation["public_raw_item_id"] = row["id"]
                await cur.executemany(
                    """
                    insert into public_raw_item_translations (
                      public_raw_item_id,
                      language,
                      summary,
                      full_translation,
                      status,
                      is_truncated,
                      source_chars,
                      translation_chars
                    )
                    values (
                      %(public_raw_item_id)s,
                      %(language)s,
                      %(summary)s,
                      %(full_translation)s,
                      %(status)s,
                      %(is_truncated)s,
                      %(source_chars)s,
                      %(translation_chars)s
                    )
                    on conflict (public_raw_item_id, language) do update
                    set summary = excluded.summary,
                        full_translation = excluded.full_translation,
                        status = excluded.status,
                        is_truncated = excluded.is_truncated,
                        source_chars = excluded.source_chars,
                        translation_chars = excluded.translation_chars,
                        updated_at = now()
                    """,
                    translation_rows,
                )
            await cur.execute(
                """
                insert into public_ingest_requests (
                  ingest_kind,
                  idempotency_key,
                  public_raw_item_id,
                  request_hash,
                  key_id,
                  nonce,
                  status
                )
                values (
                  'raw_item',
                  %(idempotency_key)s,
                  %(public_raw_item_id)s,
                  %(request_hash)s,
                  %(key_id)s,
                  %(nonce)s,
                  %(status)s
                )
                """,
                {
                    "idempotency_key": payload.idempotency_key,
                    "public_raw_item_id": row["id"],
                    "request_hash": body_sha256(raw_body),
                    "key_id": key_id,
                    "nonce": nonce,
                    "status": status,
                },
            )
        await self.db.conn.commit()
        return {"status": status, "public_raw_item_id": row["id"], "idempotency_key": payload.idempotency_key}

    async def record_rejected_ingest(
        self,
        *,
        raw_body: bytes,
        key_id: str | None,
        nonce: str | None,
        error_message: str,
        idempotency_key: str | None = None,
        ingest_kind: str = "event",
    ) -> None:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                insert into public_ingest_requests (
                  ingest_kind,
                  idempotency_key,
                  request_hash,
                  key_id,
                  nonce,
                  status,
                  error_message
                )
                values (
                  %(ingest_kind)s,
                  %(idempotency_key)s,
                  %(request_hash)s,
                  %(key_id)s,
                  %(nonce)s,
                  'rejected',
                  %(error_message)s
                )
                on conflict do nothing
                """,
                {
                    "ingest_kind": ingest_kind,
                    "idempotency_key": idempotency_key,
                    "request_hash": body_sha256(raw_body),
                    "key_id": key_id,
                    "nonce": nonce,
                    "error_message": error_message[:2000],
                },
            )
        await self.db.conn.commit()

    async def list_raw_items(
        self,
        *,
        page: int,
        page_size: int,
        lang: str | None = None,
        source_type: str | None = None,
        source_group: str | None = None,
        tag: str | None = None,
        category: str | None = None,
        q: str | None = None,
        event_id: str | None = None,
        min_relevance_score: int | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> dict[str, Any]:
        limit = min(page_size, self.max_page_size)
        offset = (page - 1) * limit
        where, params = _build_raw_item_filters(
            source_type=source_type,
            source_group=source_group,
            tag=tag,
            category=category,
            q=q,
            event_id=event_id,
            min_relevance_score=min_relevance_score,
            from_time=from_time,
            to_time=to_time,
        )
        async with self.db.conn.cursor() as cur:
            await cur.execute(f"select count(*) as total from public_raw_items {where}", params)
            total_row = await cur.fetchone()
            await cur.execute(
                f"""
                select
                  id,
                  upstream_raw_item_id,
                  idempotency_key,
                  schema_version,
                  source_name,
                  source_type,
                  source_group,
                  official_level,
                  priority,
                  source_url,
                  published_at,
                  ingested_at,
                  edited_at,
                  received_at,
                  title,
                  original_content,
                  language as source_language,
                  media_type,
                  content_category,
                  topic_tags,
                  mentioned_actors,
                  upstream_event_ids,
                  is_relevant,
                  relevance_score,
                  filter_reason,
                  classification_stage,
                  classification_status,
                  is_truncated,
                  source_text_chars,
                  translation_chars,
                  scrub_metadata,
{public_raw_item_translations_select_sql()} as translations
                from public_raw_items
                {where}
                order by coalesce(published_at, ingested_at, received_at) desc, received_at desc
                limit %(limit)s offset %(offset)s
                """,
                {**params, "limit": limit, "offset": offset},
            )
            rows = await cur.fetchall()
        await self.db.conn.commit()
        return {
            "items": [
                shape_public_raw_item(
                    row,
                    lang=lang,
                    default_language=self.default_language,
                    language_priority=self.language_priority,
                )
                for row in rows
            ],
            "page": page,
            "page_size": limit,
            "total": int(total_row["total"]),
        }

    async def get_raw_item(self, public_raw_item_id: UUID, *, lang: str | None = None) -> dict[str, Any] | None:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                f"""
                select
                  id,
                  upstream_raw_item_id,
                  idempotency_key,
                  schema_version,
                  source_name,
                  source_type,
                  source_group,
                  official_level,
                  priority,
                  source_url,
                  published_at,
                  ingested_at,
                  edited_at,
                  received_at,
                  title,
                  original_content,
                  language as source_language,
                  media_type,
                  content_category,
                  topic_tags,
                  mentioned_actors,
                  upstream_event_ids,
                  is_relevant,
                  relevance_score,
                  filter_reason,
                  classification_stage,
                  classification_status,
                  is_truncated,
                  source_text_chars,
                  translation_chars,
                  scrub_metadata,
{public_raw_item_translations_select_sql()} as translations
                from public_raw_items
                where id = %(id)s and is_visible = true
                """,
                {"id": public_raw_item_id},
            )
            row = await cur.fetchone()
        await self.db.conn.commit()
        return (
            shape_public_raw_item(
                row,
                lang=lang,
                default_language=self.default_language,
                language_priority=self.language_priority,
            )
            if row
            else None
        )

    async def list_events(
        self,
        *,
        page: int,
        page_size: int,
        lang: str | None = None,
        severity: str | None = None,
        confirmation_state: str | None = None,
        tag: str | None = None,
        category: str | None = None,
        q: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> dict[str, Any]:
        limit = min(page_size, self.max_page_size)
        offset = (page - 1) * limit
        where, params = _build_filters(
            severity=severity,
            confirmation_state=confirmation_state,
            tag=tag,
            category=category,
            q=q,
            from_time=from_time,
            to_time=to_time,
        )
        async with self.db.conn.cursor() as cur:
            await cur.execute(f"select count(*) as total from public_events {where}", params)
            total_row = await cur.fetchone()
            await cur.execute(
                f"""
                select
                  id,
                  upstream_event_id,
                  idempotency_key,
                  schema_version,
                  event_time,
                  generated_at,
                  received_at,
                  severity,
                  relevance_score,
                  confirmation_state,
                  public_source_links,
                  topic_tags,
                  content_category,
                  mentioned_actors,
                  route_metadata,
{public_event_translations_select_sql()} as translations
                from public_events
                {where}
                order by coalesce(event_time, generated_at, received_at) desc, received_at desc
                limit %(limit)s offset %(offset)s
                """,
                {**params, "limit": limit, "offset": offset},
            )
            rows = await cur.fetchall()
        await self.db.conn.commit()
        return {
            "items": [
                shape_public_event(
                    row,
                    lang=lang,
                    default_language=self.default_language,
                    language_priority=self.language_priority,
                )
                for row in rows
            ],
            "page": page,
            "page_size": limit,
            "total": int(total_row["total"]),
        }

    async def get_event(self, public_event_id: UUID, *, lang: str | None = None) -> dict[str, Any] | None:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                f"""
                select
                  id,
                  upstream_event_id,
                  idempotency_key,
                  schema_version,
                  event_time,
                  generated_at,
                  received_at,
                  severity,
                  relevance_score,
                  confirmation_state,
                  public_source_links,
                  topic_tags,
                  content_category,
                  mentioned_actors,
                  route_metadata,
{public_event_translations_select_sql()} as translations
                from public_events
                where id = %(id)s and is_visible = true
                """,
                {"id": public_event_id},
            )
            row = await cur.fetchone()
        await self.db.conn.commit()
        return (
            shape_public_event(
                row,
                lang=lang,
                default_language=self.default_language,
                language_priority=self.language_priority,
            )
            if row
            else None
        )

    async def list_tags(self) -> list[dict[str, Any]]:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                select tag, count(*)::int as count
                from public_events, unnest(topic_tags) as tag
                where is_visible = true
                group by tag
                order by count desc, tag asc
                limit 200
                """
            )
            rows = await cur.fetchall()
        await self.db.conn.commit()
        return [_json_ready(row) for row in rows]

    async def list_categories(self) -> list[dict[str, Any]]:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                select content_category as category, count(*)::int as count
                from public_events
                where is_visible = true and content_category is not null
                group by content_category
                order by count desc, content_category asc
                limit 100
                """
            )
            rows = await cur.fetchall()
        await self.db.conn.commit()
        return [_json_ready(row) for row in rows]

    async def overview_stats(self) -> dict[str, Any]:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                select
                  count(*)::int as total_events,
                  count(*) filter (where severity = 'S')::int as s_events,
                  count(*) filter (where severity = 'A')::int as a_events,
                  max(coalesce(event_time, generated_at, received_at)) as latest_event_time
                from public_events
                where is_visible = true
                """
            )
            row = await cur.fetchone()
        await self.db.conn.commit()
        return _json_ready(row or {})


def _build_filters(**filters: Any) -> tuple[str, dict[str, Any]]:
    clauses = ["is_visible = true"]
    params: dict[str, Any] = {}
    if filters.get("severity"):
        clauses.append("severity = %(severity)s")
        params["severity"] = filters["severity"]
    if filters.get("confirmation_state"):
        clauses.append("confirmation_state = %(confirmation_state)s")
        params["confirmation_state"] = filters["confirmation_state"]
    if filters.get("tag"):
        clauses.append("%(tag)s = any(topic_tags)")
        params["tag"] = filters["tag"]
    if filters.get("category"):
        clauses.append("content_category = %(category)s")
        params["category"] = filters["category"]
    if filters.get("from_time"):
        clauses.append("coalesce(event_time, generated_at, received_at) >= %(from_time)s")
        params["from_time"] = filters["from_time"]
    if filters.get("to_time"):
        clauses.append("coalesce(event_time, generated_at, received_at) <= %(to_time)s")
        params["to_time"] = filters["to_time"]
    if filters.get("q"):
        clauses.append(
            f"""
            ({public_event_translation_search_exists_sql()})
            """
        )
        params["q"] = f"%{filters['q']}%"
    return f"where {' and '.join(clauses)}", params


def _build_raw_item_filters(**filters: Any) -> tuple[str, dict[str, Any]]:
    clauses = ["is_visible = true"]
    params: dict[str, Any] = {}
    if filters.get("source_type"):
        clauses.append("source_type = %(source_type)s")
        params["source_type"] = filters["source_type"]
    if filters.get("source_group"):
        clauses.append("source_group = %(source_group)s")
        params["source_group"] = filters["source_group"]
    if filters.get("tag"):
        clauses.append("%(tag)s = any(topic_tags)")
        params["tag"] = filters["tag"]
    if filters.get("category"):
        clauses.append("content_category = %(category)s")
        params["category"] = filters["category"]
    if filters.get("min_relevance_score") is not None:
        clauses.append("relevance_score >= %(min_relevance_score)s")
        params["min_relevance_score"] = filters["min_relevance_score"]
    if filters.get("from_time"):
        clauses.append("coalesce(published_at, ingested_at, received_at) >= %(from_time)s")
        params["from_time"] = filters["from_time"]
    if filters.get("to_time"):
        clauses.append("coalesce(published_at, ingested_at, received_at) <= %(to_time)s")
        params["to_time"] = filters["to_time"]
    if filters.get("event_id"):
        clauses.append(
            """
            exists (
              select 1
              from public_events pe
              where pe.id = %(event_id)s
                and pe.upstream_event_id = any(public_raw_items.upstream_event_ids)
            )
            """
        )
        params["event_id"] = filters["event_id"]
    if filters.get("q"):
        clauses.append(
            f"""
            (
              title ilike %(q)s
              or original_content ilike %(q)s
              or source_name ilike %(q)s
              or {public_raw_item_translation_search_exists_sql()}
            )
            """
        )
        params["q"] = f"%{filters['q']}%"
    return f"where {' and '.join(clauses)}", params


def _json_ready(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def public_event_translations_select_sql(
    *,
    event_alias: str = "public_events",
    translation_alias: str = "pet",
    indent: str = "                  ",
) -> str:
    return f"""{indent}coalesce(
{indent}  (
{indent}    select jsonb_agg(
{indent}      jsonb_build_object(
{indent}        'language', {translation_alias}.language,
{indent}        'title', {translation_alias}.title,
{indent}        'summary', {translation_alias}.summary
{indent}      )
{indent}      order by
{indent}        case {translation_alias}.language
{indent}          when '{PUBLIC_LANGUAGE_EN}' then 0
{indent}          when '{PUBLIC_LANGUAGE_ZH_HANT}' then 1
{indent}          else 2
{indent}        end,
{indent}        {translation_alias}.language
{indent}    )
{indent}    from public_events_translations {translation_alias}
{indent}    where {translation_alias}.public_event_id = {event_alias}.id
{indent}  ),
{indent}  '[]'::jsonb
{indent})"""


def public_event_translation_search_exists_sql(
    *,
    event_alias: str = "public_events",
    translation_alias: str = "pet_search",
) -> str:
    return f"""exists (
              select 1
              from public_events_translations {translation_alias}
              where {translation_alias}.public_event_id = {event_alias}.id
                and (
                  {translation_alias}.title ilike %(q)s
                  or {translation_alias}.summary ilike %(q)s
                )
            )"""


def public_event_translation_rows(payload: PublicEventIngestRequest) -> list[dict[str, Any]]:
    rows_by_language: dict[str, dict[str, Any]] = {}

    def add_row(*, language: str, title: str | None, summary: str | None) -> None:
        if not title and not summary:
            return
        rows_by_language[language] = {
            "public_event_id": None,
            "language": language,
            "title": title,
            "summary": summary,
        }

    for translation in payload.translations:
        add_row(language=translation.language, title=translation.title, summary=translation.summary)
    return list(rows_by_language.values())


def public_raw_item_translations_select_sql(
    *,
    raw_item_alias: str = "public_raw_items",
    translation_alias: str = "prit",
    indent: str = "                  ",
) -> str:
    return f"""{indent}coalesce(
{indent}  (
{indent}    select jsonb_agg(
{indent}      jsonb_build_object(
{indent}        'language', {translation_alias}.language,
{indent}        'summary', {translation_alias}.summary,
{indent}        'full_translation', {translation_alias}.full_translation,
{indent}        'status', {translation_alias}.status,
{indent}        'is_truncated', {translation_alias}.is_truncated,
{indent}        'source_chars', {translation_alias}.source_chars,
{indent}        'translation_chars', {translation_alias}.translation_chars
{indent}      )
{indent}      order by
{indent}        case {translation_alias}.language
{indent}          when '{PUBLIC_LANGUAGE_EN}' then 0
{indent}          when '{PUBLIC_LANGUAGE_ZH_HANT}' then 1
{indent}          else 2
{indent}        end,
{indent}        {translation_alias}.language
{indent}    )
{indent}    from public_raw_item_translations {translation_alias}
{indent}    where {translation_alias}.public_raw_item_id = {raw_item_alias}.id
{indent}  ),
{indent}  '[]'::jsonb
{indent})"""


def public_raw_item_translation_search_exists_sql(
    *,
    raw_item_alias: str = "public_raw_items",
    translation_alias: str = "prit_search",
) -> str:
    return f"""exists (
              select 1
              from public_raw_item_translations {translation_alias}
              where {translation_alias}.public_raw_item_id = {raw_item_alias}.id
                and (
                  {translation_alias}.summary ilike %(q)s
                  or {translation_alias}.full_translation ilike %(q)s
                )
            )"""


def public_raw_item_translation_rows(payload: PublicRawItemIngestRequest) -> list[dict[str, Any]]:
    rows_by_language: dict[str, dict[str, Any]] = {}

    def add_row(
        *,
        language: str,
        summary: str | None,
        full_translation: str | None,
        status: str | None = None,
        is_truncated: bool = False,
        source_chars: int | None = None,
        translation_chars: int | None = None,
    ) -> None:
        if not summary and not full_translation:
            return
        rows_by_language[language] = {
            "public_raw_item_id": None,
            "language": language,
            "summary": summary,
            "full_translation": full_translation,
            "status": status,
            "is_truncated": is_truncated,
            "source_chars": source_chars,
            "translation_chars": translation_chars,
        }

    for translation in payload.translations:
        add_row(
            language=translation.language,
            summary=translation.summary,
            full_translation=translation.full_translation,
            status=translation.status,
            is_truncated=translation.is_truncated,
            source_chars=translation.source_chars,
            translation_chars=translation.translation_chars,
        )
    return list(rows_by_language.values())


def normalize_public_language(lang: str | None, *, default_language: str = DEFAULT_PUBLIC_LANGUAGE) -> str:
    normalized = (lang or "").strip()
    if not normalized or not LANGUAGE_CODE_RE.match(normalized):
        return default_language
    return normalized


def shape_public_event(
    row: dict[str, Any],
    *,
    lang: str | None = None,
    default_language: str = DEFAULT_PUBLIC_LANGUAGE,
    language_priority: tuple[str, ...] = (PUBLIC_LANGUAGE_EN, PUBLIC_LANGUAGE_ZH_HANT),
) -> dict[str, Any]:
    data = _json_ready(row)
    requested_lang = normalize_public_language(lang, default_language=default_language)
    translations = _public_translation_rows(data, language_priority=language_priority)
    selected_lang = _selected_language(translations, requested_lang, default_language=default_language)
    data["title"] = _localized_value(
        translations,
        field="title",
        selected_lang=selected_lang,
        default_language=default_language,
    )
    data["summary"] = _localized_value(
        translations,
        field="summary",
        selected_lang=selected_lang,
        default_language=default_language,
    )
    data["language"] = selected_lang
    data["available_languages"] = _available_languages(translations)
    data["translations"] = translations
    return data


def shape_public_raw_item(
    row: dict[str, Any],
    *,
    lang: str | None = None,
    default_language: str = DEFAULT_PUBLIC_LANGUAGE,
    language_priority: tuple[str, ...] = (PUBLIC_LANGUAGE_EN, PUBLIC_LANGUAGE_ZH_HANT),
) -> dict[str, Any]:
    data = _json_ready(row)
    requested_lang = normalize_public_language(lang, default_language=default_language)
    translations = _public_raw_item_translation_rows(data, language_priority=language_priority)
    selected_lang = _selected_raw_item_language(translations, requested_lang, default_language=default_language)
    data["summary"] = _localized_value(
        translations,
        field="summary",
        selected_lang=selected_lang,
        default_language=default_language,
    )
    data["full_translation"] = _localized_value(
        translations,
        field="full_translation",
        selected_lang=selected_lang,
        default_language=default_language,
    )
    data["language"] = selected_lang
    data["available_languages"] = _available_languages(translations)
    data["translations"] = translations
    return data


def _selected_language(
    translations: list[dict[str, str | None]],
    requested_lang: str,
    *,
    default_language: str,
) -> str:
    if _has_public_content(translations, requested_lang):
        return requested_lang
    if _has_public_content(translations, default_language):
        return default_language
    if default_language != PUBLIC_LANGUAGE_EN and _has_public_content(translations, PUBLIC_LANGUAGE_EN):
        return PUBLIC_LANGUAGE_EN
    for translation in translations:
        language = translation.get("language")
        if language and _translation_has_content(translation):
            return language
    return requested_lang


def _available_languages(translations: list[dict[str, str | None]]) -> list[str]:
    return [translation["language"] for translation in translations if translation.get("language")]


def _has_public_content(translations: list[dict[str, str | None]], lang: str) -> bool:
    return any(translation.get("language") == lang and _translation_has_content(translation) for translation in translations)


def _localized_value(
    translations: list[dict[str, str | None]],
    *,
    field: str,
    selected_lang: str,
    default_language: str,
) -> str | None:
    selected_value = _translation_value(translations, language=selected_lang, field=field)
    if selected_value:
        return selected_value
    default_value = _translation_value(translations, language=default_language, field=field)
    if default_value:
        return default_value
    if default_language != PUBLIC_LANGUAGE_EN:
        english_value = _translation_value(translations, language=PUBLIC_LANGUAGE_EN, field=field)
        if english_value:
            return english_value
    for translation in translations:
        value = translation.get(field)
        if value:
            return str(value)
    return None


def _public_translation_rows(
    row: dict[str, Any],
    *,
    language_priority: tuple[str, ...] = (PUBLIC_LANGUAGE_EN, PUBLIC_LANGUAGE_ZH_HANT),
) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    seen: set[str] = set()

    for raw_translation in row.get("translations") or []:
        if not isinstance(raw_translation, dict):
            continue
        language = raw_translation.get("language")
        if not isinstance(language, str) or not language.strip():
            continue
        title = _optional_string(raw_translation.get("title"))
        summary = _optional_string(raw_translation.get("summary"))
        if not title and not summary:
            continue
        normalized_language = language.strip()
        rows.append({"language": normalized_language, "title": title, "summary": summary})
        seen.add(normalized_language)

    return sorted(rows, key=lambda item: _language_sort_key(item["language"], language_priority=language_priority))


def _public_raw_item_translation_rows(
    row: dict[str, Any],
    *,
    language_priority: tuple[str, ...] = (PUBLIC_LANGUAGE_EN, PUBLIC_LANGUAGE_ZH_HANT),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw_translation in row.get("translations") or []:
        if not isinstance(raw_translation, dict):
            continue
        language = raw_translation.get("language")
        if not isinstance(language, str) or not language.strip():
            continue
        summary = _optional_string(raw_translation.get("summary"))
        full_translation = _optional_string(raw_translation.get("full_translation"))
        if not summary and not full_translation:
            continue
        normalized_language = language.strip()
        rows.append(
            {
                "language": normalized_language,
                "summary": summary,
                "full_translation": full_translation,
                "status": _optional_string(raw_translation.get("status")),
                "is_truncated": bool(raw_translation.get("is_truncated")),
                "source_chars": _optional_int(raw_translation.get("source_chars")),
                "translation_chars": _optional_int(raw_translation.get("translation_chars")),
            }
        )
        seen.add(normalized_language)

    return sorted(rows, key=lambda item: _language_sort_key(item["language"], language_priority=language_priority))


def _selected_raw_item_language(
    translations: list[dict[str, Any]],
    requested_lang: str,
    *,
    default_language: str,
) -> str:
    if _has_raw_item_content(translations, requested_lang):
        return requested_lang
    if _has_raw_item_content(translations, default_language):
        return default_language
    if default_language != PUBLIC_LANGUAGE_EN and _has_raw_item_content(translations, PUBLIC_LANGUAGE_EN):
        return PUBLIC_LANGUAGE_EN
    for translation in translations:
        language = translation.get("language")
        if language and _raw_item_translation_has_content(translation):
            return str(language)
    return requested_lang


def _has_raw_item_content(translations: list[dict[str, Any]], lang: str) -> bool:
    return any(translation.get("language") == lang and _raw_item_translation_has_content(translation) for translation in translations)


def _raw_item_translation_has_content(translation: dict[str, Any]) -> bool:
    return bool(translation.get("summary") or translation.get("full_translation"))


def _translation_value(translations: list[dict[str, str | None]], *, language: str, field: str) -> str | None:
    for translation in translations:
        if translation.get("language") == language:
            value = translation.get(field)
            return str(value) if value else None
    return None


def _translation_has_content(translation: dict[str, str | None]) -> bool:
    return bool(translation.get("title") or translation.get("summary"))


def _optional_string(value: Any) -> str | None:
    return str(value) if value else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _max_translation_chars(payload: PublicRawItemIngestRequest) -> int | None:
    candidates: list[int] = []
    for translation in payload.translations:
        if translation.translation_chars is not None:
            candidates.append(translation.translation_chars)
        elif translation.full_translation:
            candidates.append(len(translation.full_translation))
    return max(candidates) if candidates else None


def _language_sort_key(
    language: str,
    *,
    language_priority: tuple[str, ...] = (PUBLIC_LANGUAGE_EN, PUBLIC_LANGUAGE_ZH_HANT),
) -> tuple[int, str]:
    try:
        return (language_priority.index(language), language)
    except ValueError:
        return (len(language_priority), language)
