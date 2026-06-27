from __future__ import annotations

from alert_dispatcher.db import _event_context_query
from alert_dispatcher.raw_item_translation_sql import RAW_ITEM_DISPLAY_LANGUAGES


def _compact(sql: str) -> str:
    return " ".join(sql.split())


def test_raw_item_translation_language_convention() -> None:
    assert RAW_ITEM_DISPLAY_LANGUAGES == ("zh-Hant", "en")


def test_event_context_query_reads_raw_item_translation_summaries_without_legacy_fallback() -> None:
    sql = _compact(_event_context_query())

    assert "raw_item_translation_" not in sql
    assert "tr_zh.summary as raw_item_summary_zh" in sql
    assert "tr_en.summary as raw_item_summary_en" in sql
    assert "r.summary_zh" not in sql
    assert "r.summary_en" not in sql
    assert (
        "left join raw_item_translations tr_zh on tr_zh.raw_item_id = r.id "
        "and tr_zh.language = 'zh-Hant'"
    ) in sql
    assert "left join raw_item_translations tr_en on tr_en.raw_item_id = r.id and tr_en.language = 'en'" in sql
