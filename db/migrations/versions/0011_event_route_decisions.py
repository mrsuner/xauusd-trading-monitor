"""add event route decisions

Revision ID: 0011_event_route_decisions
Revises: 0010_public_outbox
Create Date: 2026-06-01 14:25:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0011_event_route_decisions"
down_revision = "0010_public_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table event_route_decisions (
          id uuid primary key default gen_random_uuid(),
          event_id uuid not null references events(id) on delete cascade,
          route_key text not null,
          decision_status text not null,
          route_score smallint not null default 0,
          reason text,
          payload_table text,
          payload_id uuid,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint event_route_decisions_status_check check (
            decision_status in ('queued', 'skipped')
          ),
          constraint event_route_decisions_route_score_check check (
            route_score >= 0 and route_score <= 150
          ),
          constraint event_route_decisions_payload_table_check check (
            payload_table is null or payload_table in ('alerts', 'public_outbox', 'none')
          )
        )
        """
    )

    op.execute(
        """
        create unique index event_route_decisions_event_route_uidx
          on event_route_decisions (event_id, route_key)
        """
    )
    op.execute(
        """
        create index event_route_decisions_route_created_idx
          on event_route_decisions (route_key, created_at desc)
        """
    )
    op.execute(
        """
        create index event_route_decisions_status_created_idx
          on event_route_decisions (decision_status, created_at desc)
        """
    )
    op.execute(
        """
        create trigger trg_event_route_decisions_updated_at
        before update on event_route_decisions
        for each row execute function set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_event_route_decisions_updated_at on event_route_decisions")
    op.execute("drop index if exists event_route_decisions_status_created_idx")
    op.execute("drop index if exists event_route_decisions_route_created_idx")
    op.execute("drop index if exists event_route_decisions_event_route_uidx")
    op.execute("drop table if exists event_route_decisions")
