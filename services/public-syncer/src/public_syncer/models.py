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


class PublicRawItemTranslation(BaseModel):
    language: str
    summary: str | None = None
    full_translation: str | None = None
    status: str | None = None
    input_chars: int | None = None


class PublicRawItem(BaseModel):
    id: UUID
    source_id: UUID
    source_updated_at: datetime
    retry_count: int = 0
    external_id: str | None = None
    published_at: datetime | None = None
    ingested_at: datetime
    edited_at: datetime | None = None
    title: str | None = None
    text_clean: str | None = None
    language: str | None = None
    url: str | None = None
    media_type: str | None = None
    summary_zh: str | None = None
    summary_en: str | None = None
    full_translation_zh: str | None = None
    full_translation_en: str | None = None
    translations: list[PublicRawItemTranslation] = Field(default_factory=list)
    translation_status: str | None = None
    translation_input_chars: int | None = None
    content_category: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    mentioned_actors: list[str] = Field(default_factory=list)
    source_name: str | None = None
    source_type: str | None = None
    source_group: str | None = None
    official_level: str | None = None
    priority: str | None = None
    classification_stage: str | None = None
    classification_status: str | None = None
    is_relevant: bool | None = None
    relevance_score: int | None = None
    filter_reason: str | None = None
    upstream_event_ids: list[UUID] = Field(default_factory=list)

    @field_validator("translations", mode="before")
    @classmethod
    def normalize_translations(cls, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @field_validator("topic_tags", "mentioned_actors", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    @field_validator("upstream_event_ids", mode="before")
    @classmethod
    def normalize_event_ids(cls, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []


class PublicApiResult(BaseModel):
    success: bool
    status_code: int | None = None
    response_json: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    public_event_id: str | None = None
    public_raw_item_id: str | None = None
    is_duplicate: bool = False
    is_transient: bool = False
    retry_after_seconds: int | None = None
