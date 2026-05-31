"""add source alert policy

Revision ID: 0005_source_alert_policy
Revises: 0004_translation_fields
Create Date: 2026-05-31 21:50:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0005_source_alert_policy"
down_revision = "0004_translation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table sources add column if not exists telegram_alert_enabled boolean not null default true")
    op.execute("alter table sources add column if not exists pushover_alert_enabled boolean not null default false")
    op.execute("alter table sources add column if not exists telegram_min_severity text not null default 'B'")
    op.execute("alter table sources add column if not exists pushover_min_severity text not null default 'S'")
    op.execute("alter table sources add column if not exists alert_weight smallint not null default 50")
    op.execute("alter table sources add column if not exists alert_rate_limit_per_hour integer")
    op.execute("alter table sources add column if not exists alert_cooldown_minutes integer")
    op.execute("alter table alerts add column if not exists alert_score integer")

    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_telegram_min_severity_check'
          ) then
            alter table sources add constraint sources_telegram_min_severity_check
              check (telegram_min_severity in ('S', 'A', 'B', 'C'));
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_pushover_min_severity_check'
          ) then
            alter table sources add constraint sources_pushover_min_severity_check
              check (pushover_min_severity in ('S', 'A', 'B', 'C'));
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_alert_weight_check'
          ) then
            alter table sources add constraint sources_alert_weight_check
              check (alert_weight >= 0 and alert_weight <= 100);
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_alert_rate_limit_per_hour_check'
          ) then
            alter table sources add constraint sources_alert_rate_limit_per_hour_check
              check (alert_rate_limit_per_hour is null or alert_rate_limit_per_hour >= 0);
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'sources_alert_cooldown_minutes_check'
          ) then
            alter table sources add constraint sources_alert_cooldown_minutes_check
              check (alert_cooldown_minutes is null or alert_cooldown_minutes >= 0);
          end if;
        end $$;
        """
    )
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'alerts_alert_score_check'
          ) then
            alter table alerts add constraint alerts_alert_score_check
              check (alert_score is null or alert_score >= 0);
          end if;
        end $$;
        """
    )

    op.execute(
        """
        update sources
        set alert_weight = case
              when priority = 'P0' and official_level = 'official' then 90
              when priority = 'P0' and official_level = 'semi_official' then 78
              when priority = 'P0' then 72
              when priority = 'P1' and official_level = 'official' then 74
              when priority = 'P1' then 62
              when priority = 'P2' then 45
              else 35
            end,
            telegram_min_severity = case
              when source_group in ('osint_aggregator', 'market_squawk') then 'A'
              when priority in ('P0', 'P1') then 'B'
              else 'A'
            end,
            pushover_alert_enabled = case
              when source_group in (
                'us_fed',
                'us_military',
                'us_diplomacy',
                'us_sanctions',
                'iran_government',
                'iran_irgc_official',
                'iran_supreme_leader',
                'israel_military',
                'israel_diplomacy'
              ) then true
              when source_group in ('us_trump', 'iran_irgc_adjacent') then true
              else false
            end,
            pushover_min_severity = case
              when source_group in ('us_trump', 'iran_irgc_adjacent') then 'S'
              when source_group in ('us_fed', 'us_military', 'us_sanctions', 'iran_irgc_official', 'iran_supreme_leader', 'israel_military') then 'A'
              else 'S'
            end,
            alert_rate_limit_per_hour = case
              when source_group in ('osint_aggregator', 'market_squawk') then 4
              when priority = 'P2' then 6
              else null
            end,
            alert_cooldown_minutes = case
              when source_group in ('osint_aggregator', 'market_squawk') then 10
              else null
            end
        """
    )


def downgrade() -> None:
    op.execute("alter table alerts drop constraint if exists alerts_alert_score_check")
    op.execute("alter table alerts drop column if exists alert_score")
    op.execute("alter table sources drop constraint if exists sources_alert_cooldown_minutes_check")
    op.execute("alter table sources drop constraint if exists sources_alert_rate_limit_per_hour_check")
    op.execute("alter table sources drop constraint if exists sources_alert_weight_check")
    op.execute("alter table sources drop constraint if exists sources_pushover_min_severity_check")
    op.execute("alter table sources drop constraint if exists sources_telegram_min_severity_check")
    op.execute("alter table sources drop column if exists alert_cooldown_minutes")
    op.execute("alter table sources drop column if exists alert_rate_limit_per_hour")
    op.execute("alter table sources drop column if exists alert_weight")
    op.execute("alter table sources drop column if exists pushover_min_severity")
    op.execute("alter table sources drop column if exists telegram_min_severity")
    op.execute("alter table sources drop column if exists pushover_alert_enabled")
    op.execute("alter table sources drop column if exists telegram_alert_enabled")
