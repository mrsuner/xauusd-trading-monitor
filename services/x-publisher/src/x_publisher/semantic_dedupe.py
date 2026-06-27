from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from .message import canonical_source_link, summary_for, title_for
from .models import PublicOutboxItem
from .security import sanitize_text
from .settings import Settings

logger = logging.getLogger(__name__)


class SemanticDedupeResult(BaseModel):
    is_duplicate: bool
    similarity_score: int = Field(ge=0, le=100)
    matched_item_id: str | None = None
    reason: str | None = None
    model: str | None = None


class SemanticDedupeClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self.base_url = (
            settings.semantic_dedupe_model_base_url
            or settings.translation_model_base_url
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.api_key = (
            settings.semantic_dedupe_model_api_key
            or settings.translation_model_api_key
            or settings.openrouter_model_api_key
        )
        self.models = semantic_dedupe_models(settings)
        self.response_format = settings.semantic_dedupe_response_format or settings.translation_model_response_format
        self.reasoning_effort = settings.semantic_dedupe_reasoning_effort or settings.translation_model_reasoning_effort
        self.http_referer = settings.semantic_dedupe_http_referer or settings.translation_http_referer
        self.app_title = settings.semantic_dedupe_app_title or settings.translation_app_title

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.models)

    async def compare(
        self,
        item: PublicOutboxItem,
        candidates: list[PublicOutboxItem],
    ) -> SemanticDedupeResult | None:
        if not self.settings.semantic_dedupe_enabled or not candidates:
            return None
        if not self.configured:
            logger.warning("x_semantic_dedupe_not_configured")
            return None

        last_error: Exception | None = None
        for model in self.models:
            try:
                result = await self._compare_with_model(model, item, candidates)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "x_semantic_dedupe_failed model=%s error=%s",
                    model,
                    sanitize_text(str(exc)),
                    exc_info=True,
                )
                continue

            result = result.model_copy(update={"model": model})
            if result.is_duplicate and result.similarity_score < self.settings.semantic_dedupe_threshold:
                return result.model_copy(update={"is_duplicate": False})
            return result

        if last_error:
            return None
        return None

    async def _compare_with_model(
        self,
        model: str,
        item: PublicOutboxItem,
        candidates: list[PublicOutboxItem],
    ) -> SemanticDedupeResult:
        payload: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "current_item": serialize_item(item),
                            "candidate_items": [serialize_item(candidate) for candidate in candidates],
                            "duplicate_threshold": self.settings.semantic_dedupe_threshold,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        apply_response_format(payload, self.response_format)
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.app_title:
            headers["X-Title"] = self.app_title

        response = await self.client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return parse_response(response.json())


def semantic_dedupe_models(settings: Settings) -> list[str]:
    primary = settings.semantic_dedupe_model_name or settings.translation_primary_model_name
    fallback = settings.semantic_dedupe_fallback_model_name or settings.translation_fallback_model_name
    fallback_enabled = settings.semantic_dedupe_paid_fallback_enabled and settings.translation_paid_fallback_enabled

    models: list[str] = []
    for model in (primary, fallback if fallback_enabled else None):
        if model and model not in models:
            models.append(model)
    return models


def parse_response(body: dict[str, Any]) -> SemanticDedupeResult:
    content = extract_message_content(body)
    try:
        decoded = json.loads(content)
        return SemanticDedupeResult.model_validate(decoded)
    except (TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid semantic dedupe response: {exc}") from exc


def extract_message_content(body: dict[str, Any]) -> str:
    message = body["choices"][0]["message"]
    content = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def apply_response_format(payload: dict[str, Any], response_format: str | None) -> None:
    if response_format == "json_object":
        payload["response_format"] = {"type": "json_object"}
    elif response_format == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "x_semantic_dedupe",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["is_duplicate", "similarity_score", "matched_item_id", "reason"],
                    "properties": {
                        "is_duplicate": {"type": "boolean"},
                        "similarity_score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "matched_item_id": {"type": ["string", "null"]},
                        "reason": {"type": ["string", "null"]},
                    },
                },
            },
        }
    elif response_format == "text":
        payload["response_format"] = {"type": "text"}


def serialize_item(item: PublicOutboxItem) -> dict[str, Any]:
    source_link = canonical_source_link(item)
    return {
        "id": str(item.id),
        "event_id": str(item.event_id),
        "title": title_for(item),
        "summary": summary_for(item),
        "severity": item.severity,
        "confirmation_state": item.confirmation_state,
        "topic_tags": item.topic_tags,
        "source_name": source_link.label if source_link else None,
        "generated_at": item.generated_at.isoformat(),
    }


def system_prompt() -> str:
    return (
        "You compare public X post drafts for an XAUUSD event radar. "
        "Return only valid JSON. Decide if the current item is a semantic duplicate of any candidate. "
        "Treat items as duplicates when they describe the same real-world claim or development, even if the wording, "
        "headline, language, or source label differs. Do not mark duplicates merely because both are about the same "
        "country, actor, market, or broad topic. Preserve uncertainty: an unconfirmed claim and a later confirmation "
        "may be related but are not duplicates if the factual state changed materially. "
        "Use similarity_score 0-100. Use matched_item_id only when is_duplicate is true. "
        "The JSON schema is: "
        '{"is_duplicate": boolean, "similarity_score": integer, "matched_item_id": string|null, "reason": string|null}.'
    )
