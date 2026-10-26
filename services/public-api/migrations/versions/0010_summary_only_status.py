"""Accept explicitly summary-only upstream translations without full text."""
from alembic import op

revision = "0010_summary_only_status"
down_revision = "0009_digest_content_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public_raw_item_translations drop constraint public_raw_item_translations_status_check")
    op.execute("""alter table public_raw_item_translations add constraint public_raw_item_translations_status_check
        check (status is null or status in ('pending','completed','completed_truncated','skipped','failed','summary_only'))""")
    op.execute("""alter table public_raw_item_translations add constraint summary_only_has_no_full_translation
        check (status <> 'summary_only' or (full_translation is null and nullif(btrim(summary),'') is not null))""")


def downgrade() -> None:
    op.execute("alter table public_raw_item_translations drop constraint summary_only_has_no_full_translation")
    op.execute("update public_raw_item_translations set status='skipped' where status='summary_only'")
    op.execute("alter table public_raw_item_translations drop constraint public_raw_item_translations_status_check")
    op.execute("""alter table public_raw_item_translations add constraint public_raw_item_translations_status_check
        check (status is null or status in ('pending','completed','completed_truncated','skipped','failed'))""")
