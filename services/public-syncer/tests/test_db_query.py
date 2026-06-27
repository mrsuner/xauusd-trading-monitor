from __future__ import annotations

import inspect

from public_syncer.db import (
    Database,
    public_outbox_translations_select_sql,
    raw_item_translations_select_sql,
    raw_item_upstream_event_ids_sql,
)


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def test_public_outbox_translations_select_sql_reads_translation_rows() -> None:
    sql = _compact(public_outbox_translations_select_sql())

    assert "from public_outbox_translations pot" in sql
    assert "where pot.public_outbox_id = p.id" in sql
    assert "'language', pot.language" in sql
    assert "'title', pot.title" in sql
    assert "'summary', pot.summary" in sql
    assert "'status', pot.status" in sql
    assert "order by pot.language" in sql


def test_raw_item_translations_select_sql_reads_completed_rows() -> None:
    sql = _compact(raw_item_translations_select_sql())

    assert "from raw_item_translations rit" in sql
    assert "where rit.raw_item_id = r.id" in sql
    assert "rit.status in ('completed', 'completed_truncated')" in sql
    assert "'full_translation', rit.full_translation" in sql
    assert "'input_chars', rit.input_chars" in sql


def test_raw_item_upstream_event_ids_sql_reads_processing_and_events() -> None:
    sql = _compact(raw_item_upstream_event_ids_sql())

    assert "select p.event_id" in sql
    assert "from events e" in sql
    assert "where r.id = any(e.raw_item_ids)" in sql
    assert "'{}'::uuid[]" in sql


def test_refresh_raw_item_sync_candidates_excludes_unchanged_existing_rows_before_limit() -> None:
    source = inspect.getsource(Database.refresh_raw_item_sync_candidates)
    sql = _compact(source)

    assert "with eligible as" in sql
    assert "state.source_updated_at as previous_source_updated_at" in sql
    assert (
        "from eligible where previous_source_updated_at is null "
        "or previous_source_updated_at is distinct from source_updated_at"
    ) in sql
    assert "order by sort_time asc limit %(limit)s" in sql


def test_claim_next_raw_item_does_not_select_legacy_translation_fields() -> None:
    source = inspect.getsource(Database.claim_next_raw_item)
    sql = _compact(source)

    assert "r.summary_zh" not in sql
    assert "r.summary_en" not in sql
    assert "r.full_translation_zh" not in sql
    assert "r.full_translation_en" not in sql
    assert "raw_item_translations_select_sql()" in source


def test_claim_next_public_event_does_not_select_legacy_translation_fields() -> None:
    source = inspect.getsource(Database.claim_next_item)
    sql = _compact(source)

    assert "p.public_title_zh" not in sql
    assert "p.public_summary_zh" not in sql
    assert "p.public_title_en" not in sql
    assert "p.public_summary_en" not in sql
    assert "public_outbox_translations_select_sql()" in source
