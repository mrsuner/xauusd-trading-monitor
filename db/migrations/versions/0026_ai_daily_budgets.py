"""add shared daily AI request budgets

Revision ID: 0026_ai_daily_budgets
Revises: 0025_domain_routing
Create Date: 2026-09-11 00:30:00.000000
"""

from alembic import op

revision = "0026_ai_daily_budgets"
down_revision = "0025_domain_routing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table ai_daily_budgets (
          budget_date date primary key,
          total_reserved integer not null default 0,
          classification_reserved integer not null default 0,
          translation_reserved integer not null default 0,
          updated_at timestamptz not null default now(),
          constraint ai_daily_budgets_nonnegative_check check (
            total_reserved >= 0 and classification_reserved >= 0 and translation_reserved >= 0
          )
        )
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists ai_daily_budgets")
