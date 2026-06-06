from __future__ import annotations

from event_router.db import _event_context_query


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def test_event_context_query_reads_raw_item_translation_summaries_with_legacy_fallback() -> None:
    sql = _compact(_event_context_query())

    assert "coalesce(tr_zh.summary, r.summary_zh) as raw_item_summary_zh" in sql
    assert "coalesce(tr_en.summary, r.summary_en) as raw_item_summary_en" in sql
    assert (
        "left join raw_item_translations tr_zh on tr_zh.raw_item_id = r.id "
        "and tr_zh.language = 'zh-Hant'"
    ) in sql
    assert "left join raw_item_translations tr_en on tr_en.raw_item_id = r.id and tr_en.language = 'en'" in sql


def test_event_context_query_groups_translation_summaries_for_topic_aggregation() -> None:
    sql = _compact(_event_context_query())

    assert "r.summary_en, tr_zh.summary, tr_en.summary, r.text_clean" in sql
