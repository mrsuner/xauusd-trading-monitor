from __future__ import annotations

from event_router.db import _event_context_query, public_outbox_translation_enrichment_sql
from event_router.raw_item_translation_sql import RAW_ITEM_DISPLAY_LANGUAGES


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
    assert "from event_translations et" in sql
    assert "as event_translations" in sql
    assert (
        "left join raw_item_translations tr_zh on tr_zh.raw_item_id = r.id "
        "and tr_zh.language = 'zh-Hant'"
    ) in sql
    assert "left join raw_item_translations tr_en on tr_en.raw_item_id = r.id and tr_en.language = 'en'" in sql


def test_event_context_query_groups_translation_summaries_for_topic_aggregation() -> None:
    sql = _compact(_event_context_query())

    assert "tr_zh.summary, tr_en.summary, r.text_clean" in sql


def test_public_outbox_translation_enrichment_is_idempotent_and_web_only() -> None:
    sql = _compact(public_outbox_translation_enrichment_sql())

    assert "on conflict (public_outbox_id, language) do update" in sql
    assert "nullif(btrim(public_outbox_translations.summary), '') is not null" in sql
    assert "then public_outbox_translations.summary else excluded.summary" in sql
    assert "status = public_outbox_translations.status" in sql
    assert "returning public_outbox_id" in sql
    assert "publish_status_web = 'pending'" in sql
    assert "retry_count_web = 0" in sql
    assert "p.publish_status_web in ('sent', 'skipped', 'failed')" in sql
    assert "publish_status_telegram" not in sql
    assert "publish_status_x" not in sql


def test_public_outbox_translation_enrichment_uses_configured_languages_and_primary_raw_item() -> None:
    sql = _compact(public_outbox_translation_enrichment_sql())

    assert "select unnest(%(languages)s::text[])" in sql
    assert "from unnest(e.raw_item_ids) with ordinality" in sql
    assert "order by position limit 1" in sql
    assert "rit.status in ('completed', 'completed_truncated')" in sql
    assert "nullif(btrim(rit.summary), '') is not null" in sql
    assert "%(lookback_hours)s <= 0" in sql
    assert "limit %(limit)s" in sql
