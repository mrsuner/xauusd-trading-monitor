from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SourceMetadata(BaseModel):
    id: UUID
    name: str
    handle_or_url: str
    source_type: str
    source_group: str
    official_level: str
    stance: str | None = None
    language: str | None = None
    priority: str
    reliability_score: int
    latency_score: int
    requires_confirmation: bool


class RawItem(BaseModel):
    id: UUID
    source_id: UUID
    external_id: str | None = None
    published_at: datetime | None = None
    ingested_at: datetime
    edited_at: datetime | None = None
    title: str | None = None
    text_raw: str | None = None
    text_clean: str | None = None
    summary_zh: str | None = None
    language: str | None = None
    url: str | None = None
    media_type: str
    raw_json: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None
    dedupe_key: str


class ProcessingTask(BaseModel):
    id: UUID
    raw_item: RawItem
    source: SourceMetadata
    attempt_count: int


class NormalizedItem(BaseModel):
    text_clean: str
    language: str
    keyword_score: int
    matched_keywords: list[str] = Field(default_factory=list)
    prefilter_passed: bool
    filter_reason: str | None = None


class ClassificationResult(BaseModel):
    is_relevant: bool
    relevance_score: int = Field(ge=0, le=100)
    event_type: str = "UNKNOWN"
    source_stance: str | None = None
    claim_direction: str = "unknown"
    claim_text: str | None = None
    summary_zh: str
    summary_en: str | None = None
    actors: list[str] = Field(default_factory=list)
    xauusd_impact_channel: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    confidence: int | None = Field(default=None, ge=0, le=100)
    reason: str | None = None
    region: str | None = None
    primary_actor: str | None = None
    secondary_actor: str | None = None
    market_relevance: str | None = None

    @field_validator("claim_direction")
    @classmethod
    def validate_claim_direction(cls, value: str) -> str:
        allowed = {"confirm", "deny", "warn", "escalate", "deescalate", "neutral", "unknown"}
        if value not in allowed:
            return "unknown"
        return value


class ModelResponse(BaseModel):
    provider: str
    model: str
    result: ClassificationResult
    raw_output: dict[str, Any]
