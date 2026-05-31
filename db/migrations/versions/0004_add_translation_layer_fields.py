"""add translation layer fields

Revision ID: 0004_translation_fields
Revises: 0003_add_raw_item_summary_zh
Create Date: 2026-05-31 16:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0004_translation_fields"
down_revision = "0003_add_raw_item_summary_zh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table sources add column if not exists translation_policy text not null default 'full'")
    op.execute("alter table sources add column if not exists translation_priority text not null default 'normal'")
    op.execute("alter table sources add column if not exists translation_max_chars integer")
    op.execute("alter table sources add column if not exists always_full_translate boolean not null default false")

    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_translation_policy_check'
          ) then
            alter table sources add constraint sources_translation_policy_check
              check (translation_policy in ('disabled', 'summary_only', 'full'));
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_translation_priority_check'
          ) then
            alter table sources add constraint sources_translation_priority_check
              check (translation_priority in ('normal', 'high'));
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_translation_max_chars_check'
          ) then
            alter table sources add constraint sources_translation_max_chars_check
              check (translation_max_chars is null or translation_max_chars >= 0);
          end if;
        end $$;
        """
    )

    op.execute(
        """
        update sources
        set translation_priority = 'high',
            always_full_translate = true,
            translation_max_chars = coalesce(translation_max_chars, 100000)
        where priority in ('P0', 'P1')
        """
    )

    op.execute("alter table raw_items add column if not exists summary_en text")
    op.execute("alter table raw_items add column if not exists full_translation_zh text")
    op.execute("alter table raw_items add column if not exists full_translation_en text")
    op.execute("alter table raw_items add column if not exists translation_status text not null default 'pending'")
    op.execute("alter table raw_items add column if not exists translation_model_provider text")
    op.execute("alter table raw_items add column if not exists translation_model text")
    op.execute("alter table raw_items add column if not exists translation_error text")
    op.execute("alter table raw_items add column if not exists translation_input_chars integer")
    op.execute("alter table raw_items add column if not exists translation_updated_at timestamptz")

    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'raw_items_translation_status_check'
          ) then
            alter table raw_items add constraint raw_items_translation_status_check
              check (
                translation_status in (
                  'pending',
                  'completed',
                  'completed_truncated',
                  'skipped',
                  'failed'
                )
              );
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'raw_items_translation_input_chars_check'
          ) then
            alter table raw_items add constraint raw_items_translation_input_chars_check
              check (translation_input_chars is null or translation_input_chars >= 0);
          end if;
        end $$;
        """
    )


def downgrade() -> None:
    op.execute("alter table raw_items drop constraint if exists raw_items_translation_input_chars_check")
    op.execute("alter table raw_items drop constraint if exists raw_items_translation_status_check")
    op.execute("alter table raw_items drop column if exists translation_updated_at")
    op.execute("alter table raw_items drop column if exists translation_input_chars")
    op.execute("alter table raw_items drop column if exists translation_error")
    op.execute("alter table raw_items drop column if exists translation_model")
    op.execute("alter table raw_items drop column if exists translation_model_provider")
    op.execute("alter table raw_items drop column if exists translation_status")
    op.execute("alter table raw_items drop column if exists full_translation_en")
    op.execute("alter table raw_items drop column if exists full_translation_zh")
    op.execute("alter table raw_items drop column if exists summary_en")

    op.execute("alter table sources drop constraint if exists sources_translation_max_chars_check")
    op.execute("alter table sources drop constraint if exists sources_translation_priority_check")
    op.execute("alter table sources drop constraint if exists sources_translation_policy_check")
    op.execute("alter table sources drop column if exists always_full_translate")
    op.execute("alter table sources drop column if exists translation_max_chars")
    op.execute("alter table sources drop column if exists translation_priority")
    op.execute("alter table sources drop column if exists translation_policy")
