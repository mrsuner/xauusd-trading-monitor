"""add ai model call usage tracking

Revision ID: 0006_ai_model_calls
Revises: 0005_source_alert_policy
Create Date: 2026-05-31 22:05:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0006_ai_model_calls"
down_revision = "0005_source_alert_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists ai_model_calls (
          id uuid primary key default gen_random_uuid(),
          raw_item_id uuid references raw_items(id) on delete set null,
          event_id uuid references events(id) on delete set null,
          source_id uuid references sources(id) on delete set null,
          service_name text not null,
          ai_layer text not null,
          route_name text not null,
          provider text not null,
          model_name text not null,
          request_kind text not null,
          input_tokens integer,
          output_tokens integer,
          total_tokens integer,
          estimated_cost_usd numeric(12, 6),
          latency_ms integer,
          success boolean not null,
          error_type text,
          error_message text,
          response_format text,
          usage_json jsonb not null default '{}'::jsonb,
          request_hash text,
          created_at timestamptz not null default now(),

          constraint ai_model_calls_ai_layer_check check (
            ai_layer in ('translation_summary', 'classification_reasoning', 'advanced_reasoning')
          ),
          constraint ai_model_calls_token_check check (
            (input_tokens is null or input_tokens >= 0)
            and (output_tokens is null or output_tokens >= 0)
            and (total_tokens is null or total_tokens >= 0)
          ),
          constraint ai_model_calls_latency_check check (
            latency_ms is null or latency_ms >= 0
          ),
          constraint ai_model_calls_cost_check check (
            estimated_cost_usd is null or estimated_cost_usd >= 0
          )
        )
        """
    )
    op.execute("create index if not exists ai_model_calls_created_idx on ai_model_calls (created_at desc)")
    op.execute("create index if not exists ai_model_calls_model_idx on ai_model_calls (provider, model_name, created_at desc)")
    op.execute("create index if not exists ai_model_calls_source_idx on ai_model_calls (source_id, created_at desc)")
    op.execute("create index if not exists ai_model_calls_layer_idx on ai_model_calls (ai_layer, created_at desc)")
    op.execute("create index if not exists ai_model_calls_raw_item_idx on ai_model_calls (raw_item_id, created_at desc)")


def downgrade() -> None:
    op.execute("drop table if exists ai_model_calls")
