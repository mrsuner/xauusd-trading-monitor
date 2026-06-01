from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Page(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int


class ErrorEnvelope(BaseModel):
    error: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    database: str
    service: str = "dashboard-api"


class OverviewStats(BaseModel):
    active_sources: int = 0
    raw_items_1h: int = 0
    raw_items_24h: int = 0
    events_1h: int = 0
    events_24h: int = 0
    high_impact_events_24h: int = 0
    failed_processing: int = 0
    failed_alerts: int = 0


class QueryParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)


class SourceFilters(BaseModel):
    source_type: str | None = None
    source_group: str | None = None
    priority: str | None = None
    enabled: bool | None = None
    archived: bool | None = None


SourceType = Literal["telegram", "rss", "atom", "html_polling", "api"]
OfficialLevel = Literal["official", "semi_official", "unofficial", "unofficial_mirror", "aggregator"]
Priority = Literal["P0", "P1", "P2", "P3"]
TranslationPolicy = Literal["disabled", "summary_only", "full"]
TranslationPriority = Literal["normal", "high"]
Severity = Literal["S", "A", "B", "C"]


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    handle_or_url: str = Field(min_length=1, max_length=1000)
    source_type: SourceType
    source_group: str
    official_level: OfficialLevel
    stance: str | None = None
    language: str | None = None
    priority: Priority
    reliability_score: int = Field(default=50, ge=0, le=100)
    latency_score: int = Field(default=50, ge=0, le=100)
    requires_confirmation: bool = True
    translation_policy: TranslationPolicy = "full"
    translation_priority: TranslationPriority = "normal"
    translation_max_chars: int | None = Field(default=None, ge=0)
    always_full_translate: bool = False
    telegram_alert_enabled: bool = True
    pushover_alert_enabled: bool = False
    telegram_min_severity: Severity = "B"
    pushover_min_severity: Severity = "S"
    alert_weight: int = Field(default=50, ge=0, le=100)
    alert_rate_limit_per_hour: int | None = Field(default=None, ge=0)
    alert_cooldown_minutes: int | None = Field(default=None, ge=0)
    enabled: bool = True
    source_config: dict[str, Any] = Field(default_factory=dict)


class SourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    handle_or_url: str | None = Field(default=None, min_length=1, max_length=1000)
    source_type: SourceType | None = None
    source_group: str | None = None
    official_level: OfficialLevel | None = None
    stance: str | None = None
    language: str | None = None
    priority: Priority | None = None
    reliability_score: int | None = Field(default=None, ge=0, le=100)
    latency_score: int | None = Field(default=None, ge=0, le=100)
    requires_confirmation: bool | None = None
    translation_policy: TranslationPolicy | None = None
    translation_priority: TranslationPriority | None = None
    translation_max_chars: int | None = Field(default=None, ge=0)
    always_full_translate: bool | None = None
    telegram_alert_enabled: bool | None = None
    pushover_alert_enabled: bool | None = None
    telegram_min_severity: Severity | None = None
    pushover_min_severity: Severity | None = None
    alert_weight: int | None = Field(default=None, ge=0, le=100)
    alert_rate_limit_per_hour: int | None = Field(default=None, ge=0)
    alert_cooldown_minutes: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    source_config: dict[str, Any] | None = None


class SourceHealthFilters(BaseModel):
    service_name: str | None = None
    status: str | None = None
    source_type: str | None = None


class RawItemFilters(BaseModel):
    source_id: UUID | None = None
    source_type: str | None = None
    source_group: str | None = None
    priority: str | None = None
    content_category: str | None = None
    topic_tag: str | None = None
    actor: str | None = None
    classification_status: str | None = None
    is_relevant: bool | None = None
    min_relevance_score: int | None = Field(default=None, ge=0, le=100)
    has_event: bool | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    ingested_from: datetime | None = None
    ingested_to: datetime | None = None
    q: str | None = None


class ProcessingFilters(BaseModel):
    status: str | None = None
    stage: str | None = None
    is_relevant: bool | None = None
    min_relevance_score: int | None = Field(default=None, ge=0, le=100)
    model_provider: str | None = None


class EventFilters(BaseModel):
    severity: str | None = None
    event_type: str | None = None
    source_group: str | None = None
    min_relevance_score: int | None = Field(default=None, ge=0, le=100)
    created_from: datetime | None = None
    created_to: datetime | None = None


class AlertFilters(BaseModel):
    channel: str | None = None
    delivery_status: str | None = None
    priority: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
