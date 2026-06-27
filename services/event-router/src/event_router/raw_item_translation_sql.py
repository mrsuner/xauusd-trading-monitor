from __future__ import annotations

RAW_ITEM_ZH_LANGUAGE = "zh-Hant"
RAW_ITEM_EN_LANGUAGE = "en"
RAW_ITEM_DISPLAY_LANGUAGES = (RAW_ITEM_ZH_LANGUAGE, RAW_ITEM_EN_LANGUAGE)


def raw_item_translation_summary_select_sql(
    *,
    raw_alias: str = "r",
    zh_alias: str = "tr_zh",
    en_alias: str = "tr_en",
    zh_output_alias: str = "raw_item_summary_zh",
    en_output_alias: str = "raw_item_summary_en",
    indent: str = "                  ",
) -> str:
    return (
        f"{indent}{zh_alias}.summary as {zh_output_alias},\n"
        f"{indent}{en_alias}.summary as {en_output_alias},"
    )


def raw_item_translation_join_sql(
    *,
    raw_alias: str = "r",
    zh_alias: str = "tr_zh",
    en_alias: str = "tr_en",
    indent: str = "                ",
) -> str:
    return f"""
{indent}left join raw_item_translations {zh_alias}
{indent}  on {zh_alias}.raw_item_id = {raw_alias}.id
{indent} and {zh_alias}.language = '{RAW_ITEM_ZH_LANGUAGE}'
{indent}left join raw_item_translations {en_alias}
{indent}  on {en_alias}.raw_item_id = {raw_alias}.id
{indent} and {en_alias}.language = '{RAW_ITEM_EN_LANGUAGE}'
""".rstrip()


def raw_item_translation_group_by_sql(
    *,
    zh_alias: str = "tr_zh",
    en_alias: str = "tr_en",
    indent: str = "                  ",
) -> str:
    return f"""
{indent}{zh_alias}.summary,
{indent}{en_alias}.summary,
""".rstrip()
