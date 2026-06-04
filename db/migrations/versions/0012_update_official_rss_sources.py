"""update official rss and html polling sources

Revision ID: 0012_update_official_rss_sources
Revises: 0011_event_route_decisions
Create Date: 2026-06-03 23:25:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0012_update_official_rss_sources"
down_revision = "0011_event_route_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.centcom.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=9&Site=945&max=20',
            source_type = 'rss',
            stance = 'US Central Command official press release RSS endpoint.',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15,"user_agent":"Mozilla/5.0 (compatible; XAUUSDEventRadar/1.0)"}'::jsonb,
            updated_at = now()
        where name = 'CENTCOM Press Releases'
          and source_group = 'us_military'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.state.gov/rss-feed/press-releases/feed/',
            source_type = 'rss',
            stance = 'US State Department official press releases RSS feed.',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15}'::jsonb,
            updated_at = now()
        where name = 'US State Department RSS'
          and source_group = 'us_diplomacy'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.tasnimnews.ir/en/rss',
            source_type = 'rss',
            source_config = source_config || '{"poll_interval_seconds":60,"request_timeout_seconds":30}'::jsonb,
            updated_at = now()
        where name = 'Tasnim RSS'
          and source_group = 'iran_irgc_adjacent'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.presstv.ir/rss/rss-101.xml',
            source_type = 'rss',
            stance = 'Press TV Iran official RSS feed.',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15}'::jsonb,
            updated_at = now()
        where name = 'Press TV Website'
          and source_group = 'iran_external_media'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set source_type = 'html_polling',
            source_config = '{
              "poll_interval_seconds": 180,
              "request_timeout_seconds": 15,
              "list_selector": ".content--2col__body > div",
              "title_selector": "h3.featured-stories__headline a",
              "url_selector": "h3.featured-stories__headline a",
              "published_selector": "time",
              "published_attr": "datetime"
            }'::jsonb,
            updated_at = now()
        where name = 'US Treasury Press Releases'
          and source_group = 'us_sanctions'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set source_type = 'html_polling',
            source_config = '{
              "poll_interval_seconds": 300,
              "request_timeout_seconds": 15,
              "list_selector": ".search-result.views-row",
              "title_selector": "a[href^=\\"/recent-actions/\\"]",
              "url_selector": "a[href^=\\"/recent-actions/\\"]",
              "published_selector": ".font-sans-2xs",
              "published_regex": "^([A-Za-z]+ \\\\d{2}, \\\\d{4})"
            }'::jsonb,
            updated_at = now()
        where name = 'OFAC Recent Actions'
          and source_group = 'us_sanctions'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://sepahnews.ir/',
            source_config = source_config || '{"poll_interval_seconds":120,"request_timeout_seconds":15,"requires_parser_config":true,"keyword_language":"fa"}'::jsonb,
            updated_at = now()
        where name = 'Sepah News'
          and source_group = 'iran_irgc_official'
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.centcom.mil/MEDIA/PRESS-RELEASES/',
            source_type = 'html_polling',
            stance = 'US Central Command official press release page.',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15,"requires_parser_config":true}'::jsonb,
            updated_at = now()
        where name = 'CENTCOM Press Releases'
          and source_group = 'us_military'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.state.gov/rss-feeds/',
            source_type = 'html_polling',
            stance = 'US State Department official RSS/feed index; parser configuration required per feed.',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15,"requires_parser_config":true}'::jsonb,
            updated_at = now()
        where name = 'US State Department RSS'
          and source_group = 'us_diplomacy'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.tasnimnews.com/en/rss',
            source_type = 'rss',
            source_config = '{"poll_interval_seconds":60,"request_timeout_seconds":15}'::jsonb,
            updated_at = now()
        where name = 'Tasnim RSS'
          and source_group = 'iran_irgc_adjacent'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.presstv.ir/',
            source_type = 'html_polling',
            stance = 'Press TV web source; parser configuration required.',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15,"requires_parser_config":true}'::jsonb,
            updated_at = now()
        where name = 'Press TV Website'
          and source_group = 'iran_external_media'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set source_config = '{"poll_interval_seconds":180,"request_timeout_seconds":15,"requires_parser_config":true}'::jsonb,
            updated_at = now()
        where name = 'US Treasury Press Releases'
          and source_group = 'us_sanctions'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set source_config = '{"poll_interval_seconds":300,"request_timeout_seconds":15,"requires_parser_config":true}'::jsonb,
            updated_at = now()
        where name = 'OFAC Recent Actions'
          and source_group = 'us_sanctions'
        """
    )
    bind.exec_driver_sql(
        """
        update sources
        set handle_or_url = 'https://www.sepahnews.com/',
            source_config = '{"poll_interval_seconds":120,"request_timeout_seconds":15,"requires_parser_config":true,"keyword_language":"fa"}'::jsonb,
            updated_at = now()
        where name = 'Sepah News'
          and source_group = 'iran_irgc_official'
        """
    )
