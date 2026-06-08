from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import PublicEventIngestRequest
from .security import body_sha256

logger = logging.getLogger(__name__)

DEFAULT_PUBLIC_LANGUAGE = "en"
PUBLIC_LANGUAGES = {"en", "zh-Hant"}
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
        return {
            "items": [shape_public_event(row, lang=lang) for row in rows],
            "page": page,
            "page_size": limit,
            "total": int(total_row["total"]),
        }

    async def get_event(self, public_event_id: UUID, *, lang: str | None = None) -> dict[str, Any] | None:
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
        return shape_public_event(row, lang=lang) if row else None

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

    add_row(language=PUBLIC_LANGUAGE_ZH_HANT, title=payload.public_title_zh, summary=payload.public_summary_zh)
    add_row(language=PUBLIC_LANGUAGE_EN, title=payload.public_title_en, summary=payload.public_summary_en)
    for translation in payload.translations:
        add_row(language=translation.language, title=translation.title, summary=translation.summary)
    return list(rows_by_language.values())


def normalize_public_language(lang: str | None) -> str:
    return lang if lang in PUBLIC_LANGUAGES else DEFAULT_PUBLIC_LANGUAGE


def shape_public_event(row: dict[str, Any], *, lang: str | None = None) -> dict[str, Any]:
    data = _json_ready(row)
    requested_lang = normalize_public_language(lang)
    selected_lang = _selected_language(data, requested_lang)
    data["title"] = _localized_value(data, field="title", lang=selected_lang)
    data["summary"] = _localized_value(data, field="summary", lang=selected_lang)
    data["language"] = selected_lang
    data["available_languages"] = _available_languages(data)
    return data


def _selected_language(row: dict[str, Any], requested_lang: str) -> str:
    if _has_public_content(row, requested_lang):
        return requested_lang
    fallback_lang = "zh-Hant" if requested_lang == "en" else "en"
    if _has_public_content(row, fallback_lang):
        return fallback_lang
    return requested_lang


def _available_languages(row: dict[str, Any]) -> list[str]:
    return [lang for lang in ("en", "zh-Hant") if _has_public_content(row, lang)]


def _has_public_content(row: dict[str, Any], lang: str) -> bool:
    suffix = _language_suffix(lang)
    return bool(row.get(f"public_title_{suffix}") or row.get(f"public_summary_{suffix}"))


def _localized_value(row: dict[str, Any], *, field: str, lang: str) -> str | None:
    suffix = _language_suffix(lang)
    value = row.get(f"public_{field}_{suffix}")
    if value:
        return str(value)
    fallback_suffix = "zh" if suffix == "en" else "en"
    fallback = row.get(f"public_{field}_{fallback_suffix}")
    return str(fallback) if fallback else None


def _language_suffix(lang: str) -> str:
    return "zh" if lang == "zh-Hant" else "en"
