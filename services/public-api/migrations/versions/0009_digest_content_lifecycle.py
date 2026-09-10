"""add digest content lifecycle fields

Revision ID: 0009_digest_content_lifecycle
Revises: 0008_subscription_catalog
"""

from alembic import op

revision = "0009_digest_content_lifecycle"
down_revision = "0008_subscription_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public_events add column public_content_ready_at timestamptz")
    op.execute("alter table public_events add column invalidated_at timestamptz")
    op.execute("alter table public_events add column invalidation_kind text")
    op.execute("alter table public_events add column invalidation_reason text")
    op.execute(
        """
        alter table public_events add constraint public_events_invalidation_kind_check
        check (invalidation_kind is null or invalidation_kind in ('withdrawal', 'material_correction'))
        """
    )
    op.execute(
        """
        update public_events pe
        set public_content_ready_at = ready.ready_at
        from (
          select public_event_id, min(created_at) as ready_at
          from public_events_translations
          where nullif(btrim(summary), '') is not null
          group by public_event_id
        ) ready
        where ready.public_event_id = pe.id
          and pe.public_content_ready_at is null
        """
    )
    op.execute(
        "create index public_events_digest_ready_idx "
        "on public_events (public_content_ready_at, id) where is_visible = true and public_content_ready_at is not null"
    )
    op.execute(
        """
        alter table public_ingest_requests drop constraint public_ingest_requests_ingest_kind_check
        """
    )
    op.execute(
        """
        alter table public_ingest_requests add constraint public_ingest_requests_ingest_kind_check
        check (ingest_kind in ('event', 'raw_item', 'subscription_catalog', 'event_invalidation'))
        """
    )


def downgrade() -> None:
    op.execute("alter table public_ingest_requests drop constraint public_ingest_requests_ingest_kind_check")
    op.execute(
        """
        alter table public_ingest_requests add constraint public_ingest_requests_ingest_kind_check
        check (ingest_kind in ('event', 'raw_item', 'subscription_catalog'))
        """
    )
    op.execute("drop index if exists public_events_digest_ready_idx")
    op.execute("alter table public_events drop constraint if exists public_events_invalidation_kind_check")
    op.execute("alter table public_events drop column if exists invalidation_reason")
    op.execute("alter table public_events drop column if exists invalidation_kind")
    op.execute("alter table public_events drop column if exists invalidated_at")
    op.execute("alter table public_events drop column if exists public_content_ready_at")
