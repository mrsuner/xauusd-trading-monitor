from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SourceContext(BaseModel):
    id: UUID | None = None
    name: str | None = None
    handle_or_url: str | None = None
    source_type: str | None = None
    source_group: str | None = None
    official_level: str | None = None
    priority: str | None = None
    requires_confirmation: bool | None = None
    telegram_alert_enabled: bool = True
    pushover_alert_enabled: bool = False
    telegram_min_severity: str = "B"
    pushover_min_severity: str = "S"
    alert_weight: int = 50
    alert_rate_limit_per_hour: int | None = None
    alert_cooldown_minutes: int | None = None


class RawItemContext(BaseModel):
    id: UUID | None = None
    title: str | None = None
    url: str | None = None
    summary_zh: str | None = None
    summary_en: str | None = None
    text_clean: str | None = None
    text_raw: str | None = None


class EventClaimContext(BaseModel):
    claim_text: str
    claim_direction: str
    stance: str | None = None
    confidence: int | None = None


class EventContext(BaseModel):
    id: UUID
    event_time: datetime | None = None
    detected_at: datetime
    created_at: datetime | None = None
    event_type: str
    severity: str
    relevance_score: int
    confidence: int | None = None
    confirmation_state: str
    title: str | None = None
    summary_zh: str
    summary_en: str | None = None
    market_relevance: str | None = None
    xauusd_impact_channel: list[str] = Field(default_factory=list)
    requires_confirmation: bool
    source_group: str | None = None
    source: SourceContext = Field(default_factory=SourceContext)
    raw_item: RawItemContext = Field(default_factory=RawItemContext)
    claims: list[EventClaimContext] = Field(default_factory=list)


class AlertDecision(BaseModel):
    event_id: UUID
    channel: str
    priority: str
    delivery_status: str
    message: str
    dedupe_key: str
    alert_score: int
    error_message: str | None = None


class AlertChannelStats(BaseModel):
    sent_or_pending_1h: int = 0
    last_alert_at: datetime | None = None


class AlertPolicyRuntime(BaseModel):
    backfill_mode: str = "normal"
    is_backfill: bool = False
    telegram_stats: AlertChannelStats = Field(default_factory=AlertChannelStats)
    pushover_stats: AlertChannelStats = Field(default_factory=AlertChannelStats)


class AlertDelivery(BaseModel):
    id: UUID
    event_id: UUID
    channel: str
    priority: str
    message: str
    attempt_count: int


class ProviderResult(BaseModel):
    success: bool
    status_code: int | None = None
    response_json: dict[str, Any] = Field(default_factory=dict)
    retry_after_seconds: int | None = None
    error_message: str | None = None
    is_transient: bool = False
