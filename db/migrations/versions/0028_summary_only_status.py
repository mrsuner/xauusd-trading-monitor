"""Keep successful summaries distinct from full translations."""
from alembic import op

revision = "0028_summary_only_status"
down_revision = "0027_ai_token_budgets"
branch_labels = None
depends_on = None


def constraints(include_summary: bool) -> None:
    extra = ", 'summary_only'" if include_summary else ""
    for table, column, existing in (
        ("raw_items", "translation_status", ", 'partial_completed'"),
        ("raw_item_translations", "status", ""),
    ):
        name = f"{table}_{column}_check"
        op.execute(f"alter table {table} drop constraint {name}")
        op.execute(f"""alter table {table} add constraint {name}
            check ({column} in ('pending','completed','completed_truncated','skipped','failed'{existing}{extra}))""")


def upgrade() -> None:
    constraints(True)
    op.execute("""alter table raw_item_translations add constraint summary_only_has_no_full_translation
        check (status <> 'summary_only' or (full_translation is null and nullif(btrim(summary),'') is not null))""")


def downgrade() -> None:
    op.execute("alter table raw_item_translations drop constraint summary_only_has_no_full_translation")
    op.execute("update raw_item_translations set status='skipped' where status='summary_only'")
    op.execute("update raw_items set translation_status='skipped' where translation_status='summary_only'")
    constraints(False)
