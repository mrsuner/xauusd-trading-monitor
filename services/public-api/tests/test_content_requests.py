from __future__ import annotations

import os
from dataclasses import dataclass, field
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from alembic import command
from alembic.config import Config
import pytest
from httpx import ASGITransport, AsyncClient

from public_api.content_requests import withdraw
from public_api.db import Database, PublicRepository
from public_api.models import PublicEventIngestRequest, PublicRawItemIngestRequest
from public_api.app import create_app


@dataclass
class LocalQaDatabase:
    dsn: str = field(repr=False)


def test_withdrawal_requires_one_target_and_a_public_reason() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        withdraw(None, reason="Request")
    with pytest.raises(ValueError, match="public reason"):
        withdraw(None, event_id=uuid4(), reason=" ")


@pytest.fixture(scope="module")
def qa_database():
    name = os.getenv("TICKBASE_CONTENT_QA_DATABASE")
    if not name:
        pytest.skip("Opt in with TICKBASE_CONTENT_QA_DATABASE and a local PUBLIC_DATABASE_URL.")
    assert name.startswith("tickbase_content_qa_")
    original = os.environ["PUBLIC_DATABASE_URL"]
    info = conninfo_to_dict(original)
    assert info.get("host") in {"localhost", "127.0.0.1"}, "QA must use local PostgreSQL."
    dsn = make_conninfo(original, dbname=name)
    # Alembic expects a URL, not libpq key/value syntax.
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(original)
    os.environ["PUBLIC_DATABASE_URL"] = urlunsplit(parts._replace(path="/" + name))
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        os.environ["PUBLIC_DATABASE_URL"] = original
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as conn:
        # Minimal notification fixture mirrors the columns used by the operator tool.
        conn.execute("CREATE SCHEMA IF NOT EXISTS notify")
        conn.execute("CREATE TABLE IF NOT EXISTS notify.deliveries (id uuid PRIMARY KEY, public_event_id uuid, status text, error_code text, updated_at timestamptz)")
        conn.execute("CREATE TABLE IF NOT EXISTS notify.digest_editions (id uuid PRIMARY KEY, status text, invalidated_at timestamptz, invalidation_kind text, invalidation_reason text, updated_at timestamptz)")
        conn.execute("CREATE TABLE IF NOT EXISTS notify.digest_edition_events (edition_id uuid, public_event_id uuid)")
        conn.execute("CREATE TABLE IF NOT EXISTS notify.digest_batches (id uuid PRIMARY KEY, status text, error_code text, updated_at timestamptz)")
        conn.execute("CREATE TABLE IF NOT EXISTS notify.digest_batch_editions (batch_id uuid, edition_id uuid)")
    return LocalQaDatabase(dsn)


def seed(conn):
    raw, upstream_raw, event, upstream_event, independent, edition, batch = [uuid4() for _ in range(7)]
    conn.execute("""INSERT INTO public_events (id, upstream_event_id, idempotency_key, schema_version, severity)
                    VALUES (%s, %s, %s, 'public_event.v1', 'A'), (%s, %s, %s, 'public_event.v1', 'A')""",
                 (event, upstream_event, str(event), independent, uuid4(), str(independent)))
    conn.execute("""INSERT INTO public_raw_items (id, upstream_raw_item_id, idempotency_key, schema_version, upstream_event_ids)
                    VALUES (%s, %s, %s, 'public_raw_item.v1', %s)""", (raw, upstream_raw, str(raw), [upstream_event]))
    conn.execute("INSERT INTO notify.deliveries VALUES (%s, %s, 'pending', NULL, now()), (%s, %s, 'sent', NULL, now())",
                 (uuid4(), event, uuid4(), event))
    conn.execute("INSERT INTO notify.digest_editions (id, status) VALUES (%s, 'published')", (edition,))
    conn.execute("INSERT INTO notify.digest_edition_events VALUES (%s, %s)", (edition, event))
    conn.execute("INSERT INTO notify.digest_batches (id, status) VALUES (%s, 'pending')", (batch,))
    conn.execute("INSERT INTO notify.digest_batch_editions VALUES (%s, %s)", (batch, edition))
    return raw, event, independent, edition, batch


def test_preview_apply_retry_and_independent_reporting(qa_database):
    with psycopg.connect(qa_database.dsn, autocommit=True, row_factory=dict_row) as conn:
        # Roll back only this test's fixtures, not any shared database or service.
        with conn.transaction(force_rollback=True):
            raw, event, independent, edition, batch = seed(conn)
            preview = withdraw(conn, raw_item_id=raw, reason="Content request")
            assert preview["applied"] is False
            assert preview["event_ids"] == [str(event)]
            assert preview["pending_notifications"] == 1
            assert conn.execute("SELECT is_visible FROM public_raw_items WHERE id = %s", (raw,)).fetchone()["is_visible"]
            applied = withdraw(conn, raw_item_id=raw, reason="Content request", apply=True)
            assert applied["applied"]
            assert not conn.execute("SELECT is_visible FROM public_events WHERE id = %s", (event,)).fetchone()["is_visible"]
            assert not conn.execute("SELECT is_visible FROM public_raw_items WHERE id = %s", (raw,)).fetchone()["is_visible"]
            assert conn.execute("SELECT is_visible FROM public_events WHERE id = %s", (independent,)).fetchone()["is_visible"]
            assert conn.execute("SELECT status FROM notify.digest_editions WHERE id = %s", (edition,)).fetchone()["status"] == "invalidated"
            assert conn.execute("SELECT status FROM notify.digest_batches WHERE id = %s", (batch,)).fetchone()["status"] == "canceled"
            assert {row["status"] for row in conn.execute("SELECT status FROM notify.deliveries WHERE public_event_id = %s", (event,))} == {"canceled", "sent"}
            assert withdraw(conn, raw_item_id=raw, reason="Content request", apply=True)["pending_notifications"] == 0


@pytest.mark.asyncio
async def test_http_lists_and_details_hide_withdrawn_content_in_every_language(qa_database, monkeypatch):
    monkeypatch.setenv("PUBLIC_DATABASE_URL", qa_database.dsn)
    app = create_app()
    with psycopg.connect(qa_database.dsn, autocommit=True, row_factory=dict_row) as conn:
        raw, event, independent, edition, batch = seed(conn)
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://content-qa") as client:
                assert (await client.get(f"/events/{event}")).status_code == 200
                assert (await client.get(f"/raw-items/{raw}")).status_code == 200
                with psycopg.connect(qa_database.dsn, autocommit=True) as conn:
                    withdraw(conn, raw_item_id=raw, reason="Content request", apply=True)
                for lang in ("en", "zh-Hant", "th", "ja"):
                    assert (await client.get(f"/events/{event}", params={"lang": lang})).status_code == 404
                    assert (await client.get(f"/raw-items/{raw}", params={"lang": lang})).status_code == 404
                    events = (await client.get("/events", params={"lang": lang})).json()["items"]
                    assert str(event) not in {row["id"] for row in events}
                    assert str(independent) in {row["id"] for row in events}
                    raws = (await client.get("/raw-items", params={"lang": lang})).json()["items"]
                    assert str(raw) not in {row["id"] for row in raws}
    finally:
        with psycopg.connect(qa_database.dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM notify.digest_batch_editions WHERE batch_id = %s", (batch,))
            conn.execute("DELETE FROM notify.digest_batches WHERE id = %s", (batch,))
            conn.execute("DELETE FROM notify.digest_edition_events WHERE edition_id = %s", (edition,))
            conn.execute("DELETE FROM notify.digest_editions WHERE id = %s", (edition,))
            conn.execute("DELETE FROM notify.deliveries WHERE public_event_id = %s", (event,))
            conn.execute("DELETE FROM public_raw_items WHERE id = %s", (raw,))
            conn.execute("DELETE FROM public_events WHERE id = ANY(%s::uuid[])", ([event, independent],))


@pytest.mark.asyncio
async def test_event_reingest_with_a_new_payload_key_cannot_resurrect(qa_database):
    db = Database(qa_database.dsn)
    await db.connect()
    repo = PublicRepository(db, max_page_size=100)
    upstream = uuid4()
    payload = PublicEventIngestRequest.model_validate({
        "schema_version": "public_event.v1", "idempotency_key": f"event:{upstream}:v1",
        "upstream_event_id": upstream, "severity": "A",
        "translations": [{"language": "en", "title": "QA reporting", "summary": "QA summary"}],
    })
    try:
        first = await repo.ingest_event(payload, raw_body=b"qa", key_id=None, nonce=None)
        with psycopg.connect(qa_database.dsn, autocommit=True) as conn:
            withdraw(conn, event_id=first["public_event_id"], reason="Content request", apply=True)
        assert await repo.get_event(first["public_event_id"], lang="en") is None
        payload.idempotency_key = f"event:{upstream}:v2"
        again = await repo.ingest_event(payload, raw_body=b"qa2", key_id=None, nonce=None)
        assert again["withdrawn"] is True
        assert again["public_event_id"] == first["public_event_id"]
        assert await repo.get_event(first["public_event_id"], lang="ja") is None
    finally:
        async with db.conn.cursor() as cur:
            await cur.execute("DELETE FROM public_ingest_requests WHERE upstream_event_id = %s", (upstream,))
            await cur.execute("DELETE FROM public_events WHERE upstream_event_id = %s", (upstream,))
        await db.conn.commit()
        await db.close()


@pytest.mark.asyncio
async def test_withdrawn_raw_item_and_translations_stay_unavailable_after_resync(qa_database):
    db = Database(qa_database.dsn)
    await db.connect()
    repo = PublicRepository(db, max_page_size=100)
    upstream = uuid4()
    payload = PublicRawItemIngestRequest.model_validate({
        "schema_version": "public_raw_item.v1", "idempotency_key": f"raw_item:{upstream}:v1",
        "upstream_raw_item_id": upstream, "title": "QA source", "original_content": "QA original",
        "translations": [{"language": "ja", "summary": "QA translation"}],
    })
    try:
        first = await repo.ingest_raw_item(payload, raw_body=b"qa", key_id=None, nonce=None)
        with psycopg.connect(qa_database.dsn, autocommit=True) as conn:
            withdraw(conn, raw_item_id=first["public_raw_item_id"], reason="Content request", apply=True)
        payload.original_content = "Updated source must remain hidden"
        payload.translations[0].summary = "Updated translation must remain hidden"
        again = await repo.ingest_raw_item(payload, raw_body=b"qa2", key_id=None, nonce=None)
        assert again["withdrawn"] is True
        assert await repo.get_raw_item(first["public_raw_item_id"], lang="ja") is None
    finally:
        async with db.conn.cursor() as cur:
            await cur.execute("DELETE FROM public_ingest_requests WHERE public_raw_item_id IN (SELECT id FROM public_raw_items WHERE upstream_raw_item_id = %s)", (upstream,))
            await cur.execute("DELETE FROM public_raw_items WHERE upstream_raw_item_id = %s", (upstream,))
        await db.conn.commit()
        await db.close()
