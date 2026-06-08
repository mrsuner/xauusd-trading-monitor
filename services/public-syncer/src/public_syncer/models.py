from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PublicOutboxTranslation(BaseModel):
    language: str
    title: str | None = None
    summary: str | None = None
    status: str | None = None


class PublicOutboxItem(BaseModel):
    id: UUID
    event_id: UUID
    public_title_zh: str | None = None
    public_summary_zh: str | None = None
    public_title_en: str | None = None
    public_summary_en: str | None = None
    translations: list[PublicOutboxTranslation] = Field(default_factory=list)
    public_source_links: list[dict[str, Any]] = Field(default_factory=list)
    severity: str
    relevance_score: int | None = None
    confirmation_state: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    retry_count_web: int = 0
    generated_at: datetime
    event_time: datetime | None = None

    @field_validator("public_source_links", mode="before")
    @classmethod
    def normalize_source_links(cls, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @field_validator("translations", mode="before")
    @classmethod
    def normalize_translations(cls, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []


class PublicApiResult(BaseModel):
    success: bool
    status_code: int | None = None
    response_json: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    public_event_id: str | None = None
    is_duplicate: bool = False
    is_transient: bool = False
    retry_after_seconds: int | None = None
