from __future__ import annotations

import json
import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
DEFAULT_TRANSLATION_OUTPUT_LANGUAGES = ("zh-Hant", "en")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")
    db_pool_min_size: int = Field(default=1, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=0, alias="DB_POOL_MAX_SIZE")
    poll_interval_seconds: float = Field(default=2.0, alias="POLL_INTERVAL_SECONDS")
    stale_task_timeout_seconds: int = Field(default=900, alias="STALE_TASK_TIMEOUT_SECONDS")
    model_route: str = Field(default="cloud_small", alias="MODEL_ROUTE")

    local_model_base_url: str | None = Field(default=None, alias="LOCAL_MODEL_BASE_URL")
    local_model_api_key: str | None = Field(default=None, alias="LOCAL_MODEL_API_KEY")
    local_model_name: str | None = Field(default=None, alias="LOCAL_MODEL_NAME")
    local_model_response_format: str = Field(default="none", alias="LOCAL_MODEL_RESPONSE_FORMAT")
    local_model_reasoning_effort: str | None = Field(default=None, alias="LOCAL_MODEL_REASONING_EFFORT")

    cloud_model_base_url: str | None = Field(default="https://api.openai.com/v1", alias="CLOUD_MODEL_BASE_URL")
    cloud_model_api_key: str | None = Field(default=None, alias="CLOUD_MODEL_API_KEY")
    cloud_model_name: str | None = Field(default=None, alias="CLOUD_MODEL_NAME")
    cloud_model_response_format: str = Field(default="json_object", alias="CLOUD_MODEL_RESPONSE_FORMAT")
    cloud_model_reasoning_effort: str | None = Field(default=None, alias="CLOUD_MODEL_REASONING_EFFORT")

    auxiliary_model_enabled: bool = Field(default=False, alias="AUXILIARY_MODEL_ENABLED")
    auxiliary_model_route: str = Field(default="disabled", alias="AUXILIARY_MODEL_ROUTE")

    openrouter_model_base_url: str | None = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_MODEL_BASE_URL"
    )
    openrouter_model_api_key: str | None = Field(default=None, alias="OPENROUTER_MODEL_API_KEY")
    openrouter_model_name: str | None = Field(default=None, alias="OPENROUTER_MODEL_NAME")
    openrouter_model_response_format: str = Field(default="json_object", alias="OPENROUTER_MODEL_RESPONSE_FORMAT")
    openrouter_model_reasoning_effort: str | None = Field(default=None, alias="OPENROUTER_MODEL_REASONING_EFFORT")
    openrouter_http_referer: str | None = Field(default=None, alias="OPENROUTER_HTTP_REFERER")
    openrouter_app_title: str | None = Field(default="XAUUSD Event Radar", alias="OPENROUTER_APP_TITLE")

    translation_model_enabled: bool = Field(default=True, alias="TRANSLATION_MODEL_ENABLED")
    translation_model_base_url: str | None = Field(
        default="https://openrouter.ai/api/v1", alias="TRANSLATION_MODEL_BASE_URL"
    )
    translation_model_api_key: str | None = Field(default=None, alias="TRANSLATION_MODEL_API_KEY")
    translation_primary_model_name: str = Field(
        default="openai/gpt-oss-20b:free", alias="TRANSLATION_PRIMARY_MODEL_NAME"
    )
    translation_fallback_model_name: str | None = Field(
        default="openai/gpt-oss-20b", alias="TRANSLATION_FALLBACK_MODEL_NAME"
    )
    translation_paid_fallback_enabled: bool = Field(default=True, alias="TRANSLATION_PAID_FALLBACK_ENABLED")
    translation_model_response_format: str = Field(default="none", alias="TRANSLATION_MODEL_RESPONSE_FORMAT")
    translation_model_reasoning_effort: str | None = Field(default=None, alias="TRANSLATION_MODEL_REASONING_EFFORT")
    translation_http_referer: str | None = Field(default=None, alias="TRANSLATION_HTTP_REFERER")
    translation_app_title: str | None = Field(default="XAUUSD Event Radar", alias="TRANSLATION_APP_TITLE")
    translation_output_languages_raw: str = Field(default="zh-Hant,en", alias="TRANSLATION_OUTPUT_LANGUAGES")
    translation_language_labels_json: str | None = Field(default=None, alias="TRANSLATION_LANGUAGE_LABELS_JSON")
    translation_require_all_languages: bool = Field(default=True, alias="TRANSLATION_REQUIRE_ALL_LANGUAGES")
    translation_default_max_chars: int = Field(default=20000, alias="TRANSLATION_DEFAULT_MAX_CHARS")
    translation_high_priority_max_chars: int = Field(default=100000, alias="TRANSLATION_HIGH_PRIORITY_MAX_CHARS")
    translation_single_call_max_chars: int = Field(default=100000, alias="TRANSLATION_SINGLE_CALL_MAX_CHARS")
    max_classification_calls_per_run: int = Field(default=0, alias="MAX_CLASSIFICATION_CALLS_PER_RUN")
    max_translation_calls_per_run: int = Field(default=0, alias="MAX_TRANSLATION_CALLS_PER_RUN")
    max_translation_paid_fallback_calls_per_run: int = Field(
        default=0, alias="MAX_TRANSLATION_PAID_FALLBACK_CALLS_PER_RUN"
    )

    model_timeout_seconds: float = Field(default=30.0, alias="MODEL_TIMEOUT_SECONDS")
    max_model_calls_per_run: int = Field(default=0, alias="MAX_MODEL_CALLS_PER_RUN")
    relevance_threshold_event: int = Field(default=70, alias="RELEVANCE_THRESHOLD_EVENT")
    max_attempts: int = Field(default=3, alias="MAX_ATTEMPTS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("worker_concurrency")
    @classmethod
    def validate_worker_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("WORKER_CONCURRENCY must be >= 1")
        return value

    @field_validator("db_pool_min_size")
    @classmethod
    def validate_db_pool_min_size(cls, value: int) -> int:
        if value < 0:
            raise ValueError("DB_POOL_MIN_SIZE must be >= 0")
        return value

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_db_pool_max_size(cls, value: int) -> int:
        if value < 0:
            raise ValueError("DB_POOL_MAX_SIZE must be >= 0")
        return value

    @field_validator("stale_task_timeout_seconds")
    @classmethod
    def validate_stale_task_timeout_seconds(cls, value: int) -> int:
        if value < 60:
            raise ValueError("STALE_TASK_TIMEOUT_SECONDS must be >= 60")
        return value

    @field_validator("max_model_calls_per_run")
    @classmethod
    def validate_max_model_calls_per_run(cls, value: int) -> int:
        if value < 0:
            raise ValueError("model call budgets must be >= 0")
        return value

    @field_validator(
        "max_classification_calls_per_run",
        "max_translation_calls_per_run",
        "max_translation_paid_fallback_calls_per_run",
        "translation_default_max_chars",
        "translation_high_priority_max_chars",
        "translation_single_call_max_chars",
    )
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("relevance_threshold_event")
    @classmethod
    def validate_threshold(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("RELEVANCE_THRESHOLD_EVENT must be between 0 and 100")
        return value

    @field_validator(
        "local_model_response_format",
        "cloud_model_response_format",
        "openrouter_model_response_format",
        "translation_model_response_format",
    )
    @classmethod
    def validate_response_format(cls, value: str) -> str:
        allowed = {"none", "json_object", "json_schema", "text"}
        if value not in allowed:
            raise ValueError(f"response format must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator(
        "local_model_reasoning_effort",
        "cloud_model_reasoning_effort",
        "openrouter_model_reasoning_effort",
        "openrouter_http_referer",
        "openrouter_app_title",
        "translation_model_api_key",
        "translation_fallback_model_name",
        "translation_model_reasoning_effort",
        "translation_http_referer",
        "translation_app_title",
        "translation_language_labels_json",
    )
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value

    @field_validator("translation_output_languages_raw")
    @classmethod
    def validate_translation_output_languages_raw(cls, value: str) -> str:
        parse_language_list(value, env_name="TRANSLATION_OUTPUT_LANGUAGES")
        return value

    @property
    def translation_output_languages(self) -> tuple[str, ...]:
        return parse_language_list(self.translation_output_languages_raw, env_name="TRANSLATION_OUTPUT_LANGUAGES")

    @property
    def translation_language_labels(self) -> dict[str, str]:
        if not self.translation_language_labels_json:
            return {}
        try:
            decoded = json.loads(self.translation_language_labels_json)
        except json.JSONDecodeError as exc:
            raise ValueError("TRANSLATION_LANGUAGE_LABELS_JSON must be valid JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("TRANSLATION_LANGUAGE_LABELS_JSON must be a JSON object")
        labels: dict[str, str] = {}
        for key, value in decoded.items():
            language = str(key).strip()
            if language not in self.translation_output_languages:
                raise ValueError("TRANSLATION_LANGUAGE_LABELS_JSON keys must match TRANSLATION_OUTPUT_LANGUAGES")
            label = str(value).strip()
            if label:
                labels[language] = label
        return labels


def parse_language_list(value: str | None, *, env_name: str) -> tuple[str, ...]:
    raw_languages = [item.strip() for item in str(value or "").split(",")]
    languages: list[str] = []
    for language in raw_languages:
        if not language:
            continue
        if not LANGUAGE_CODE_RE.match(language):
            raise ValueError(f"{env_name} contains invalid BCP 47 language code: {language}")
        if language in languages:
            raise ValueError(f"{env_name} contains duplicate language code: {language}")
        languages.append(language)
    if not languages:
        raise ValueError(f"{env_name} must contain at least one language code")
    if len(languages) > 8:
        raise ValueError(f"{env_name} supports at most 8 languages")
    return tuple(languages)
