from __future__ import annotations

from .model_contracts import ModelClient
from .openrouter_client import OpenRouterClient
from .ollama_cloud_client import OllamaCloudClient
from .settings import Settings


def _token_limits(settings: Settings, *, translation: bool = False) -> dict[str, int]:
    return dict(max_input_tokens=settings.ai_max_input_tokens,
                max_output_tokens=settings.translation_max_output_tokens if translation else settings.classification_max_output_tokens,
                summary_output_tokens=settings.summary_max_output_tokens)

def build_model_client(settings: Settings) -> ModelClient:
    if settings.model_route == "cloud_small" and settings.classification_model_provider == "ollama_cloud":
        return OllamaCloudClient(
            provider="cloud_small", base_url=settings.ollama_cloud_base_url, api_key=settings.ollama_api_key,
            model=settings.ollama_cloud_classification_model,
            timeout_seconds=settings.ollama_cloud_classification_timeout_seconds,
            reasoning_effort=settings.ollama_cloud_classification_reasoning_effort,
            **_token_limits(settings),
        )

    if settings.model_route == "cloud_small":
        if not settings.cloud_model_base_url or not settings.cloud_model_name:
            raise ValueError("CLOUD_MODEL_BASE_URL and CLOUD_MODEL_NAME are required for cloud_small route")
        if not settings.cloud_model_api_key:
            raise ValueError("CLOUD_MODEL_API_KEY is required for cloud_small route")
        return OpenRouterClient(
            provider="cloud_small",
            base_url=settings.cloud_model_base_url,
            api_key=settings.cloud_model_api_key,
            model=settings.cloud_model_name,
            timeout_seconds=settings.cloud_model_timeout_seconds or settings.model_timeout_seconds,
            response_format=settings.cloud_model_response_format,
            reasoning_effort=settings.cloud_model_reasoning_effort,
            **_token_limits(settings),
            classification_provider_options={
                "sort": "price",
                "require_parameters": True,
                "max_price": {"prompt": settings.cloud_model_max_prompt_price,
                              "completion": settings.cloud_model_max_completion_price},
            },
        )

    raise ValueError(f"unsupported MODEL_ROUTE: {settings.model_route}")

def build_auxiliary_model_client(settings: Settings) -> ModelClient | None:
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
        return OpenRouterClient(
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
            **_token_limits(settings, translation=True),
        )

    raise ValueError(f"unsupported AUXILIARY_MODEL_ROUTE: {settings.auxiliary_model_route}")

def build_translation_model_clients(settings: Settings) -> list[ModelClient]:
    if not settings.translation_model_enabled:
        return []
    clients = [_build_translation_client(settings, api_provider=settings.translation_model_provider,
                                         route_name="translation_primary")]
    if settings.translation_paid_fallback_enabled:
        if not settings.translation_fallback_model_name:
            raise ValueError("TRANSLATION_FALLBACK_MODEL_NAME is required when translation fallback is enabled")
        clients.append(_build_translation_client(
            settings, api_provider=settings.translation_fallback_provider or settings.translation_model_provider,
            route_name="translation_paid_fallback", model=settings.translation_fallback_model_name,
        ))
    return clients


def _build_translation_client(settings: Settings, *, api_provider: str, route_name: str,
                              model: str | None = None) -> ModelClient:
    if api_provider == "ollama_cloud":
        return OllamaCloudClient(
            provider=route_name, base_url=settings.ollama_cloud_base_url, api_key=settings.ollama_api_key,
            model=model or settings.ollama_cloud_translation_model,
            timeout_seconds=settings.ollama_cloud_translation_timeout_seconds,
            reasoning_effort=settings.ollama_cloud_translation_reasoning_effort,
            **_token_limits(settings, translation=True),
            translation_output_languages=settings.translation_output_languages,
            translation_language_labels=settings.translation_language_labels,
            translation_require_all_languages=settings.translation_require_all_languages,
        )

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
    return OpenRouterClient(
        provider=route_name, base_url=base_url, api_key=api_key,
        model=model or settings.translation_primary_model_name,
        timeout_seconds=settings.translation_model_timeout_seconds or settings.model_timeout_seconds,
        response_format=settings.translation_model_response_format,
        reasoning_effort=settings.translation_model_reasoning_effort,
        extra_headers=extra_headers,
        translation_output_languages=settings.translation_output_languages,
        translation_language_labels=settings.translation_language_labels,
        translation_require_all_languages=settings.translation_require_all_languages,
        **_token_limits(settings, translation=True),
        translation_provider_options={"sort": "price", "require_parameters": True,
            "max_price": {"prompt": settings.translation_max_prompt_price,
                          "completion": settings.translation_max_completion_price}},
    )
