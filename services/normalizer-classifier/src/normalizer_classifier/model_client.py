from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from .models import (
    AuxiliaryModelResponse,
    AuxiliaryTextResult,
    AIModelCallUsage,
    ClassificationResult,
    ModelResponse,
    NormalizedItem,
    RawItem,
    SourceMetadata,
)
from .settings import Settings
from .usage import (
    estimated_cost_usd,
    estimate_messages_tokens,
    estimate_text_tokens,
    infer_api_provider,
    request_hash,
    usage_from_response,
)
from .taxonomy import TaxonomyContext


logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"
SENSITIVE_LOG_KEY_PARTS = (
    "authorization",
    "api_key",
    "bearer",
    "credential",
    "password",
    "secret",
    "signature",
    "token",
)


class ModelClientError(RuntimeError):
    def __init__(self, message: str, *, usage: AIModelCallUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


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
        translation_output_languages: tuple[str, ...] = ("zh-Hant", "en"),
        translation_language_labels: dict[str, str] | None = None,
        translation_require_all_languages: bool = True,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.api_provider = infer_api_provider(base_url)
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format
        self.reasoning_effort = reasoning_effort
        self.extra_headers = extra_headers or {}
        self.translation_output_languages = translation_output_languages
        self.translation_language_labels = translation_language_labels or {}
        self.translation_require_all_languages = translation_require_all_languages

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
        started = time.perf_counter()
        try:
            body = await self._post_chat_completions(
                payload,
                ai_layer="classification_reasoning",
                request_kind="classify_raw_item",
            )
        except Exception as exc:
            usage = self._build_usage(
                payload=payload,
                ai_layer="classification_reasoning",
                request_kind="classify_raw_item",
                started=started,
                success=False,
                error=exc,
            )
            raise ModelClientError(f"model request failed: {exc}", usage=usage) from exc

        content = extract_message_content(body)
        try:
            decoded = json.loads(content)
            result = ClassificationResult.model_validate(decoded)
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            usage = self._build_usage(
                payload=payload,
                body=body,
                output_text=content,
                ai_layer="classification_reasoning",
                request_kind="classify_raw_item",
                started=started,
                success=False,
                error=exc,
            )
            raise ModelClientError(f"invalid model response: {exc}", usage=usage) from exc

        usage = self._build_usage(
            payload=payload,
            body=body,
            output_text=content,
            ai_layer="classification_reasoning",
            request_kind="classify_raw_item",
            started=started,
            success=True,
        )
        return ModelResponse(
            provider=self.provider,
            api_provider=self.api_provider,
            model=self.model,
            result=result,
            raw_output=body,
            usage=usage,
        )

    async def summarize_and_translate(
        self,
        raw_item: RawItem,
        source: SourceMetadata,
        normalized: NormalizedItem,
        *,
        full_translation_required: bool = True,
        input_text: str | None = None,
        truncated: bool = False,
        taxonomy_context: TaxonomyContext | None = None,
    ) -> AuxiliaryModelResponse:
        taxonomy_context = taxonomy_context or TaxonomyContext()
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": auxiliary_text_system_prompt(
                        self.translation_output_languages,
                        language_labels=self.translation_language_labels,
                    ),
                },
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
                            "translation_scope": {
                                "summary_required": True,
                                "full_translation_required": full_translation_required,
                                "truncated_input": truncated,
                                "output_languages": list(self.translation_output_languages),
                                "require_all_languages": self.translation_require_all_languages,
                            },
                            "taxonomy_context": {
                                "content_categories": [
                                    {
                                        "key": category.key,
                                        "label_en": category.label_en,
                                        "description": category.description,
                                    }
                                    for category in taxonomy_context.categories
                                ],
                                "known_topic_tags": [
                                    {"key": tag.key, "label": tag.label, "tag_type": tag.tag_type}
                                    for tag in taxonomy_context.tags[:80]
                                ],
                            },
                            "raw_item": {
                                "title": raw_item.title,
                                "text_clean": input_text if input_text is not None else normalized.text_clean,
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
        self._apply_common_payload_options(
            payload,
            auxiliary_text_json_schema_response_format(
                self.translation_output_languages,
                require_all_languages=self.translation_require_all_languages,
            ),
        )
        started = time.perf_counter()
        try:
            body = await self._post_chat_completions(
                payload,
                ai_layer="translation_summary",
                request_kind="translate_summary",
            )
        except Exception as exc:
            usage = self._build_usage(
                payload=payload,
                ai_layer="translation_summary",
                request_kind="translate_summary",
                started=started,
                success=False,
                error=exc,
            )
            raise ModelClientError(f"auxiliary model request failed: {exc}", usage=usage) from exc

        content = extract_message_content(body)
        try:
            decoded = json.loads(content)
            result = AuxiliaryTextResult.model_validate(decoded)
            validate_auxiliary_text_result(
                result,
                languages=self.translation_output_languages,
                require_all_languages=self.translation_require_all_languages,
                full_translation_required=full_translation_required,
            )
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            usage = self._build_usage(
                payload=payload,
                body=body,
                output_text=content,
                ai_layer="translation_summary",
                request_kind="translate_summary",
                started=started,
                success=False,
                error=exc,
            )
            raise ModelClientError(f"invalid auxiliary model response: {exc}", usage=usage) from exc

        usage = self._build_usage(
            payload=payload,
            body=body,
            output_text=content,
            ai_layer="translation_summary",
            request_kind="translate_summary",
            started=started,
            success=True,
        )
        return AuxiliaryModelResponse(
            provider=self.provider,
            api_provider=self.api_provider,
            model=self.model,
            result=result,
            raw_output=body,
            usage=usage,
        )

    async def _post_chat_completions(
        self,
        payload: dict[str, Any],
        *,
        ai_layer: str,
        request_kind: str,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/chat/completions"
        request_started = time.perf_counter()
        logger.debug(
            "ai_model_api_request",
            extra={
                "ai_layer": ai_layer,
                "request_kind": request_kind,
                "route_name": self.provider,
                "api_provider": self.api_provider,
                "model": self.model,
                "endpoint": endpoint,
                "timeout_seconds": self.timeout_seconds,
                "headers": _sanitize_for_log(headers),
                "payload": _sanitize_for_log(payload),
            },
        )
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
            except Exception as exc:
                latency_ms = int((time.perf_counter() - request_started) * 1000)
                logger.debug(
                    "ai_model_api_error",
                    extra={
                        "ai_layer": ai_layer,
                        "request_kind": request_kind,
                        "route_name": self.provider,
                        "api_provider": self.api_provider,
                        "model": self.model,
                        "endpoint": endpoint,
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    exc_info=True,
                )
                raise

            latency_ms = int((time.perf_counter() - request_started) * 1000)
            response_text = response.text
            try:
                response_body = response.json()
            except json.JSONDecodeError:
                response_body = None

            logger.debug(
                "ai_model_api_response",
                extra={
                    "ai_layer": ai_layer,
                    "request_kind": request_kind,
                    "route_name": self.provider,
                    "api_provider": self.api_provider,
                    "model": self.model,
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "response_headers": _sanitize_for_log(dict(response.headers)),
                    "response_body": _sanitize_for_log(response_body if response_body is not None else response_text),
                },
            )
            response.raise_for_status()
            if response_body is None:
                return response.json()
            return response_body

    def _apply_common_payload_options(self, payload: dict[str, Any], schema_response_format: dict[str, Any]) -> None:
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.response_format == "json_schema":
            payload["response_format"] = schema_response_format
        elif self.response_format == "text":
            payload["response_format"] = {"type": "text"}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

    def _build_usage(
        self,
        *,
        payload: dict[str, Any],
        ai_layer: str,
        request_kind: str,
        started: float,
        success: bool,
        body: dict[str, Any] | None = None,
        output_text: str | None = None,
        error: Exception | None = None,
    ) -> AIModelCallUsage:
        latency_ms = int((time.perf_counter() - started) * 1000)
        response_usage = usage_from_response(body or {})
        input_tokens = response_usage["input_tokens"]
        output_tokens = response_usage["output_tokens"]
        total_tokens = response_usage["total_tokens"]
        usage_json = dict((body or {}).get("usage") or {})
        usage_estimated = False

        if input_tokens is None:
            input_tokens = estimate_messages_tokens(self.model, payload.get("messages") or [])
            usage_estimated = True
        if output_tokens is None and output_text is not None:
            output_tokens = estimate_text_tokens(self.model, output_text)
            usage_estimated = True
        if total_tokens is None and (input_tokens is not None or output_tokens is not None):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)
            usage_estimated = True

        if usage_estimated:
            usage_json["estimated"] = True

        return AIModelCallUsage(
            ai_layer=ai_layer,
            route_name=self.provider,
            provider=self.api_provider,
            model_name=self.model,
            request_kind=request_kind,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd(self.api_provider, self.model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            success=success,
            error_type=type(error).__name__ if error else None,
            error_message=str(error)[:2000] if error else None,
            response_format=self.response_format,
            usage_json=usage_json,
            request_hash=request_hash(payload),
        )


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
            translation_output_languages=settings.translation_output_languages,
            translation_language_labels=settings.translation_language_labels,
            translation_require_all_languages=settings.translation_require_all_languages,
        )

    raise ValueError(f"unsupported AUXILIARY_MODEL_ROUTE: {settings.auxiliary_model_route}")


def build_translation_model_clients(settings: Settings) -> list[OpenAIStyleModelClient]:
    if not settings.translation_model_enabled:
        return []

    base_url = settings.translation_model_base_url or settings.openrouter_model_base_url
    api_key = settings.translation_model_api_key or settings.openrouter_model_api_key
    if not base_url:
        raise ValueError("TRANSLATION_MODEL_BASE_URL is required when TRANSLATION_MODEL_ENABLED=true")
    if not api_key:
        raise ValueError("TRANSLATION_MODEL_API_KEY or OPENROUTER_MODEL_API_KEY is required for translation route")

    extra_headers = {}
    referer = settings.translation_http_referer or settings.openrouter_http_referer
    app_title = settings.translation_app_title or settings.openrouter_app_title
    if referer:
        extra_headers["HTTP-Referer"] = referer
    if app_title:
        extra_headers["X-Title"] = app_title

    clients = [
        OpenAIStyleModelClient(
            provider="translation_primary",
            base_url=base_url,
            api_key=api_key,
            model=settings.translation_primary_model_name,
            timeout_seconds=settings.model_timeout_seconds,
            response_format=settings.translation_model_response_format,
            reasoning_effort=settings.translation_model_reasoning_effort,
            extra_headers=extra_headers,
            translation_output_languages=settings.translation_output_languages,
            translation_language_labels=settings.translation_language_labels,
            translation_require_all_languages=settings.translation_require_all_languages,
        )
    ]

    if settings.translation_paid_fallback_enabled and settings.translation_fallback_model_name:
        clients.append(
            OpenAIStyleModelClient(
                provider="translation_paid_fallback",
                base_url=base_url,
                api_key=api_key,
                model=settings.translation_fallback_model_name,
                timeout_seconds=settings.model_timeout_seconds,
                response_format=settings.translation_model_response_format,
                reasoning_effort=settings.translation_model_reasoning_effort,
                extra_headers=extra_headers,
                translation_output_languages=settings.translation_output_languages,
                translation_language_labels=settings.translation_language_labels,
                translation_require_all_languages=settings.translation_require_all_languages,
            )
        )
    return clients


def extract_message_content(body: dict[str, Any]) -> str:
    message = body["choices"][0]["message"]
    content = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _sanitize_for_log(value: Any, *, key: str = "") -> Any:
    if _is_sensitive_log_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {str(item_key): _sanitize_for_log(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_log(item, key=key) for item in value]
    return value


def _is_sensitive_log_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized.endswith("_tokens") or normalized == "tokens":
        return False
    return any(part in normalized.split("_") for part in SENSITIVE_LOG_KEY_PARTS) or any(
        part in normalized
        for part in (
            "api_key",
            "access_token",
            "bearer_token",
        )
    )


def system_prompt() -> str:
    return (
        "You classify news items for an XAUUSD event radar. "
        "Return only valid JSON. Do not provide trading instructions, entries, stop loss, take profit, "
        "position sizing, buy, sell, long, short, bullish, or bearish recommendations. "
        "Do not predict market direction. "
        "Do not describe the event as a gold catalyst or imply whether gold should rise or fall. "
        "Return event summaries in a summaries array using BCP 47 language keys. "
        "Include exactly one zh-Hant summary and optionally one en summary. "
        "The zh-Hant summary must be concise, no more than 280 Chinese characters, and must not copy the full source text. "
        "The en summary must be concise, no more than 400 English characters, and must not copy the full source text. "
        "Decide whether the item is relevant to gold through safe_haven, real_rate, inflation, dollar, "
        "liquidity, oil, sanctions, geopolitics, or Fed expectations. "
        "The JSON schema is: "
        '{"is_relevant": boolean, "relevance_score": 0-100, "event_type": string, '
        '"source_stance": string|null, "claim_direction": "confirm|deny|warn|escalate|deescalate|neutral|unknown", '
        '"claim_text": string|null, "summaries": [{"language": "zh-Hant|en", "summary": string}], "actors": string[], '
        '"xauusd_impact_channel": string[], "requires_confirmation": boolean, "confidence": 0-100|null, '
        '"reason": string|null, "region": string|null, "primary_actor": string|null, '
        '"secondary_actor": string|null, "market_relevance": string|null}.'
    )


def auxiliary_text_system_prompt(
    output_languages: tuple[str, ...] = ("zh-Hant", "en"),
    *,
    language_labels: dict[str, str] | None = None,
) -> str:
    language_labels = language_labels or {}
    language_descriptions = ", ".join(
        f"{language} ({language_labels[language]})" if language_labels.get(language) else language
        for language in output_languages
    )
    return (
        "You summarize and translate news items for an XAUUSD event radar. "
        "Return only valid JSON. Do not wrap JSON in Markdown. Use Traditional Chinese for Chinese output. "
        "Do not provide trading instructions, entries, stop loss, take profit, position sizing, buy, sell, long, "
        "short, bullish, or bearish recommendations. Do not predict market direction. "
        "Do not decide whether a message is important, relevant, urgent, official, or market moving. "
        "You may classify the item's content taxonomy for timeline filtering only. "
        "Only follow translation_scope. "
        "Return translations as a translations array. Each translation object must contain language, summary, "
        "and full_translation. Use BCP 47 language codes. "
        f"Return exactly these output languages when translation_scope.require_all_languages is true: {language_descriptions}. "
        "The zh-Hant summary must be a concise Traditional Chinese news summary, no more than 280 Chinese characters, "
        "and must not copy the full source text. "
        "The en summary must be a concise English news summary, no more than 400 English characters, "
        "and must not copy the full source text. "
        "For other requested languages, write a concise news summary in that language and keep it under 400 characters. "
        "If full_translation_required is true, every requested language's full_translation field must contain a faithful "
        "full-text translation of the supplied text. If the original text is already English, the en full_translation "
        "may equal the supplied cleaned text. If the original text is already Chinese, the zh-Hant full_translation may equal "
        "the supplied cleaned text. If full_translation_required is false, return null for full_translation in every translation. "
        "Preserve names, places, institutions, numbers, dates, quoted claims, and uncertainty. "
        "content_category must be one of the enabled taxonomy_context.content_categories keys. "
        "If no controlled category fits, use other. Use routine for ordinary schedules, ceremonies, interviews, "
        "lifestyle, or non-policy background pieces when that category is available. "
        "topic_tags must contain 0-12 short lowercase topic slugs useful for filtering. Prefer known_topic_tags keys "
        "when they fit, but you may add new short topic tags when needed. "
        "mentioned_actors must contain 0-12 named people, countries, agencies, military units, institutions, or "
        "organizations explicitly mentioned in the item. "
        "If truncated_input is true, mention in notes that full translation is based on truncated input. "
        "Do not add facts that are not in the input. "
        "The JSON schema is: "
        '{"translations": [{"language": string, "summary": string|null, "full_translation": string|null}], '
        '"content_category": string|null, "topic_tags": string[], '
        '"mentioned_actors": string[], "detected_language": string|null, "notes": string|null}.'
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
                    "summaries": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 2,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "language": {"type": "string", "enum": ["zh-Hant", "en"]},
                                "summary": {"type": "string", "maxLength": 400},
                            },
                            "required": ["language", "summary"],
                        },
                    },
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
                    "summaries",
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


def auxiliary_text_json_schema_response_format(
    output_languages: tuple[str, ...] = ("zh-Hant", "en"),
    *,
    require_all_languages: bool = True,
) -> dict[str, Any]:
    translation_items: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "language": {"type": "string"},
            "summary": {"type": ["string", "null"]},
            "full_translation": {"type": ["string", "null"]},
        },
        "required": ["language", "summary", "full_translation"],
    }
    if output_languages:
        translation_items["properties"]["language"]["enum"] = list(output_languages)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "xauusd_auxiliary_text",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "translations": {
                        "type": "array",
                        "minItems": len(output_languages) if require_all_languages else 1,
                        "maxItems": 8,
                        "items": translation_items,
                    },
                    "content_category": {
                        "type": ["string", "null"],
                    },
                    "topic_tags": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                    "mentioned_actors": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                    "detected_language": {"type": ["string", "null"]},
                    "notes": {"type": ["string", "null"]},
                },
                "required": [
                    "translations",
                    "content_category",
                    "topic_tags",
                    "mentioned_actors",
                    "detected_language",
                    "notes",
                ],
            },
        },
    }


def validate_auxiliary_text_result(
    result: AuxiliaryTextResult,
    *,
    languages: tuple[str, ...],
    require_all_languages: bool,
    full_translation_required: bool,
) -> None:
    if not require_all_languages:
        return
    missing_languages: list[str] = []
    incomplete_languages: list[str] = []
    for language in languages:
        translation = result.translation_for(language)
        if translation is None:
            missing_languages.append(language)
            continue
        if not translation.summary:
            incomplete_languages.append(language)
            continue
        if full_translation_required and not translation.full_translation:
            incomplete_languages.append(language)
    if missing_languages or incomplete_languages:
        parts: list[str] = []
        if missing_languages:
            parts.append(f"missing languages: {', '.join(missing_languages)}")
        if incomplete_languages:
            parts.append(f"incomplete languages: {', '.join(incomplete_languages)}")
        raise ValueError("; ".join(parts))
