"""add public raw item sync state

Revision ID: 0018_public_raw_item_sync_state
Revises: 0017_public_outbox_translations
Create Date: 2026-06-13 14:05:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0018_public_raw_item_sync_state"
down_revision = "0017_public_outbox_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table public_raw_item_sync_state (
          raw_item_id uuid primary key references raw_items(id) on delete cascade,
          publish_status text not null default 'pending',
          retry_count integer not null default 0,
          last_error text,
          next_retry_at timestamptz,
          locked_by text,
          locked_at timestamptz,
          last_payload_hash text,
          provider_response jsonb,
          external_web_id text,
          synced_at timestamptz,
          source_updated_at timestamptz not null,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint public_raw_item_sync_state_status_check check (
            publish_status in ('pending', 'sending', 'sent', 'failed', 'skipped', 'retry')
          ),
          constraint public_raw_item_sync_state_retry_count_check check (retry_count >= 0),
          constraint public_raw_item_sync_state_provider_response_object_check check (
            provider_response is null or jsonb_typeof(provider_response) = 'object'
          )
        )
        """
    )
    op.execute(
        """
        create index public_raw_item_sync_state_claim_idx
          on public_raw_item_sync_state (publish_status, next_retry_at, source_updated_at)
        """
    )
    op.execute(
        """
        create index public_raw_item_sync_state_synced_idx
          on public_raw_item_sync_state (synced_at desc)
        """
    )
    op.execute(
        """
        create trigger trg_public_raw_item_sync_state_updated_at
        before update on public_raw_item_sync_state
        for each row execute function set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_public_raw_item_sync_state_updated_at on public_raw_item_sync_state")
    op.execute("drop index if exists public_raw_item_sync_state_synced_idx")
    op.execute("drop index if exists public_raw_item_sync_state_claim_idx")
    op.execute("drop table if exists public_raw_item_sync_state")
