"""drop raw item legacy translation columns

Revision ID: 0020_drop_raw_item_tr_legacy
Revises: 0019_raw_item_tr_backfill
Create Date: 2026-06-27 19:20:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0020_drop_raw_item_tr_legacy"
down_revision = "0019_raw_item_tr_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        insert into raw_item_translations (
          raw_item_id,
          language,
          summary,
          full_translation,
          status,
          model_provider,
          model,
          error,
          input_chars,
          updated_at,
          created_at
        )
        select
          id,
          'zh-Hant',
          summary_zh,
          full_translation_zh,
          case
            when translation_status = 'partial_completed' then 'completed'
            when translation_status in ('completed', 'completed_truncated', 'skipped', 'failed') then translation_status
            else 'completed'
          end,
          translation_model_provider,
          translation_model,
          translation_error,
          translation_input_chars,
          coalesce(translation_updated_at, updated_at, now()),
          created_at
        from raw_items
        where summary_zh is not null
           or full_translation_zh is not null
        on conflict (raw_item_id, language) do update
        set summary = coalesce(raw_item_translations.summary, excluded.summary),
            full_translation = coalesce(raw_item_translations.full_translation, excluded.full_translation),
            status = coalesce(raw_item_translations.status, excluded.status),
            model_provider = coalesce(raw_item_translations.model_provider, excluded.model_provider),
            model = coalesce(raw_item_translations.model, excluded.model),
            error = coalesce(raw_item_translations.error, excluded.error),
            input_chars = coalesce(raw_item_translations.input_chars, excluded.input_chars),
            updated_at = greatest(raw_item_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute(
        """
        insert into raw_item_translations (
          raw_item_id,
          language,
          summary,
          full_translation,
          status,
          model_provider,
          model,
          error,
          input_chars,
          updated_at,
          created_at
        )
        select
          id,
          'en',
          summary_en,
          full_translation_en,
          case
            when translation_status = 'partial_completed' then 'completed'
            when translation_status in ('completed', 'completed_truncated', 'skipped', 'failed') then translation_status
            else 'completed'
          end,
          translation_model_provider,
          translation_model,
          translation_error,
          translation_input_chars,
          coalesce(translation_updated_at, updated_at, now()),
          created_at
        from raw_items
        where summary_en is not null
           or full_translation_en is not null
        on conflict (raw_item_id, language) do update
        set summary = coalesce(raw_item_translations.summary, excluded.summary),
            full_translation = coalesce(raw_item_translations.full_translation, excluded.full_translation),
            status = coalesce(raw_item_translations.status, excluded.status),
            model_provider = coalesce(raw_item_translations.model_provider, excluded.model_provider),
            model = coalesce(raw_item_translations.model, excluded.model),
            error = coalesce(raw_item_translations.error, excluded.error),
            input_chars = coalesce(raw_item_translations.input_chars, excluded.input_chars),
            updated_at = greatest(raw_item_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute("alter table raw_items drop column if exists summary_zh")
    op.execute("alter table raw_items drop column if exists summary_en")
    op.execute("alter table raw_items drop column if exists full_translation_zh")
    op.execute("alter table raw_items drop column if exists full_translation_en")


def downgrade() -> None:
    op.execute("alter table raw_items add column if not exists summary_zh text")
    op.execute("alter table raw_items add column if not exists summary_en text")
    op.execute("alter table raw_items add column if not exists full_translation_zh text")
    op.execute("alter table raw_items add column if not exists full_translation_en text")
