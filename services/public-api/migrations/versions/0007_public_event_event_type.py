"""add event_type column to public_events

Revision ID: 0007_public_event_event_type
Revises: 0006_drop_pub_event_tr_legacy
Create Date: 2026-07-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0007_public_event_event_type"
down_revision = "0006_drop_pub_event_tr_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public_events add column if not exists event_type text")
    op.execute("create index if not exists public_events_event_type_idx on public_events (event_type)")


def downgrade() -> None:
    op.execute("drop index if exists public_events_event_type_idx")
    op.execute("alter table public_events drop column if exists event_type")
