from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
    translation_policy: str = "full"
    translation_priority: str = "normal"
    translation_max_chars: int | None = None
    always_full_translate: bool = False


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
    summary_en: str | None = None
    full_translation_zh: str | None = None
    full_translation_en: str | None = None
    content_category: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    mentioned_actors: list[str] = Field(default_factory=list)
    translation_status: str = "pending"
    translation_model_provider: str | None = None
    translation_model: str | None = None
    translation_error: str | None = None
    translation_input_chars: int | None = None
    translation_updated_at: datetime | None = None
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


class AuxiliaryTextResult(BaseModel):
    summary_zh: str
    summary_en: str
    full_translation_zh: str | None = None
    full_translation_en: str | None = None
    content_category: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    mentioned_actors: list[str] = Field(default_factory=list)
    detected_language: str | None = None
    notes: str | None = None

    @field_validator("topic_tags", "mentioned_actors", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in normalized:
                normalized.append(text[:120])
        return normalized[:12]


class ModelResponse(BaseModel):
    provider: str
    api_provider: str
    model: str
    result: ClassificationResult
    raw_output: dict[str, Any]
    usage: "AIModelCallUsage"


class AuxiliaryModelResponse(BaseModel):
    provider: str
    api_provider: str
    model: str
    result: AuxiliaryTextResult
    raw_output: dict[str, Any]
    usage: "AIModelCallUsage"


class AIModelCallUsage(BaseModel):
    service_name: str = "normalizer-classifier"
    ai_layer: str
    route_name: str
    provider: str
    model_name: str
    request_kind: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: Decimal | None = None
    latency_ms: int | None = None
    success: bool
    error_type: str | None = None
    error_message: str | None = None
    response_format: str | None = None
    usage_json: dict[str, Any] = Field(default_factory=dict)
    request_hash: str | None = None
