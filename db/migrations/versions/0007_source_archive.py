"""add source archive state

Revision ID: 0007_source_archive
Revises: 0006_ai_model_calls
Create Date: 2026-05-31 23:30:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0007_source_archive"
down_revision = "0006_ai_model_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table sources add column if not exists archived_at timestamptz")
    op.execute("create index if not exists sources_archived_at_idx on sources (archived_at)")


def downgrade() -> None:
    op.execute("drop index if exists sources_archived_at_idx")
    op.execute("alter table sources drop column if exists archived_at")
