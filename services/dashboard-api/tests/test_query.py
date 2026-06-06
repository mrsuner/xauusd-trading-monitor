from __future__ import annotations

from dashboard_api.repository import build_public_outbox_query, build_raw_items_query
from dashboard_api.query import QueryBuilder, clamp_page_size, offset_for


def test_query_builder_adds_where_and_params() -> None:
    builder = QueryBuilder(
        base_select="select * from sources",
        base_count="select count(*) as total from sources",
        order_by="order by name",
    )

    builder.add_equal("source_type", "source_type", "telegram")
    builder.add_search(("name", "handle_or_url"), "q", "irna")

    assert builder.where_sql() == " where source_type = %(source_type)s and (name ilike %(q)s or handle_or_url ilike %(q)s)"
    assert builder.params == {"source_type": "telegram", "q": "%irna%"}
    assert builder.list_sql().endswith("order by name limit %(limit)s offset %(offset)s")
    assert builder.count_sql().endswith("where source_type = %(source_type)s and (name ilike %(q)s or handle_or_url ilike %(q)s)")


def test_pagination_helpers() -> None:
    assert clamp_page_size(500, 200) == 200
    assert clamp_page_size(0, 200) == 1
    assert offset_for(1, 50) == 0
    assert offset_for(3, 50) == 100


def test_raw_items_query_excludes_empty_text_by_default() -> None:
    builder = build_raw_items_query({})

    sql = builder.list_sql()

    assert "regexp_replace(coalesce(r.text_clean" in sql
    assert "regexp_replace(coalesce(r.summary_zh" not in sql
    assert "r.title !~* '^\\[no title\\]'" in sql


def test_raw_items_query_can_include_empty_text() -> None:
    builder = build_raw_items_query({"include_empty_text": True})

    assert "r.title !~* '^\\[no title\\]'" not in builder.list_sql()


def test_raw_items_query_filters_taxonomy_fields() -> None:
    builder = build_raw_items_query(
        {
            "content_category": "diplomacy",
            "topic_tag": "iran",
            "actor": "Trump",
        }
    )

    sql = builder.list_sql()

    assert "r.content_category = %(content_category)s" in sql
    assert "r.topic_tags ? %(topic_tag)s" in sql
    assert "r.mentioned_actors ? %(actor)s" in sql
    assert builder.params["content_category"] == "diplomacy"
    assert builder.params["topic_tag"] == "iran"
    assert builder.params["actor"] == "Trump"


def test_raw_items_query_includes_relevance_and_event_fields() -> None:
    builder = build_raw_items_query({})

    sql = builder.list_sql()

    assert "left join raw_item_processing p on p.raw_item_id = r.id" in sql
    assert "left join events e on e.id = p.event_id" in sql
    assert "p.relevance_score" in sql
    assert "(e.id is not null) as has_event" in sql


def test_raw_items_query_includes_translation_rows() -> None:
    builder = build_raw_items_query({"q": "gold"})

    sql = builder.list_sql()
    count_sql = builder.count_sql()

    assert "left join raw_item_translations tr_zh" in sql
    assert "tr_zh.language = 'zh-Hant'" in sql
    assert "left join raw_item_translations tr_en" in sql
    assert "coalesce(translations.items, '[]'::jsonb) as translations" in sql
    assert "coalesce(tr_zh.summary, r.summary_zh) as summary_zh" in sql
    assert "translation_search.search_text ilike %(q)s" in sql
    assert "translation_search.search_text" in count_sql
    assert builder.params["q"] == "%gold%"


def test_raw_items_query_filters_relevance_and_event_fields() -> None:
    builder = build_raw_items_query(
        {
            "classification_status": "completed",
            "is_relevant": True,
            "min_relevance_score": 70,
            "has_event": True,
        }
    )

    sql = builder.list_sql()

    assert "p.status = %(classification_status)s" in sql
    assert "p.is_relevant = %(is_relevant)s" in sql
    assert "p.relevance_score >= %(min_relevance_score)s" in sql
    assert "e.id is not null" in sql
    assert builder.params["classification_status"] == "completed"
    assert builder.params["is_relevant"] is True
    assert builder.params["min_relevance_score"] == 70


def test_public_outbox_query_filters_status_across_channels() -> None:
    builder = build_public_outbox_query({"publish_status": "failed"})

    sql = builder.list_sql()

    assert "from public_outbox p" in sql
    assert "p.publish_status_web = %(publish_status)s" in sql
    assert "p.publish_status_telegram = %(publish_status)s" in sql
    assert "p.publish_status_x = %(publish_status)s" in sql
    assert builder.params["publish_status"] == "failed"


def test_public_outbox_query_filters_status_by_channel() -> None:
    builder = build_public_outbox_query({"channel": "telegram", "publish_status": "sent"})

    sql = builder.list_sql()

    assert "p.publish_status_telegram = %(publish_status)s" in sql
    assert "p.publish_status_web = %(publish_status)s" not in sql
    assert "p.publish_status_x = %(publish_status)s" not in sql
    assert builder.params["publish_status"] == "sent"


def test_public_outbox_query_filters_public_flag_and_search() -> None:
    builder = build_public_outbox_query({"approved_for_public": True, "q": "gold"})

    sql = builder.list_sql()

    assert "p.approved_for_public = %(approved_for_public)s" in sql
    assert "p.public_title_zh ilike %(q)s" in sql
    assert "e.title ilike %(q)s" in sql
    assert builder.params["approved_for_public"] is True
    assert builder.params["q"] == "%gold%"
