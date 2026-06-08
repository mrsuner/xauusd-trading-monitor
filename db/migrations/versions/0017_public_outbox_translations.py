"""add public outbox translations

Revision ID: 0017_public_outbox_translations
Revises: 0016_tickbase_anomaly_ingest
Create Date: 2026-06-08 11:30:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0017_public_outbox_translations"
down_revision = "0016_tickbase_anomaly_ingest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table public_outbox_translations (
          id uuid primary key default gen_random_uuid(),
          public_outbox_id uuid not null references public_outbox(id) on delete cascade,
          language text not null,
          title text,
          summary text,
          status text not null default 'approved',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint public_outbox_translations_language_check check (btrim(language) <> ''),
          constraint public_outbox_translations_status_check check (
            status in ('draft', 'approved', 'skipped', 'failed')
          ),
          constraint public_outbox_translations_content_check check (
            title is not null or summary is not null or status in ('skipped', 'failed')
          ),
          constraint public_outbox_translations_outbox_language_key unique (public_outbox_id, language)
        )
        """
    )
    op.execute(
        """
        create index public_outbox_translations_language_idx
          on public_outbox_translations (language)
        """
    )
    op.execute(
        """
        create index public_outbox_translations_status_idx
          on public_outbox_translations (status)
        """
    )
    op.execute(
        """
        create index public_outbox_translations_updated_at_idx
          on public_outbox_translations (updated_at desc)
        """
    )
    op.execute(
        """
        create index public_outbox_translations_title_trgm_idx
          on public_outbox_translations using gin (title gin_trgm_ops)
        """
    )
    op.execute(
        """
        create index public_outbox_translations_summary_trgm_idx
          on public_outbox_translations using gin (summary gin_trgm_ops)
        """
    )
    op.execute(
        """
        create trigger trg_public_outbox_translations_updated_at
        before update on public_outbox_translations
        for each row execute function set_updated_at()
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
        set title = excluded.title,
            summary = excluded.summary,
            status = excluded.status,
            updated_at = now()
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
        set title = excluded.title,
            summary = excluded.summary,
            status = excluded.status,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_public_outbox_translations_updated_at on public_outbox_translations")
    op.execute("drop index if exists public_outbox_translations_summary_trgm_idx")
    op.execute("drop index if exists public_outbox_translations_title_trgm_idx")
    op.execute("drop index if exists public_outbox_translations_updated_at_idx")
    op.execute("drop index if exists public_outbox_translations_status_idx")
    op.execute("drop index if exists public_outbox_translations_language_idx")
    op.execute("drop table if exists public_outbox_translations")
