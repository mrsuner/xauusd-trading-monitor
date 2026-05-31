from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from .models import ClassificationResult, ModelResponse, NormalizedItem, RawItem, SourceMetadata
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
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format
        self.reasoning_effort = reasoning_effort

    async def classify(self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem) -> ModelResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

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
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.response_format == "json_schema":
            payload["response_format"] = classification_json_schema_response_format()
        elif self.response_format == "text":
            payload["response_format"] = {"type": "text"}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        message = body["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
        try:
            decoded = json.loads(content)
            result = ClassificationResult.model_validate(decoded)
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ModelClientError(f"invalid model response: {exc}") from exc

        return ModelResponse(provider=self.provider, model=self.model, result=result, raw_output=body)


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
