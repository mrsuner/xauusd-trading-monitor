"""seed initial sources

Revision ID: 0002_seed_sources
Revises: 0001_initial_schema
Create Date: 2026-05-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0002_seed_sources"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        insert into sources (
          name,
          handle_or_url,
          source_type,
          source_group,
          official_level,
          stance,
          language,
          priority,
          reliability_score,
          latency_score,
          requires_confirmation,
          source_config
        )
        select *
        from (
          values
            (
              'Trump Truth Social Alert',
              '@TrumpTruthSocial_Alert',
              'telegram',
              'us_trump',
              'unofficial_mirror',
              'Trump Truth Social third-party mirror; fast but requires original-link confirmation.',
              'en',
              'P0',
              70::smallint,
              95::smallint,
              true,
              '{"telegram_username":"TrumpTruthSocial_Alert","backfill_hours":6}'::jsonb
            ),
            (
              'IRNA English',
              '@Irna_en',
              'telegram',
              'iran_government',
              'official',
              'Iranian government official news agency English channel.',
              'en',
              'P0',
              90::smallint,
              75::smallint,
              false,
              '{"telegram_username":"Irna_en","backfill_hours":6}'::jsonb
            ),
            (
              'Tasnim News',
              '@Tasnimnews',
              'telegram',
              'iran_irgc_adjacent',
              'semi_official',
              'Iranian semi-official outlet often treated as IRGC-linked or hardline-adjacent.',
              'fa',
              'P0',
              78::smallint,
              85::smallint,
              true,
              '{"telegram_username":"Tasnimnews","backfill_hours":6}'::jsonb
            ),
            (
              'Khamenei English',
              '@Khamenei_en',
              'telegram',
              'iran_supreme_leader',
              'official',
              'Supreme Leader office English messaging; high weight for strategic red lines.',
              'en',
              'P0',
              92::smallint,
              60::smallint,
              false,
              '{"telegram_username":"Khamenei_en","backfill_hours":12}'::jsonb
            ),
            (
              'IDF Official',
              '@idfofficial',
              'telegram',
              'israel_military',
              'official',
              'Israel Defense Forces official channel for military announcements.',
              'en',
              'P0',
              92::smallint,
              85::smallint,
              false,
              '{"telegram_username":"idfofficial","backfill_hours":6}'::jsonb
            ),
            (
              'Press TV',
              '@presstv',
              'telegram',
              'iran_external_media',
              'official',
              'Iranian state external English media; useful for fast English framing.',
              'en',
              'P1',
              78::smallint,
              82::smallint,
              true,
              '{"telegram_username":"presstv","backfill_hours":6}'::jsonb
            ),
            (
              'Mehr News English',
              '@enmehrnews',
              'telegram',
              'iran_conservative',
              'semi_official',
              'Iranian semi-official conservative outlet for internal hardline/conservative framing.',
              'en',
              'P1',
              74::smallint,
              75::smallint,
              true,
              '{"telegram_username":"enmehrnews","backfill_hours":6}'::jsonb
            ),
            (
              'Israel MFA',
              '@israelmfa',
              'telegram',
              'israel_diplomacy',
              'official',
              'Israel Ministry of Foreign Affairs official channel.',
              'en',
              'P1',
              90::smallint,
              70::smallint,
              false,
              '{"telegram_username":"israelmfa","backfill_hours":6}'::jsonb
            ),
            (
              'FinancialJuice',
              '@FinancialJuice',
              'telegram',
              'market_squawk',
              'aggregator',
              'Market squawk source for fast macro and geopolitical headlines.',
              'en',
              'P1',
              66::smallint,
              90::smallint,
              true,
              '{"telegram_username":"FinancialJuice","backfill_hours":3}'::jsonb
            ),
            (
              'Middle East Spectator',
              '@Middle_East_Spectator',
              'telegram',
              'osint_aggregator',
              'aggregator',
              'Middle East aggregator with explicit regional stance; early hint source only.',
              'en',
              'P2',
              52::smallint,
              90::smallint,
              true,
              '{"telegram_username":"Middle_East_Spectator","backfill_hours":3}'::jsonb
            ),
            (
              'OSINTdefender',
              '@OSINTdefender',
              'telegram',
              'osint_aggregator',
              'aggregator',
              'OSINT conflict monitor; useful for early military hints but requires confirmation.',
              'en',
              'P2',
              55::smallint,
              88::smallint,
              true,
              '{"telegram_username":"OSINTdefender","backfill_hours":3}'::jsonb
            ),
            (
              'Federal Reserve RSS',
              'https://www.federalreserve.gov/feeds/press_all.xml',
              'rss',
              'us_fed',
              'official',
              'Federal Reserve official RSS feed.',
              'en',
              'P0',
              95::smallint,
              65::smallint,
              false,
              '{"poll_interval_seconds":120,"request_timeout_seconds":15,"timezone_hint":"America/New_York"}'::jsonb
            ),
            (
              'CENTCOM Press Releases',
              'https://www.centcom.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=9&Site=945&max=20',
              'rss',
              'us_military',
              'official',
              'US Central Command official press release RSS endpoint.',
              'en',
              'P0',
              95::smallint,
              65::smallint,
              false,
              '{"poll_interval_seconds":120,"request_timeout_seconds":15,"user_agent":"Mozilla/5.0 (compatible; XAUUSDEventRadar/1.0)"}'::jsonb
            ),
            (
              'US State Department RSS',
              'https://www.state.gov/rss-feed/press-releases/feed/',
              'rss',
              'us_diplomacy',
              'official',
              'US State Department official press releases RSS feed.',
              'en',
              'P0',
              94::smallint,
              60::smallint,
              false,
              '{"poll_interval_seconds":120,"request_timeout_seconds":15}'::jsonb
            ),
            (
              'Tasnim RSS',
              'https://www.tasnimnews.ir/en/rss',
              'rss',
              'iran_irgc_adjacent',
              'semi_official',
              'Tasnim RSS for hardline/security-adjacent Iranian news.',
              'en',
              'P0',
              78::smallint,
              75::smallint,
              true,
              '{"poll_interval_seconds":60,"request_timeout_seconds":30}'::jsonb
            ),
            (
              'Sepah News',
              'https://sepahnews.ir/',
              'html_polling',
              'iran_irgc_official',
              'official',
              'IRGC official public relations news site; parser configuration required.',
              'fa',
              'P0',
              94::smallint,
              60::smallint,
              false,
              '{"poll_interval_seconds":120,"request_timeout_seconds":15,"requires_parser_config":true,"keyword_language":"fa"}'::jsonb
            ),
            (
              'Mehr News RSS',
              'https://en.mehrnews.com/rss',
              'rss',
              'iran_conservative',
              'semi_official',
              'Mehr English RSS for semi-official conservative Iranian framing.',
              'en',
              'P1',
              74::smallint,
              65::smallint,
              true,
              '{"poll_interval_seconds":120,"request_timeout_seconds":15}'::jsonb
            ),
            (
              'Press TV Website',
              'https://www.presstv.ir/rss/rss-101.xml',
              'rss',
              'iran_external_media',
              'official',
              'Press TV Iran official RSS feed.',
              'en',
              'P1',
              78::smallint,
              70::smallint,
              true,
              '{"poll_interval_seconds":120,"request_timeout_seconds":15}'::jsonb
            ),
            (
              'US Treasury Press Releases',
              'https://home.treasury.gov/news/press-releases',
              'html_polling',
              'us_sanctions',
              'official',
              'US Treasury official press releases for sanctions and financial restrictions.',
              'en',
              'P1',
              94::smallint,
              55::smallint,
              false,
              '{"poll_interval_seconds":180,"request_timeout_seconds":15,"list_selector":".content--2col__body > div","title_selector":"h3.featured-stories__headline a","url_selector":"h3.featured-stories__headline a","published_selector":"time","published_attr":"datetime"}'::jsonb
            ),
            (
              'OFAC Recent Actions',
              'https://ofac.treasury.gov/recent-actions',
              'html_polling',
              'us_sanctions',
              'official',
              'OFAC recent actions page; RSS is not assumed in V1.',
              'en',
              'P2',
              95::smallint,
              50::smallint,
              false,
              '{"poll_interval_seconds":300,"request_timeout_seconds":15,"list_selector":".search-result.views-row","title_selector":"a[href^=\"/recent-actions/\"]","url_selector":"a[href^=\"/recent-actions/\"]","published_selector":".font-sans-2xs","published_regex":"^([A-Za-z]+ \\\\d{2}, \\\\d{4})"}'::jsonb
            ),
            (
              'Jerusalem Post Iran News',
              'https://www.jpost.com/tags/iran-news',
              'html_polling',
              'israel_media',
              'unofficial',
              'Israeli media/security-establishment-adjacent perspective; requires confirmation.',
              'en',
              'P2',
              68::smallint,
              65::smallint,
              true,
              '{"poll_interval_seconds":300,"request_timeout_seconds":15,"requires_parser_config":true}'::jsonb
            )
        ) as seed_sources (
          name,
          handle_or_url,
          source_type,
          source_group,
          official_level,
          stance,
          language,
          priority,
          reliability_score,
          latency_score,
          requires_confirmation,
          source_config
        )
        where not exists (
          select 1
          from sources
          where sources.source_type = seed_sources.source_type
            and lower(sources.handle_or_url) = lower(seed_sources.handle_or_url)
        )
        """
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        delete from sources
        where (source_type, lower(handle_or_url)) in (
          ('telegram', lower('@TrumpTruthSocial_Alert')),
          ('telegram', lower('@Irna_en')),
          ('telegram', lower('@Tasnimnews')),
          ('telegram', lower('@Khamenei_en')),
          ('telegram', lower('@idfofficial')),
          ('telegram', lower('@presstv')),
          ('telegram', lower('@enmehrnews')),
          ('telegram', lower('@israelmfa')),
          ('telegram', lower('@FinancialJuice')),
          ('telegram', lower('@Middle_East_Spectator')),
          ('telegram', lower('@OSINTdefender')),
          ('rss', lower('https://www.federalreserve.gov/feeds/press_all.xml')),
          ('html_polling', lower('https://www.centcom.mil/MEDIA/PRESS-RELEASES/')),
          ('html_polling', lower('https://www.state.gov/rss-feeds/')),
          ('rss', lower('https://www.tasnimnews.com/en/rss')),
          ('html_polling', lower('https://www.sepahnews.com/')),
          ('rss', lower('https://en.mehrnews.com/rss')),
          ('html_polling', lower('https://www.presstv.ir/')),
          ('html_polling', lower('https://home.treasury.gov/news/press-releases')),
          ('html_polling', lower('https://ofac.treasury.gov/recent-actions')),
          ('html_polling', lower('https://www.jpost.com/tags/iran-news'))
        )
        """
    )
