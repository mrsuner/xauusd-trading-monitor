"""Opt-in local PostgreSQL coverage across source controls, collectors and syncer.

Prepare the isolated database with db/alembic.ini upgrade head first. No network
collection, model calls or notification delivery is performed by these tests.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dashboard_api.db import Database as DashboardDatabase
from dashboard_api.repository import DashboardRepository

for service in ("public-syncer", "rss-collector", "telegram-collector"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / service / "src"))

from public_syncer.db import Database as SyncDatabase
from rss_collector.db import Database as RssDatabase
from telegram_collector.db import Database as TelegramDatabase


@pytest.mark.parametrize("source_type", ["rss", "telegram"])
def test_source_stop_persists_across_new_connections_and_blocks_publication(source_type):
    name = os.getenv("TICKBASE_SOURCE_QA_DATABASE")
    if not name:
        pytest.skip("Opt in with a migrated tickbase_sources_qa_* database and local PUBLIC_DATABASE_URL.")
    assert name.startswith("tickbase_sources_qa_")
    original = os.environ["PUBLIC_DATABASE_URL"]
    assert conninfo_to_dict(original).get("host") in {"localhost", "127.0.0.1"}
    dsn = make_conninfo(original, dbname=name)
    source, independent_source, raw, independent_raw, combined, independent_event = [uuid4() for _ in range(6)]

    with psycopg.connect(dsn) as conn:
        for id, kind in ((source, source_type), (independent_source, "rss")):
            conn.execute("""INSERT INTO sources (id, name, handle_or_url, source_type,
                         source_group, official_level, priority)
                         VALUES (%s, 'Content QA fixture', %s, %s, 'qa', 'unofficial', 'P3')""",
                         (id, f"https://example.invalid/{id}", kind))
        for id, owner in ((raw, source), (independent_raw, independent_source)):
            conn.execute("""INSERT INTO raw_items (id, source_id, title, text_clean, dedupe_key, translation_status)
                         VALUES (%s, %s, 'QA title', 'QA reporting', %s, 'skipped')""", (id, owner, str(id)))
            # The real schema's insert trigger creates the processing row.
            conn.execute("UPDATE raw_item_processing SET is_relevant = true, relevance_score = 90 WHERE raw_item_id = %s", (id,))
        for id, items in ((combined, [raw, independent_raw]), (independent_event, [independent_raw])):
            conn.execute("INSERT INTO events (id, event_type, raw_item_ids) VALUES (%s, 'macro_policy', %s)", (id, items))
            conn.execute("INSERT INTO public_outbox (event_id, approved_for_public) VALUES (%s, true)", (id,))

    async def exercise():
        dashboard = DashboardDatabase(dsn, min_size=1, max_size=1)
        sync = SyncDatabase(dsn)
        collector = RssDatabase(dsn) if source_type == "rss" else TelegramDatabase(dsn)
        fetch_sources = collector.fetch_enabled_sources if source_type == "rss" else collector.fetch_enabled_telegram_sources
        await dashboard.connect()
        await sync.connect()
        await collector.connect()
        try:
            repo = DashboardRepository(dashboard, max_page_size=100)
            assert source in {row.id for row in await fetch_sources()}
            assert await sync.refresh_raw_item_sync_candidates(limit=100, min_relevance_score=60, backfill_enabled=True) == 2
            assert (await repo.set_source_enabled(source, enabled=False))["enabled"] is False
            # Recreate all connections, as after a service restart: no in-memory gate.
            await dashboard.close()
            dashboard = DashboardDatabase(dsn, min_size=1, max_size=1)
            await dashboard.connect()
            repo = DashboardRepository(dashboard, max_page_size=100)
            await sync.close()
            await sync.connect()
            await collector.close()
            await collector.connect()
            assert (await repo.get_source(source))["enabled"] is False
            assert source not in {row.id for row in await fetch_sources()}
            claim = dict(worker_id="content-qa", lock_timeout_seconds=60, max_attempts=3)
            assert (await sync.claim_next_raw_item(**claim)).id == independent_raw
            assert await sync.claim_next_raw_item(**claim) is None
            assert (await sync.claim_next_item(**claim)).event_id == independent_event
            assert await sync.claim_next_item(**claim) is None
            archived = await repo.archive_source(source)
            assert archived["archived_at"] is not None and archived["enabled"] is False
            assert await sync.refresh_raw_item_sync_candidates(limit=100, min_relevance_score=60, backfill_enabled=True) == 0
            assert source not in {row.id for row in await fetch_sources()}
            assert await sync.claim_next_item(**claim) is None
            # Existing explicit re-enable is an operator action, not an automatic restart.
            enabled = await repo.set_source_enabled(source, enabled=True)
            assert enabled["enabled"] is True and enabled["archived_at"] is None
            assert (await sync.claim_next_raw_item(**claim)).id == raw
            assert (await sync.claim_next_item(**claim)).event_id == combined
        finally:
            await collector.close()
            await sync.close()
            await dashboard.close()

    try:
        asyncio.run(exercise())
    finally:
        # Remove only this run's designated fixtures. Seeded catalog sources remain.
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM events WHERE id = ANY(%s::uuid[])", ([combined, independent_event],))
            conn.execute("DELETE FROM raw_items WHERE id = ANY(%s::uuid[])", ([raw, independent_raw],))
            conn.execute("DELETE FROM sources WHERE id = ANY(%s::uuid[])", ([source, independent_source],))
