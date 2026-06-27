"""drop public raw item legacy translation columns

Revision ID: 0005_drop_public_raw_item_legacy_translation_columns
Revises: 0004_backfill_public_raw_item_translation_rows
Create Date: 2026-06-27 19:20:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0005_drop_public_raw_item_legacy_translation_columns"
down_revision = "0004_backfill_public_raw_item_translation_rows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        insert into public_raw_item_translations (
          public_raw_item_id,
          language,
          summary,
          full_translation,
          status,
          is_truncated,
          source_chars,
          translation_chars,
          created_at,
          updated_at
        )
        select
          id,
          'zh-Hant',
          summary_zh,
          full_translation_zh,
          null,
          lower(coalesce(scrub_metadata ->> 'full_translation_zh_truncated', 'false')) = 'true',
          source_text_chars,
          case when full_translation_zh is not null then char_length(full_translation_zh) else null end,
          created_at,
          updated_at
        from public_raw_items
        where summary_zh is not null
           or full_translation_zh is not null
        on conflict (public_raw_item_id, language) do update
        set summary = coalesce(public_raw_item_translations.summary, excluded.summary),
            full_translation = coalesce(public_raw_item_translations.full_translation, excluded.full_translation),
            status = coalesce(public_raw_item_translations.status, excluded.status),
            is_truncated = public_raw_item_translations.is_truncated or excluded.is_truncated,
            source_chars = coalesce(public_raw_item_translations.source_chars, excluded.source_chars),
            translation_chars = coalesce(public_raw_item_translations.translation_chars, excluded.translation_chars),
            updated_at = greatest(public_raw_item_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute(
        """
        insert into public_raw_item_translations (
          public_raw_item_id,
          language,
          summary,
          full_translation,
          status,
          is_truncated,
          source_chars,
          translation_chars,
          created_at,
          updated_at
        )
        select
          id,
          'en',
          summary_en,
          full_translation_en,
          null,
          lower(coalesce(scrub_metadata ->> 'full_translation_en_truncated', 'false')) = 'true',
          source_text_chars,
          case when full_translation_en is not null then char_length(full_translation_en) else null end,
          created_at,
          updated_at
        from public_raw_items
        where summary_en is not null
           or full_translation_en is not null
        on conflict (public_raw_item_id, language) do update
        set summary = coalesce(public_raw_item_translations.summary, excluded.summary),
            full_translation = coalesce(public_raw_item_translations.full_translation, excluded.full_translation),
            status = coalesce(public_raw_item_translations.status, excluded.status),
            is_truncated = public_raw_item_translations.is_truncated or excluded.is_truncated,
            source_chars = coalesce(public_raw_item_translations.source_chars, excluded.source_chars),
            translation_chars = coalesce(public_raw_item_translations.translation_chars, excluded.translation_chars),
            updated_at = greatest(public_raw_item_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute("alter table public_raw_items drop column if exists summary_zh")
    op.execute("alter table public_raw_items drop column if exists summary_en")
    op.execute("alter table public_raw_items drop column if exists full_translation_zh")
    op.execute("alter table public_raw_items drop column if exists full_translation_en")


def downgrade() -> None:
    op.execute("alter table public_raw_items add column if not exists summary_zh text")
    op.execute("alter table public_raw_items add column if not exists summary_en text")
    op.execute("alter table public_raw_items add column if not exists full_translation_zh text")
    op.execute("alter table public_raw_items add column if not exists full_translation_en text")
