from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from . import model_tasks
from .model_transport import ChatCompletionTransport
from .models import AIModelCallUsage, AuxiliaryModelResponse, ModelResponse, NormalizedItem, RawItem, SourceMetadata
from .taxonomy import TaxonomyContext
from .usage import build_model_call_usage


class OllamaCloudClient:
    def __init__(self, *, provider: str, base_url: str, api_key: str | None, model: str | None,
                 timeout_seconds: float, reasoning_effort: str | None = None,
                 translation_output_languages: tuple[str, ...] = ("zh-Hant", "en"),
                 translation_language_labels: dict[str, str] | None = None,
                 translation_require_all_languages: bool = True) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("OLLAMA_API_KEY is required for Ollama Cloud")
        if not model or not model.strip():
            raise ValueError("an explicit Ollama Cloud model is required for the selected layer")
        # This provider targets the direct Cloud API, never a local Ollama daemon.
        url = urlsplit(base_url)
        if (url.scheme != "https" or url.hostname != "ollama.com" or url.path.rstrip("/") != "/v1"
                or url.username or url.password or url.query or url.fragment or url.port not in {None, 443}):
            raise ValueError("OLLAMA_CLOUD_BASE_URL must be https://ollama.com/v1")
        self.provider = provider
        self.api_provider = "ollama_cloud"
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.response_format = "prompt_json_schema"
        self.translation_output_languages = translation_output_languages
        self.translation_language_labels = translation_language_labels or {}
        self.translation_require_all_languages = translation_require_all_languages
        self.transport = ChatCompletionTransport(
            base_url=self.base_url, api_key=self.api_key, timeout_seconds=self.timeout_seconds,
            provider=self.provider, api_provider=self.api_provider, model=self.model, extra_headers={},
        )

    async def classify(self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem,
                       *, taxonomy_context: TaxonomyContext | None = None,
                       domain_modules: list[str] | None = None, enabled_domain_keys: list[str] | None = None) -> ModelResponse:
        return await model_tasks.classify(self, raw_item, source, normalized, taxonomy_context=taxonomy_context,
                                          domain_modules=domain_modules, enabled_domain_keys=enabled_domain_keys)

    async def summarize_and_translate(self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem,
                                     *, full_translation_required: bool = True, input_text: str | None = None,
                                     truncated: bool = False, taxonomy_context: TaxonomyContext | None = None,
                                     script_repair_fields: tuple[str, ...] = ()) -> AuxiliaryModelResponse:
        return await model_tasks.summarize_and_translate(self, raw_item, source, normalized,
            full_translation_required=full_translation_required, input_text=input_text, truncated=truncated,
            taxonomy_context=taxonomy_context, script_repair_fields=script_repair_fields)

    async def _post_chat_completions(self, payload: dict[str, Any], *, ai_layer: str, request_kind: str) -> dict[str, Any]:
        return await self.transport.post(payload, ai_layer=ai_layer, request_kind=request_kind)

    def _build_usage(self, **kwargs: Any) -> AIModelCallUsage:
        return build_model_call_usage(route_name=self.provider, api_provider=self.api_provider, model=self.model,
                                      response_format=self.response_format, **kwargs)

    def _prepare_payload(self, payload: dict[str, Any], schema_response_format: dict[str, Any], *, ai_layer: str) -> None:
        # Cloud has no enforced structured outputs. Keep the schema in the prompt,
        # then validate the final answer using the same business contract.
        schema = schema_response_format["json_schema"]["schema"]
        payload["messages"][0]["content"] += (
            " Return exactly one JSON object matching this schema. No Markdown, commentary, or reasoning in the answer. "
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        )
        if ai_layer == "translation_summary":
            # Leave headroom below the shared validator's character limits.
            payload["messages"][0]["content"] += (
                " Write each summary as one short sentence. Aim for at most 120 characters for zh-Hant "
                "and 220 characters for each other language, counting spaces and punctuation. "
                "Put supporting details in full_translation rather than the summary. "
                "Preserve attribution and uncertainty even in the short summary. "
                "Check summary length before returning JSON and shorten it if needed."
                " Validate summary and full_translation independently for every output language. "
                "When full_translation_required is true, translate the entire supplied text in each "
                "language's full_translation even when its summary is already translated. "
                "Copy source text only into the full_translation whose target language matches the source. "
                "For an English source, only en may reuse English text: zh-Hant, th, and ja "
                "full_translation must be Traditional Chinese, Thai, and Japanese respectively. "
                "Names and handles may remain unchanged within an otherwise translated sentence."
            )
        payload["stream"] = False
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

    def _extract_content(self, body: dict[str, Any]) -> str:
        choice = body["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if (choice.get("finish_reason") != "stop" or message.get("refusal")
                or not isinstance(content, str) or not content.strip()):
            raise ValueError("incomplete, refused, or missing Ollama Cloud final answer")
        return content
