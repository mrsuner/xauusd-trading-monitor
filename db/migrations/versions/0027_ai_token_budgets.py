"""Add conservative shared daily and lifetime per-item token reservations."""
from alembic import op

revision = "0027_ai_token_budgets"
down_revision = "0026_ai_daily_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""alter table ai_daily_budgets add column tokens_reserved bigint not null default 0
        check (tokens_reserved >= 0)""")
    op.execute("""create table ai_item_token_budgets (
        raw_item_id uuid primary key references raw_items(id) on delete cascade,
        tokens_reserved bigint not null default 0 check (tokens_reserved >= 0),
        updated_at timestamptz not null default now()
    )""")


def downgrade() -> None:
    op.execute("drop table ai_item_token_budgets")
    op.execute("alter table ai_daily_budgets drop column tokens_reserved")
