from __future__ import annotations

from datetime import datetime
from typing import Any
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


class SourceHealthFilters(BaseModel):
    service_name: str | None = None
    status: str | None = None
    source_type: str | None = None


class RawItemFilters(BaseModel):
    source_id: UUID | None = None
    source_type: str | None = None
    source_group: str | None = None
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
