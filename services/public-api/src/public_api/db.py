from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import PublicEventIngestRequest
from .security import body_sha256


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
    def __init__(self, db: Database, *, max_page_size: int) -> None:
        self.db = db
        self.max_page_size = max_page_size

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
        params = {
            "upstream_event_id": payload.upstream_event_id,
            "idempotency_key": payload.idempotency_key,
            "schema_version": payload.schema_version,
            "event_time": payload.event_time,
            "generated_at": payload.generated_at,
            "severity": payload.severity,
            "relevance_score": payload.relevance_score,
            "confirmation_state": payload.confirmation_state,
            "public_title_zh": payload.public_title_zh,
            "public_summary_zh": payload.public_summary_zh,
            "public_title_en": payload.public_title_en,
            "public_summary_en": payload.public_summary_en,
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
                  public_title_zh,
                  public_summary_zh,
                  public_title_en,
                  public_summary_en,
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
                  %(public_title_zh)s,
                  %(public_summary_zh)s,
                  %(public_title_en)s,
                  %(public_summary_en)s,
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
                    public_title_zh = excluded.public_title_zh,
                    public_summary_zh = excluded.public_summary_zh,
                    public_title_en = excluded.public_title_en,
                    public_summary_en = excluded.public_summary_en,
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
            await cur.execute(
                """
                insert into public_ingest_requests (
                  idempotency_key,
                  upstream_event_id,
                  public_event_id,
                  request_hash,
                  key_id,
                  nonce,
                  status
                )
                values (
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

    async def record_rejected_ingest(
        self,
        *,
        raw_body: bytes,
        key_id: str | None,
        nonce: str | None,
        error_message: str,
        idempotency_key: str | None = None,
    ) -> None:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
                insert into public_ingest_requests (
                  idempotency_key,
                  request_hash,
                  key_id,
                  nonce,
                  status,
                  error_message
                )
                values (
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
                    "idempotency_key": idempotency_key,
                    "request_hash": body_sha256(raw_body),
                    "key_id": key_id,
                    "nonce": nonce,
                    "error_message": error_message[:2000],
                },
            )
        await self.db.conn.commit()

    async def list_events(
        self,
        *,
        page: int,
        page_size: int,
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
                  public_title_zh,
                  public_summary_zh,
                  public_title_en,
                  public_summary_en,
                  public_source_links,
                  topic_tags,
                  content_category,
                  mentioned_actors,
                  route_metadata
                from public_events
                {where}
                order by coalesce(event_time, generated_at, received_at) desc, received_at desc
                limit %(limit)s offset %(offset)s
                """,
                {**params, "limit": limit, "offset": offset},
            )
            rows = await cur.fetchall()
        await self.db.conn.commit()
        return {"items": [_json_ready(row) for row in rows], "page": page, "page_size": limit, "total": int(total_row["total"])}

    async def get_event(self, public_event_id: UUID) -> dict[str, Any] | None:
        async with self.db.conn.cursor() as cur:
            await cur.execute(
                """
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
                  public_title_zh,
                  public_summary_zh,
                  public_title_en,
                  public_summary_en,
                  public_source_links,
                  topic_tags,
                  content_category,
                  mentioned_actors,
                  route_metadata
                from public_events
                where id = %(id)s and is_visible = true
                """,
                {"id": public_event_id},
            )
            row = await cur.fetchone()
        await self.db.conn.commit()
        return _json_ready(row) if row else None

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
            """
            (
              public_title_zh ilike %(q)s
              or public_summary_zh ilike %(q)s
              or public_title_en ilike %(q)s
              or public_summary_en ilike %(q)s
            )
            """
        )
        params["q"] = f"%{filters['q']}%"
    return f"where {' and '.join(clauses)}", params


def _json_ready(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)
