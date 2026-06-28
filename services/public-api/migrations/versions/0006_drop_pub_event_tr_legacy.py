"""drop public event legacy translation columns

Revision ID: 0006_drop_pub_event_tr_legacy
Revises: 0005_drop_pub_raw_item_tr_legacy
Create Date: 2026-06-27 20:10:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0006_drop_pub_event_tr_legacy"
down_revision = "0005_drop_pub_raw_item_tr_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        insert into public_events_translations (
          public_event_id,
          language,
          title,
          summary,
          created_at,
          updated_at
        )
        select
          id,
          'zh-Hant',
          public_title_zh,
          public_summary_zh,
          created_at,
          updated_at
        from public_events
        where public_title_zh is not null
           or public_summary_zh is not null
        on conflict (public_event_id, language) do update
        set title = coalesce(public_events_translations.title, excluded.title),
            summary = coalesce(public_events_translations.summary, excluded.summary),
            updated_at = greatest(public_events_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute(
        """
        insert into public_events_translations (
          public_event_id,
          language,
          title,
          summary,
          created_at,
          updated_at
        )
        select
          id,
          'en',
          public_title_en,
          public_summary_en,
          created_at,
          updated_at
        from public_events
        where public_title_en is not null
           or public_summary_en is not null
        on conflict (public_event_id, language) do update
        set title = coalesce(public_events_translations.title, excluded.title),
            summary = coalesce(public_events_translations.summary, excluded.summary),
            updated_at = greatest(public_events_translations.updated_at, excluded.updated_at)
        """
    )
    op.execute("alter table public_events drop column if exists public_title_zh")
    op.execute("alter table public_events drop column if exists public_summary_zh")
    op.execute("alter table public_events drop column if exists public_title_en")
    op.execute("alter table public_events drop column if exists public_summary_en")


def downgrade() -> None:
    op.execute("alter table public_events add column if not exists public_title_zh text")
    op.execute("alter table public_events add column if not exists public_summary_zh text")
    op.execute("alter table public_events add column if not exists public_title_en text")
    op.execute("alter table public_events add column if not exists public_summary_en text")
