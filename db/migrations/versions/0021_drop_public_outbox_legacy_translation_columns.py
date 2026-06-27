"""drop public outbox legacy translation columns

Revision ID: 0021_drop_public_outbox_legacy_translation_columns
Revises: 0020_drop_raw_item_legacy_translation_columns
Create Date: 2026-06-27 20:10:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0021_drop_public_outbox_legacy_translation_columns"
down_revision = "0020_drop_raw_item_legacy_translation_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        insert into public_outbox_translations (
          public_outbox_id,
          language,
          title,
          summary,
          status,
          created_at,
          updated_at
        )
        select
          id,
          'zh-Hant',
          public_title_zh,
          public_summary_zh,
          'approved',
          created_at,
          updated_at
        from public_outbox
        where public_title_zh is not null
           or public_summary_zh is not null
        on conflict (public_outbox_id, language) do update
        set title = coalesce(public_outbox_translations.title, excluded.title),
            summary = coalesce(public_outbox_translations.summary, excluded.summary),
            status = public_outbox_translations.status,
            updated_at = greatest(public_outbox_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute(
        """
        insert into public_outbox_translations (
          public_outbox_id,
          language,
          title,
          summary,
          status,
          created_at,
          updated_at
        )
        select
          id,
          'en',
          public_title_en,
          public_summary_en,
          'approved',
          created_at,
          updated_at
        from public_outbox
        where public_title_en is not null
           or public_summary_en is not null
        on conflict (public_outbox_id, language) do update
        set title = coalesce(public_outbox_translations.title, excluded.title),
            summary = coalesce(public_outbox_translations.summary, excluded.summary),
            status = public_outbox_translations.status,
            updated_at = greatest(public_outbox_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute("alter table public_outbox drop column if exists public_title_zh")
    op.execute("alter table public_outbox drop column if exists public_summary_zh")
    op.execute("alter table public_outbox drop column if exists public_title_en")
    op.execute("alter table public_outbox drop column if exists public_summary_en")


def downgrade() -> None:
    op.execute("alter table public_outbox add column if not exists public_title_zh text")
    op.execute("alter table public_outbox add column if not exists public_summary_zh text")
    op.execute("alter table public_outbox add column if not exists public_title_en text")
    op.execute("alter table public_outbox add column if not exists public_summary_en text")
