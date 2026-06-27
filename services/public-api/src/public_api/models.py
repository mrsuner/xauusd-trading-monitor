from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class PublicSourceLink(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str | None = None
    source_name: str | None = None
    url: HttpUrl


class PublicEventTranslationInput(BaseModel):
    language: str
    title: str | None = None
    summary: str | None = None

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not LANGUAGE_CODE_RE.match(normalized):
            raise ValueError("invalid language code")
        return normalized

    @field_validator("title", "summary")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def require_public_content(self) -> PublicEventTranslationInput:
        if not self.title and not self.summary:
            raise ValueError("translation requires title or summary")
        return self


class PublicRawItemSourceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    source_type: str | None = None
    source_group: str | None = None
    official_level: str | None = None
    priority: str | None = None

    @field_validator("name", "source_type", "source_group", "official_level", "priority")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized[:120] or None


class PublicRawItemTranslationInput(BaseModel):
    language: str
    summary: str | None = None
    full_translation: str | None = None
    status: str | None = None
    is_truncated: bool = False
    source_chars: int | None = Field(default=None, ge=0)
    translation_chars: int | None = Field(default=None, ge=0)

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not LANGUAGE_CODE_RE.match(normalized):
            raise ValueError("invalid language code")
        return normalized

    @field_validator("summary", "full_translation", "status")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"pending", "completed", "completed_truncated", "skipped", "failed"}:
            raise ValueError("invalid translation status")
        return value

    @model_validator(mode="after")
    def require_public_content(self) -> PublicRawItemTranslationInput:
        if not self.summary and not self.full_translation:
            raise ValueError("translation requires summary or full_translation")
        return self


class PublicRawItemClassificationInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_relevant: bool | None = None
    relevance_score: int | None = Field(default=None, ge=0, le=100)
    filter_reason: str | None = None
    stage: str | None = None
    status: str | None = None

    @field_validator("filter_reason", "stage", "status")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized[:500] or None


class PublicRawItemIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    idempotency_key: str = Field(min_length=1, max_length=300)
    upstream_raw_item_id: UUID
    source: PublicRawItemSourceInput = Field(default_factory=PublicRawItemSourceInput)
    source_url: HttpUrl | None = None
    published_at: datetime | None = None
    ingested_at: datetime | None = None
    edited_at: datetime | None = None
    title: str | None = None
    original_content: str | None = None
    language: str | None = None
    media_type: str | None = None
    translations: list[PublicRawItemTranslationInput] = Field(default_factory=list)
    classification: PublicRawItemClassificationInput = Field(default_factory=PublicRawItemClassificationInput)
    content_category: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    mentioned_actors: list[str] = Field(default_factory=list)
    upstream_event_ids: list[UUID] = Field(default_factory=list)
    scrub_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != "public_raw_item.v1":
            raise ValueError("unsupported schema_version")
        return value

    @field_validator(
        "title",
        "original_content",
        "language",
        "media_type",
        "content_category",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not LANGUAGE_CODE_RE.match(value):
            raise ValueError("invalid language code")
        return value

    @field_validator("topic_tags", "mentioned_actors")
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        return normalize_public_text_list(value)

    @field_validator("content_category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized[:80] or None

    @field_validator("upstream_event_ids")
    @classmethod
    def dedupe_upstream_event_ids(cls, value: list[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        result: list[UUID] = []
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result[:30]

    @model_validator(mode="after")
    def require_public_content(self) -> PublicRawItemIngestRequest:
        if not self.title and not self.original_content and not self.translations:
            raise ValueError("raw item requires public display content")
        return self


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
    translations: list[PublicEventTranslationInput] = Field(default_factory=list)
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
        return normalize_public_text_list(value)

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
    title: str | None
    summary: str | None
    language: str
    available_languages: list[str]
    translations: list[dict[str, Any]] = Field(default_factory=list)
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


def normalize_public_text_list(value: list[str]) -> list[str]:
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
