from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from .models import (
    AuxiliaryModelResponse,
    AuxiliaryTextResult,
    ClassificationResult,
    ModelResponse,
    NormalizedItem,
    RawItem,
    SourceMetadata,
)
from .settings import Settings


class ModelClientError(RuntimeError):
    pass


class OpenAIStyleModelClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        response_format: str,
        reasoning_effort: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format
        self.reasoning_effort = reasoning_effort
        self.extra_headers = extra_headers or {}

    async def classify(self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem) -> ModelResponse:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source": {
                                "name": source.name,
                                "source_group": source.source_group,
                                "official_level": source.official_level,
                                "priority": source.priority,
                                "stance": source.stance,
                                "requires_confirmation": source.requires_confirmation,
                            },
                            "raw_item": {
                                "title": raw_item.title,
                                "text_clean": normalized.text_clean,
                                "language": normalized.language,
                                "url": raw_item.url,
                                "published_at": raw_item.published_at.isoformat() if raw_item.published_at else None,
                            },
                            "rule_prefilter": {
                                "keyword_score": normalized.keyword_score,
                                "matched_keywords": normalized.matched_keywords,
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        self._apply_common_payload_options(payload, classification_json_schema_response_format())
        body = await self._post_chat_completions(payload)

        content = extract_message_content(body)
        try:
            decoded = json.loads(content)
            result = ClassificationResult.model_validate(decoded)
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ModelClientError(f"invalid model response: {exc}") from exc

        return ModelResponse(provider=self.provider, model=self.model, result=result, raw_output=body)

    async def summarize_and_translate(
        self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem
    ) -> AuxiliaryModelResponse:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": auxiliary_text_system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source": {
                                "name": source.name,
                                "source_type": source.source_type,
                                "source_group": source.source_group,
                                "official_level": source.official_level,
                                "priority": source.priority,
                                "stance": source.stance,
                            },
                            "raw_item": {
                                "title": raw_item.title,
                                "text_clean": normalized.text_clean,
                                "language": normalized.language,
                                "url": raw_item.url,
                                "published_at": raw_item.published_at.isoformat() if raw_item.published_at else None,
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        self._apply_common_payload_options(payload, auxiliary_text_json_schema_response_format())
        body = await self._post_chat_completions(payload)

        content = extract_message_content(body)
        try:
            decoded = json.loads(content)
            result = AuxiliaryTextResult.model_validate(decoded)
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ModelClientError(f"invalid auxiliary model response: {exc}") from exc

        return AuxiliaryModelResponse(provider=self.provider, model=self.model, result=result, raw_output=body)

    async def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _apply_common_payload_options(self, payload: dict[str, Any], schema_response_format: dict[str, Any]) -> None:
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.response_format == "json_schema":
            payload["response_format"] = schema_response_format
        elif self.response_format == "text":
            payload["response_format"] = {"type": "text"}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort


def build_model_client(settings: Settings) -> OpenAIStyleModelClient:
    if settings.model_route == "local_8b":
        if not settings.local_model_base_url or not settings.local_model_name:
            raise ValueError("LOCAL_MODEL_BASE_URL and LOCAL_MODEL_NAME are required for local_8b route")
        return OpenAIStyleModelClient(
            provider="local_8b",
            base_url=settings.local_model_base_url,
            api_key=settings.local_model_api_key,
            model=settings.local_model_name,
            timeout_seconds=settings.model_timeout_seconds,
            response_format=settings.local_model_response_format,
            reasoning_effort=settings.local_model_reasoning_effort,
        )

    if settings.model_route == "cloud_small":
        if not settings.cloud_model_base_url or not settings.cloud_model_name:
            raise ValueError("CLOUD_MODEL_BASE_URL and CLOUD_MODEL_NAME are required for cloud_small route")
        if not settings.cloud_model_api_key:
            raise ValueError("CLOUD_MODEL_API_KEY is required for cloud_small route")
        return OpenAIStyleModelClient(
            provider="cloud_small",
            base_url=settings.cloud_model_base_url,
            api_key=settings.cloud_model_api_key,
            model=settings.cloud_model_name,
            timeout_seconds=settings.model_timeout_seconds,
            response_format=settings.cloud_model_response_format,
            reasoning_effort=settings.cloud_model_reasoning_effort,
        )

    raise ValueError(f"unsupported MODEL_ROUTE: {settings.model_route}")


def build_auxiliary_model_client(settings: Settings) -> OpenAIStyleModelClient | None:
    if not settings.auxiliary_model_enabled or settings.auxiliary_model_route == "disabled":
        return None

    if settings.auxiliary_model_route == "openrouter_free":
        if not settings.openrouter_model_base_url or not settings.openrouter_model_name:
            raise ValueError("OPENROUTER_MODEL_BASE_URL and OPENROUTER_MODEL_NAME are required for openrouter_free route")
        if not settings.openrouter_model_api_key:
            raise ValueError("OPENROUTER_MODEL_API_KEY is required for openrouter_free route")
        extra_headers = {}
        if settings.openrouter_http_referer:
            extra_headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_app_title:
            extra_headers["X-Title"] = settings.openrouter_app_title
        return OpenAIStyleModelClient(
            provider="openrouter_free",
            base_url=settings.openrouter_model_base_url,
            api_key=settings.openrouter_model_api_key,
            model=settings.openrouter_model_name,
            timeout_seconds=settings.model_timeout_seconds,
            response_format=settings.openrouter_model_response_format,
            reasoning_effort=settings.openrouter_model_reasoning_effort,
            extra_headers=extra_headers,
        )

    raise ValueError(f"unsupported AUXILIARY_MODEL_ROUTE: {settings.auxiliary_model_route}")


def extract_message_content(body: dict[str, Any]) -> str:
    message = body["choices"][0]["message"]
    content = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def system_prompt() -> str:
    return (
        "You classify news items for an XAUUSD event radar. "
        "Return only valid JSON. Do not provide trading instructions, entries, stop loss, take profit, "
        "position sizing, buy, sell, long, short, bullish, or bearish recommendations. "
        "Do not predict market direction. "
        "Do not describe the event as a gold catalyst or imply whether gold should rise or fall. "
        "Use Traditional Chinese for summary_zh. "
        "Decide whether the item is relevant to gold through safe_haven, real_rate, inflation, dollar, "
        "liquidity, oil, sanctions, geopolitics, or Fed expectations. "
        "The JSON schema is: "
        '{"is_relevant": boolean, "relevance_score": 0-100, "event_type": string, '
        '"source_stance": string|null, "claim_direction": "confirm|deny|warn|escalate|deescalate|neutral|unknown", '
        '"claim_text": string|null, "summary_zh": string, "summary_en": string|null, "actors": string[], '
        '"xauusd_impact_channel": string[], "requires_confirmation": boolean, "confidence": 0-100|null, '
        '"reason": string|null, "region": string|null, "primary_actor": string|null, '
        '"secondary_actor": string|null, "market_relevance": string|null}.'
    )


def auxiliary_text_system_prompt() -> str:
    return (
        "You summarize and translate news items for an XAUUSD event radar. "
        "Return only valid JSON. Use Traditional Chinese. "
        "Do not provide trading instructions, entries, stop loss, take profit, position sizing, buy, sell, long, "
        "short, bullish, or bearish recommendations. Do not predict market direction. "
        "summary_zh must be a concise Traditional Chinese news summary, preferably under 90 Chinese characters. "
        "If the source text is not Chinese, translation_zh should be a faithful Traditional Chinese translation of "
        "the key content, preferably under 500 Chinese characters. If the source text is already Chinese, "
        "translation_zh should be null. Preserve names, places, institutions, numbers, dates, and uncertainty. "
        "Do not add facts that are not in the input. "
        "The JSON schema is: "
        '{"summary_zh": string, "translation_zh": string|null, "detected_language": string|null, "notes": string|null}.'
    )


def classification_json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "xauusd_event_classification",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "is_relevant": {"type": "boolean"},
                    "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "event_type": {"type": "string"},
                    "source_stance": {"type": ["string", "null"]},
                    "claim_direction": {
                        "type": "string",
                        "enum": ["confirm", "deny", "warn", "escalate", "deescalate", "neutral", "unknown"],
                    },
                    "claim_text": {"type": ["string", "null"]},
                    "summary_zh": {"type": "string"},
                    "summary_en": {"type": ["string", "null"]},
                    "actors": {"type": "array", "items": {"type": "string"}},
                    "xauusd_impact_channel": {"type": "array", "items": {"type": "string"}},
                    "requires_confirmation": {"type": "boolean"},
                    "confidence": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
                    "reason": {"type": ["string", "null"]},
                    "region": {"type": ["string", "null"]},
                    "primary_actor": {"type": ["string", "null"]},
                    "secondary_actor": {"type": ["string", "null"]},
                    "market_relevance": {"type": ["string", "null"]},
                },
                "required": [
                    "is_relevant",
                    "relevance_score",
                    "event_type",
                    "source_stance",
                    "claim_direction",
                    "claim_text",
                    "summary_zh",
                    "summary_en",
                    "actors",
                    "xauusd_impact_channel",
                    "requires_confirmation",
                    "confidence",
                    "reason",
                    "region",
                    "primary_actor",
                    "secondary_actor",
                    "market_relevance",
                ],
            },
        },
    }


def auxiliary_text_json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "xauusd_auxiliary_text",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary_zh": {"type": "string"},
                    "translation_zh": {"type": ["string", "null"]},
                    "detected_language": {"type": ["string", "null"]},
                    "notes": {"type": ["string", "null"]},
                },
                "required": ["summary_zh", "translation_zh", "detected_language", "notes"],
            },
        },
    }
