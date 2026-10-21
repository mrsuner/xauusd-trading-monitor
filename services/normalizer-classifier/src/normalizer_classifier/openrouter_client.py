from __future__ import annotations

from typing import Any

from . import model_tasks
from .model_transport import ChatCompletionTransport
from .models import AIModelCallUsage, AuxiliaryModelResponse, ModelResponse, NormalizedItem, RawItem, SourceMetadata
from .taxonomy import TaxonomyContext
from .usage import build_model_call_usage


class OpenRouterClient:
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
        translation_provider_options: dict[str, Any] | None = None,
        classification_provider_options: dict[str, Any] | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("an OpenRouter API key is required")
        if not model or not model.strip():
            raise ValueError("an explicit OpenRouter model is required")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.api_provider = "openrouter"
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format
        self.reasoning_effort = reasoning_effort
        self.extra_headers = extra_headers or {}
        self.translation_output_languages = translation_output_languages
        self.translation_language_labels = translation_language_labels or {}
        self.translation_require_all_languages = translation_require_all_languages
        self.translation_provider_options = translation_provider_options
        self.classification_provider_options = classification_provider_options
        self.transport = ChatCompletionTransport(
            base_url=self.base_url, api_key=self.api_key, timeout_seconds=self.timeout_seconds,
            provider=self.provider, api_provider=self.api_provider, model=self.model, extra_headers=self.extra_headers,
        )

    async def classify(self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem,
                       *, taxonomy_context: TaxonomyContext | None = None,
                       domain_modules: list[str] | None = None, enabled_domain_keys: list[str] | None = None) -> ModelResponse:
        return await model_tasks.classify(self, raw_item, source, normalized, taxonomy_context=taxonomy_context,
                                          domain_modules=domain_modules, enabled_domain_keys=enabled_domain_keys)

    async def summarize_and_translate(self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem,
                                     *, full_translation_required: bool = True, input_text: str | None = None,
                                     truncated: bool = False, taxonomy_context: TaxonomyContext | None = None) -> AuxiliaryModelResponse:
        return await model_tasks.summarize_and_translate(self, raw_item, source, normalized,
            full_translation_required=full_translation_required, input_text=input_text, truncated=truncated,
            taxonomy_context=taxonomy_context)

    async def _post_chat_completions(self, payload: dict[str, Any], *, ai_layer: str, request_kind: str) -> dict[str, Any]:
        return await self.transport.post(payload, ai_layer=ai_layer, request_kind=request_kind)

    def _build_usage(self, **kwargs: Any) -> AIModelCallUsage:
        return build_model_call_usage(route_name=self.provider, api_provider=self.api_provider, model=self.model,
                                      response_format=self.response_format, **kwargs)

    def _extract_content(self, body: dict[str, Any]) -> str:
        message = body["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
        if isinstance(content, list):
            return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        return str(content)

    def _prepare_payload(self, payload: dict[str, Any], schema_response_format: dict[str, Any], *, ai_layer: str) -> None:
        # Luna does not advertise temperature support on OpenRouter. Sending it
        # with require_parameters=true leaves no eligible provider.
        if self.model.rsplit("/", 1)[-1] == "gpt-6-luna":
            payload.pop("temperature", None)
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.response_format == "json_schema":
            payload["response_format"] = schema_response_format
        elif self.response_format == "text":
            payload["response_format"] = {"type": "text"}
        if self.reasoning_effort == "none":
            payload["reasoning"] = {"enabled": False}
        elif self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        options = self.classification_provider_options if ai_layer == "classification_reasoning" else self.translation_provider_options
        if options:
            payload["provider"] = options
