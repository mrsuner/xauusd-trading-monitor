from __future__ import annotations

from public_syncer.db import public_outbox_translations_select_sql


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
