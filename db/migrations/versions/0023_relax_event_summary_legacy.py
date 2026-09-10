"""relax legacy event summary requirement for translation cutover

Revision ID: 0023_relax_event_summary_legacy
Revises: 0022_event_translations
Create Date: 2026-09-10 00:10:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0023_relax_event_summary_legacy"
down_revision = "0022_event_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table events alter column summary_zh drop not null")


def downgrade() -> None:
    op.execute(
        """
        update events e
        set summary_zh = et.summary
        from event_translations et
        where et.event_id = e.id
          and et.language = 'zh-Hant'
          and e.summary_zh is null
        """
    )
    op.execute("alter table events alter column summary_zh set not null")
