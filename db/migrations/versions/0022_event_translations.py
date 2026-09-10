"""add private event translations

Revision ID: 0022_event_translations
Revises: 0021_drop_outbox_tr_legacy
Create Date: 2026-09-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0022_event_translations"
down_revision = "0021_drop_outbox_tr_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table event_translations (
          event_id uuid not null references events(id) on delete cascade,
          language text not null,
          summary text not null,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint event_translations_pkey primary key (event_id, language),
          constraint event_translations_language_check check (btrim(language) <> ''),
          constraint event_translations_summary_check check (btrim(summary) <> '')
        )
        """
    )
    op.execute(
        """
        create index event_translations_language_idx
          on event_translations (language)
        """
    )
    op.execute(
        """
        create trigger trg_event_translations_updated_at
        before update on event_translations
        for each row execute function set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_event_translations_updated_at on event_translations")
    op.execute("drop index if exists event_translations_language_idx")
    op.execute("drop table if exists event_translations")
