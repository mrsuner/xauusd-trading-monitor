"""add public outbox

Revision ID: 0010_public_outbox
Revises: 0009_taxonomy_dictionaries
Create Date: 2026-06-01 13:30:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0010_public_outbox"
down_revision = "0009_taxonomy_dictionaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table public_outbox (
          id uuid primary key default gen_random_uuid(),
          event_id uuid not null references events(id) on delete cascade,
          public_title_zh text,
          public_summary_zh text,
          public_title_en text,
          public_summary_en text,
          public_source_links jsonb not null default '[]'::jsonb,
          severity text not null default 'B',
          relevance_score smallint,
          confirmation_state text,
          topic_tags text[] not null default '{}'::text[],
          approved_for_public boolean not null default false,
          publish_status_web text not null default 'pending',
          publish_status_telegram text not null default 'pending',
          publish_status_x text not null default 'pending',
          retry_count_web integer not null default 0,
          retry_count_telegram integer not null default 0,
          retry_count_x integer not null default 0,
          last_error_web text,
          last_error_telegram text,
          last_error_x text,
          provider_response_telegram jsonb,
          provider_response_x jsonb,
          provider_response_web jsonb,
          external_telegram_message_id text,
          external_x_post_id text,
          external_web_id text,
          next_retry_telegram_at timestamptz,
          next_retry_x_at timestamptz,
          next_retry_web_at timestamptz,
          locked_by_telegram text,
          locked_at_telegram timestamptz,
          locked_by_x text,
          locked_at_x timestamptz,
          locked_by_web text,
          locked_at_web timestamptz,
          generated_at timestamptz not null default now(),
          published_web_at timestamptz,
          published_telegram_at timestamptz,
          published_x_at timestamptz,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint public_outbox_severity_check check (
            severity in ('S', 'A', 'B', 'C')
          ),
          constraint public_outbox_relevance_score_check check (
            relevance_score is null or relevance_score between 0 and 100
          ),
          constraint public_outbox_confirmation_state_check check (
            confirmation_state is null or confirmation_state in (
              'unconfirmed',
              'partially_confirmed',
              'confirmed',
              'contradicted'
            )
          ),
          constraint public_outbox_source_links_array_check check (
            jsonb_typeof(public_source_links) = 'array'
          ),
          constraint public_outbox_publish_status_web_check check (
            publish_status_web in ('pending', 'sending', 'sent', 'failed', 'skipped', 'retry')
          ),
          constraint public_outbox_publish_status_telegram_check check (
            publish_status_telegram in ('pending', 'sending', 'sent', 'failed', 'skipped', 'retry')
          ),
          constraint public_outbox_publish_status_x_check check (
            publish_status_x in ('pending', 'sending', 'sent', 'failed', 'skipped', 'retry')
          ),
          constraint public_outbox_retry_count_web_check check (retry_count_web >= 0),
          constraint public_outbox_retry_count_telegram_check check (retry_count_telegram >= 0),
          constraint public_outbox_retry_count_x_check check (retry_count_x >= 0)
        )
        """
    )

    op.execute("create unique index public_outbox_event_uidx on public_outbox (event_id)")
    op.execute(
        """
        create index public_outbox_telegram_claim_idx
          on public_outbox (publish_status_telegram, next_retry_telegram_at, generated_at)
          where approved_for_public = true
        """
    )
    op.execute(
        """
        create index public_outbox_x_claim_idx
          on public_outbox (publish_status_x, next_retry_x_at, generated_at)
          where approved_for_public = true
        """
    )
    op.execute(
        """
        create index public_outbox_web_claim_idx
          on public_outbox (publish_status_web, next_retry_web_at, generated_at)
          where approved_for_public = true
        """
    )
    op.execute("create index public_outbox_generated_idx on public_outbox (generated_at desc)")
    op.execute("create index public_outbox_topic_tags_gin_idx on public_outbox using gin (topic_tags)")
    op.execute(
        """
        create trigger trg_public_outbox_updated_at
        before update on public_outbox
        for each row execute function set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_public_outbox_updated_at on public_outbox")
    op.execute("drop index if exists public_outbox_topic_tags_gin_idx")
    op.execute("drop index if exists public_outbox_generated_idx")
    op.execute("drop index if exists public_outbox_web_claim_idx")
    op.execute("drop index if exists public_outbox_x_claim_idx")
    op.execute("drop index if exists public_outbox_telegram_claim_idx")
    op.execute("drop index if exists public_outbox_event_uidx")
    op.execute("drop table if exists public_outbox")
