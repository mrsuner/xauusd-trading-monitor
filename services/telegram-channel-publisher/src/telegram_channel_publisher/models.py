from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SourceLink(BaseModel):
    source_name: str | None = None
    name: str | None = None
    url: str | None = None

    @property
    def label(self) -> str:
        return self.source_name or self.name or "Source"


class PublicOutboxItem(BaseModel):
    id: UUID
    event_id: UUID
    title: str | None = None
    summary: str | None = None
    public_source_links: list[SourceLink] = Field(default_factory=list)
    severity: str
    relevance_score: int | None = None
    confirmation_state: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    retry_count_telegram: int = 0
    generated_at: datetime


class ProviderResult(BaseModel):
    success: bool
    status_code: int | None = None
    response_json: dict[str, Any] = Field(default_factory=dict)
    retry_after_seconds: int | None = None
    error_message: str | None = None
    is_transient: bool = False
