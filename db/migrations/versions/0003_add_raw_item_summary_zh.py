"""add raw item summary zh

Revision ID: 0003_add_raw_item_summary_zh
Revises: 0002_seed_sources
Create Date: 2026-05-31 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0003_add_raw_item_summary_zh"
down_revision = "0002_seed_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table raw_items add column if not exists summary_zh text")


def downgrade() -> None:
    op.execute("alter table raw_items drop column if exists summary_zh")
