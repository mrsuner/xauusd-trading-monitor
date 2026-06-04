"""tune rss source fetching

Revision ID: 0013_tune_rss_source_fetching
Revises: 0012_update_official_rss_sources
Create Date: 2026-06-03 23:35:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0013_tune_rss_source_fetching"
down_revision = "0012_update_official_rss_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        update sources
        set source_config = source_config || '{"user_agent":"Mozilla/5.0 (compatible; XAUUSDEventRadar/1.0)"}'::jsonb,
            updated_at = now()
        where name = 'US State Department RSS'
          and source_group = 'us_diplomacy'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set source_config = source_config || '{"request_timeout_seconds":30}'::jsonb,
            updated_at = now()
        where name = 'Tasnim RSS'
          and source_group = 'iran_irgc_adjacent'
        """
    )
    bind.exec_driver_sql(
        """
        update source_health h
        set last_error_at = null,
            last_error_message = null,
            updated_at = now()
        from sources s
        where s.id = h.source_id
          and s.name in (
            'CENTCOM Press Releases',
            'US State Department RSS',
            'Press TV Website',
            'US Treasury Press Releases',
            'OFAC Recent Actions',
            'Tasnim RSS'
          )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        update sources
        set source_config = source_config - 'user_agent',
            updated_at = now()
        where name = 'US State Department RSS'
          and source_group = 'us_diplomacy'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set source_config = source_config || '{"request_timeout_seconds":15}'::jsonb,
            updated_at = now()
        where name = 'Tasnim RSS'
          and source_group = 'iran_irgc_adjacent'
        """
    )
