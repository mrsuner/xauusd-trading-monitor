from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class PublicSourceLink(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str | None = None
    source_name: str | None = None
    url: HttpUrl


class PublicEventIngestRequest(BaseModel):
    schema_version: str
    idempotency_key: str = Field(min_length=1, max_length=300)
    upstream_event_id: UUID
    event_time: datetime | None = None
    generated_at: datetime | None = None
    severity: str
    relevance_score: int | None = Field(default=None, ge=0, le=100)
    confirmation_state: str | None = None
    public_title_zh: str | None = None
    public_summary_zh: str | None = None
    public_title_en: str | None = None
    public_summary_en: str | None = None
    public_source_links: list[PublicSourceLink] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    content_category: str | None = None
    mentioned_actors: list[str] = Field(default_factory=list)
    route_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != "public_event.v1":
            raise ValueError("unsupported schema_version")
        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        if value not in {"S", "A", "B", "C"}:
            raise ValueError("severity must be S, A, B, or C")
        return value

    @field_validator("confirmation_state")
    @classmethod
    def validate_confirmation_state(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"unconfirmed", "partially_confirmed", "confirmed", "contradicted"}:
            raise ValueError("invalid confirmation_state")
        return value

    @field_validator("topic_tags", "mentioned_actors")
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            normalized = item.strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized[:80])
        return result[:30]

    @field_validator("content_category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized[:80] or None


class PublicEventListItem(BaseModel):
    id: UUID
    upstream_event_id: UUID
    idempotency_key: str
    schema_version: str
    event_time: datetime | None
    generated_at: datetime | None
    received_at: datetime
    severity: str
    relevance_score: int | None
    confirmation_state: str | None
    public_title_zh: str | None
    public_summary_zh: str | None
    public_title_en: str | None
    public_summary_en: str | None
    public_source_links: list[dict[str, Any]]
    topic_tags: list[str]
    content_category: str | None
    mentioned_actors: list[str]
    route_metadata: dict[str, Any]


class PageResponse(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int


class IngestResponse(BaseModel):
    status: str
    public_event_id: UUID
    idempotency_key: str
