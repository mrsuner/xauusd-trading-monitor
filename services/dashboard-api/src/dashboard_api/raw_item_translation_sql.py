from __future__ import annotations

RAW_ITEM_ZH_LANGUAGE = "zh-Hant"
RAW_ITEM_EN_LANGUAGE = "en"
RAW_ITEM_DISPLAY_LANGUAGES = (RAW_ITEM_ZH_LANGUAGE, RAW_ITEM_EN_LANGUAGE)


def raw_item_translation_summary_select_sql(
    *,
    raw_alias: str = "r",
    zh_alias: str = "tr_zh",
    en_alias: str = "tr_en",
    zh_output_alias: str = "summary_zh",
    en_output_alias: str = "summary_en",
    indent: str = "          ",
) -> str:
    return (
        f"{indent}{zh_alias}.summary as {zh_output_alias},\n"
        f"{indent}{en_alias}.summary as {en_output_alias},"
    )


def raw_item_translation_full_translation_select_sql(
    *,
    raw_alias: str = "r",
    zh_alias: str = "tr_zh",
    en_alias: str = "tr_en",
    zh_output_alias: str = "full_translation_zh",
    en_output_alias: str = "full_translation_en",
    indent: str = "          ",
) -> str:
    return (
        f"{indent}{zh_alias}.full_translation as {zh_output_alias},\n"
        f"{indent}{en_alias}.full_translation as {en_output_alias},"
    )


def raw_item_translation_join_sql(
    *,
    raw_alias: str = "r",
    zh_alias: str = "tr_zh",
    en_alias: str = "tr_en",
    indent: str = "        ",
) -> str:
    return f"""
{indent}left join raw_item_translations {zh_alias} on {zh_alias}.raw_item_id = {raw_alias}.id and {zh_alias}.language = '{RAW_ITEM_ZH_LANGUAGE}'
{indent}left join raw_item_translations {en_alias} on {en_alias}.raw_item_id = {raw_alias}.id and {en_alias}.language = '{RAW_ITEM_EN_LANGUAGE}'
""".rstrip()


def raw_item_translation_json_lateral_sql(
    *,
    raw_alias: str = "r",
    output_alias: str = "translations",
    translation_alias: str = "rt",
    indent: str = "        ",
) -> str:
    return f"""
{indent}left join lateral (
{indent}  select jsonb_agg(
{indent}    jsonb_build_object(
{indent}      'language', {translation_alias}.language,
{indent}      'summary', {translation_alias}.summary,
{indent}      'full_translation', {translation_alias}.full_translation,
{indent}      'status', {translation_alias}.status,
{indent}      'model_provider', {translation_alias}.model_provider,
{indent}      'model', {translation_alias}.model,
{indent}      'error', {translation_alias}.error,
{indent}      'input_chars', {translation_alias}.input_chars,
{indent}      'updated_at', {translation_alias}.updated_at
{indent}    )
{indent}    order by {translation_alias}.language
{indent}  ) as items
{indent}  from raw_item_translations {translation_alias}
{indent}  where {translation_alias}.raw_item_id = {raw_alias}.id
{indent}) {output_alias} on true
""".rstrip()


def raw_item_translation_search_lateral_sql(
    *,
    raw_alias: str = "r",
    output_alias: str = "translation_search",
    translation_alias: str = "rt",
    indent: str = "        ",
) -> str:
    return f"""
{indent}left join lateral (
{indent}  select string_agg(concat_ws(' ', {translation_alias}.summary, {translation_alias}.full_translation), ' ') as search_text
{indent}  from raw_item_translations {translation_alias}
{indent}  where {translation_alias}.raw_item_id = {raw_alias}.id
{indent}) {output_alias} on true
""".rstrip()
