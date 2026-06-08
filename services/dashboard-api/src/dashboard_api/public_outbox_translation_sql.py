from __future__ import annotations


def public_outbox_translation_json_lateral_sql(
    *,
    outbox_alias: str = "p",
    output_alias: str = "translations",
    translation_alias: str = "pot",
    indent: str = "        ",
) -> str:
    return f"""
{indent}left join lateral (
{indent}  select jsonb_agg(
{indent}    jsonb_build_object(
{indent}      'language', {translation_alias}.language,
{indent}      'title', {translation_alias}.title,
{indent}      'summary', {translation_alias}.summary,
{indent}      'status', {translation_alias}.status,
{indent}      'updated_at', {translation_alias}.updated_at
{indent}    )
{indent}    order by {translation_alias}.language
{indent}  ) as items
{indent}  from public_outbox_translations {translation_alias}
{indent}  where {translation_alias}.public_outbox_id = {outbox_alias}.id
{indent}) {output_alias} on true
""".rstrip()


def public_outbox_translation_search_lateral_sql(
    *,
    outbox_alias: str = "p",
    output_alias: str = "translation_search",
    translation_alias: str = "pot",
    indent: str = "        ",
) -> str:
    return f"""
{indent}left join lateral (
{indent}  select string_agg(concat_ws(' ', {translation_alias}.title, {translation_alias}.summary), ' ') as search_text
{indent}  from public_outbox_translations {translation_alias}
{indent}  where {translation_alias}.public_outbox_id = {outbox_alias}.id
{indent}) {output_alias} on true
""".rstrip()
