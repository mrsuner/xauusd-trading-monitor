"""add partial raw item translation status

Revision ID: 0015_raw_item_partial_translation_status
Revises: 0014_raw_item_translations
Create Date: 2026-06-06 18:20:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0015_raw_item_partial_translation_status"
down_revision = "0014_raw_item_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table raw_items drop constraint if exists raw_items_translation_status_check")
    op.execute(
        """
        alter table raw_items add constraint raw_items_translation_status_check
          check (
            translation_status in (
              'pending',
              'completed',
              'completed_truncated',
              'partial_completed',
              'skipped',
              'failed'
            )
          )
        """
    )


def downgrade() -> None:
    op.execute("alter table raw_items drop constraint if exists raw_items_translation_status_check")
    op.execute(
        """
        update raw_items
        set translation_status = 'completed'
        where translation_status = 'partial_completed'
        """
    )
    op.execute(
        """
        alter table raw_items add constraint raw_items_translation_status_check
          check (
            translation_status in (
              'pending',
              'completed',
              'completed_truncated',
              'skipped',
              'failed'
            )
          )
        """
    )
