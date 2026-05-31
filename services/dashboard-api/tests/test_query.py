from __future__ import annotations

from dashboard_api.repository import build_raw_items_query
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
    assert "r.title !~* '^\\[no title\\]'" in sql


def test_raw_items_query_can_include_empty_text() -> None:
    builder = build_raw_items_query({"include_empty_text": True})

    assert "r.title !~* '^\\[no title\\]'" not in builder.list_sql()
