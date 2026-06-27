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


class RawItemTranslationContext(BaseModel):
    language: str
    summary: str | None = None
    full_translation: str | None = None
    status: str | None = None


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
    raw_item_translations: list[RawItemTranslationContext] = Field(default_factory=list)
    claims: list[EventClaimContext] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)


class AlertChannelStats(BaseModel):
    sent_or_pending_1h: int = 0
    last_alert_at: datetime | None = None


class RoutePolicyRuntime(BaseModel):
    backfill_mode: str = "normal"
    is_backfill: bool = False
    telegram_stats: AlertChannelStats = Field(default_factory=AlertChannelStats)
    pushover_stats: AlertChannelStats = Field(default_factory=AlertChannelStats)


class AlertDecision(BaseModel):
    event_id: UUID
    channel: str
    priority: str
    message: str
    dedupe_key: str
    alert_score: int


class PublicOutboxTranslation(BaseModel):
    language: str
    title: str | None = None
    summary: str | None = None
    status: str = "approved"


class PublicOutboxDraft(BaseModel):
    event_id: UUID
    translations: list[PublicOutboxTranslation] = Field(default_factory=list)
    public_source_links: list[dict[str, Any]] = Field(default_factory=list)
    severity: str
    relevance_score: int | None = None
    confirmation_state: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    approved_for_public: bool = False
    publish_status_web: str = "skipped"
    publish_status_telegram: str = "skipped"
    publish_status_x: str = "skipped"


class RouteDecision(BaseModel):
    event_id: UUID
    route_key: str
    decision_status: str
    route_score: int
    reason: str | None = None
    payload_table: str | None = None
    payload_id: UUID | None = None


class RouteResult(BaseModel):
    event_id: UUID
    route_key: str
    queued: bool
    route_score: int
    reason: str
    alert: AlertDecision | None = None
    public_outbox: PublicOutboxDraft | None = None
