from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from tickbase_anomaly_consumer.db import Database
from tickbase_anomaly_consumer.mapping import SeverityThresholds, map_anomaly
from tickbase_anomaly_consumer.models import AnomalyEvent

pytestmark = pytest.mark.asyncio

THRESHOLDS = SeverityThresholds(s_multiplier=3.0, a_multiplier=2.0, b_multiplier=1.5)


def _event(event_id: int, *, change_abs: float, threshold: float = 10.0) -> AnomalyEvent:
    return AnomalyEvent(
        id=event_id,
        rule_id="it-rule",
        asset_class="metal",
        base="XAU",
        quote="USD",
        direction="up",
        metric="abs",
        window_secs=60,
        threshold=threshold,
        change_abs=change_abs,
        change_pct=0.6,
        value_start=2400.0,
        value_end=2400.0 + change_abs,
        obs_count=5,
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        triggered_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )


async def _count(pool_url: str, sql: str, params) -> int:
    async with await psycopg.AsyncConnection.connect(pool_url, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()
        return int(next(iter(row.values())))


async def test_ingest_is_idempotent_and_routes_by_severity():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping DB integration test")

    # Isolated id space for this test.
    s_id, b_id = 90001, 90002
    clean_sql = "delete from tickbase_anomaly_ingest where tickbase_id = any(%s)"

    async with await psycopg.AsyncConnection.connect(url, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute(clean_sql, ([s_id, b_id],))
        await conn.commit()

    db = Database(url)
    await db.connect()
    try:
        s_event = _event(s_id, change_abs=35.0)  # 3.5x -> S -> public
        b_event = _event(b_id, change_abs=16.0)  # 1.6x -> B -> private only

        assert await db.ingest(s_event, map_anomaly(s_event, THRESHOLDS)) is True
        assert await db.ingest(s_event, map_anomaly(s_event, THRESHOLDS)) is False  # replay no-op
        assert await db.ingest(b_event, map_anomaly(b_event, THRESHOLDS)) is True

        assert await db.current_cursor() >= b_id
    finally:
        await db.close()

    # Exactly one event + one alert each; public_outbox only for the S event.
    ingest_join = (
        "select count(*) from {table} t "
        "join tickbase_anomaly_ingest i on i.event_id = t.event_id "
        "where i.tickbase_id = any(%s)"
    )
    assert await _count(url, ingest_join.format(table="alerts"), ([s_id, b_id],)) == 2
    assert await _count(url, ingest_join.format(table="public_outbox"), ([s_id, b_id],)) == 1
    assert await _count(
        url,
        "select count(*) from events e "
        "join tickbase_anomaly_ingest i on i.event_id = e.id "
        "where i.tickbase_id = any(%s) and e.event_type = 'market_anomaly'",
        ([s_id, b_id],),
    ) == 2

    # Cleanup: drop ingest rows first (they FK events with no cascade), then
    # the events (alerts/public_outbox cascade off events on delete).
    async with await psycopg.AsyncConnection.connect(url, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select event_id from tickbase_anomaly_ingest where tickbase_id = any(%s)",
                ([s_id, b_id],),
            )
            event_ids = [row["event_id"] for row in await cur.fetchall()]
            await cur.execute(clean_sql, ([s_id, b_id],))
            if event_ids:
                await cur.execute("delete from events where id = any(%s)", (event_ids,))
        await conn.commit()
