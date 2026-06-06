"""add raw item translations

Revision ID: 0014_raw_item_translations
Revises: 0013_tune_rss_source_fetching
Create Date: 2026-06-06 15:45:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0014_raw_item_translations"
down_revision = "0013_tune_rss_source_fetching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists raw_item_translations (
          id uuid primary key default gen_random_uuid(),
          raw_item_id uuid not null references raw_items(id) on delete cascade,
          language text not null,
          summary text,
          full_translation text,
          status text not null default 'pending',
          model_provider text,
          model text,
          error text,
          input_chars integer,
          updated_at timestamptz not null default now(),
          created_at timestamptz not null default now(),

          constraint raw_item_translations_raw_item_language_key unique (raw_item_id, language),
          constraint raw_item_translations_language_check check (btrim(language) <> ''),
          constraint raw_item_translations_status_check check (
            status in (
              'pending',
              'completed',
              'completed_truncated',
              'skipped',
              'failed'
            )
          ),
          constraint raw_item_translations_input_chars_check check (
            input_chars is null or input_chars >= 0
          )
        )
        """
    )
    op.execute(
        """
        create index if not exists raw_item_translations_language_idx
          on raw_item_translations (language)
        """
    )
    op.execute(
        """
        create index if not exists raw_item_translations_status_idx
          on raw_item_translations (status)
        """
    )
    op.execute(
        """
        create index if not exists raw_item_translations_updated_at_idx
          on raw_item_translations (updated_at desc)
        """
    )
    op.execute(
        """
        create index if not exists raw_item_translations_summary_trgm_idx
          on raw_item_translations using gin (summary gin_trgm_ops)
        """
    )
    op.execute(
        """
        create index if not exists raw_item_translations_full_translation_trgm_idx
          on raw_item_translations using gin (full_translation gin_trgm_ops)
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
          'zh-Hant',
          summary_zh,
          full_translation_zh,
          translation_status,
          translation_model_provider,
          translation_model,
          translation_error,
          translation_input_chars,
          coalesce(translation_updated_at, updated_at),
          created_at
        from raw_items
        where summary_zh is not null
           or full_translation_zh is not null
           or translation_status in ('completed', 'completed_truncated', 'skipped', 'failed')
        on conflict (raw_item_id, language) do update
        set summary = excluded.summary,
            full_translation = excluded.full_translation,
            status = excluded.status,
            model_provider = excluded.model_provider,
            model = excluded.model,
            error = excluded.error,
            input_chars = excluded.input_chars,
            updated_at = excluded.updated_at
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
          translation_status,
          translation_model_provider,
          translation_model,
          translation_error,
          translation_input_chars,
          coalesce(translation_updated_at, updated_at),
          created_at
        from raw_items
        where summary_en is not null
           or full_translation_en is not null
           or translation_status in ('completed', 'completed_truncated', 'skipped', 'failed')
        on conflict (raw_item_id, language) do update
        set summary = excluded.summary,
            full_translation = excluded.full_translation,
            status = excluded.status,
            model_provider = excluded.model_provider,
            model = excluded.model,
            error = excluded.error,
            input_chars = excluded.input_chars,
            updated_at = excluded.updated_at
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists raw_item_translations")
