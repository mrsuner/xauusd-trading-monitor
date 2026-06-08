"""add public event translations

Revision ID: 0002_public_event_translations
Revises: 0001_public_events
Create Date: 2026-06-08 21:10:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0002_public_event_translations"
down_revision = "0001_public_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pg_trgm")
    op.execute(
        """
        create table public_events_translations (
          id uuid primary key default gen_random_uuid(),
          public_event_id uuid not null references public_events(id) on delete cascade,
          language text not null,
          title text,
          summary text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint public_events_translations_language_check check (btrim(language) <> ''),
          constraint public_events_translations_content_check check (
            title is not null or summary is not null
          ),
          constraint public_events_translations_event_language_key unique (public_event_id, language)
        )
        """
    )
    op.execute(
        """
        create index public_events_translations_language_idx
          on public_events_translations (language)
        """
    )
    op.execute(
        """
        create index public_events_translations_updated_at_idx
          on public_events_translations (updated_at desc)
        """
    )
    op.execute(
        """
        create index public_events_translations_title_trgm_idx
          on public_events_translations using gin (title gin_trgm_ops)
        """
    )
    op.execute(
        """
        create index public_events_translations_summary_trgm_idx
          on public_events_translations using gin (summary gin_trgm_ops)
        """
    )
    op.execute(
        """
        create trigger trg_public_events_translations_updated_at
        before update on public_events_translations
        for each row execute function set_updated_at()
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
          'zh-Hant',
          public_title_zh,
          public_summary_zh,
          created_at,
          updated_at
        from public_events
        where public_title_zh is not null
           or public_summary_zh is not null
        on conflict (public_event_id, language) do update
        set title = excluded.title,
            summary = excluded.summary,
            updated_at = now()
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
        set title = excluded.title,
            summary = excluded.summary,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_public_events_translations_updated_at on public_events_translations")
    op.execute("drop index if exists public_events_translations_summary_trgm_idx")
    op.execute("drop index if exists public_events_translations_title_trgm_idx")
    op.execute("drop index if exists public_events_translations_updated_at_idx")
    op.execute("drop index if exists public_events_translations_language_idx")
    op.execute("drop table if exists public_events_translations")
