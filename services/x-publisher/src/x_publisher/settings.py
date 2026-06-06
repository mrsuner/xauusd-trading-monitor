from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    service_name: str = Field(default="x-publisher", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    enabled: bool = Field(default=False, alias="X_PUBLISHER_ENABLED")
    dry_run: bool = Field(default=True, alias="X_PUBLISHER_DRY_RUN")
    api_base_url: str = Field(default="https://api.twitter.com/2", alias="X_API_BASE_URL")
    api_key: str | None = Field(default=None, alias="X_API_KEY")
    api_secret: str | None = Field(default=None, alias="X_API_SECRET")
    access_token: str | None = Field(default=None, alias="X_ACCESS_TOKEN")
    access_token_secret: str | None = Field(default=None, alias="X_ACCESS_TOKEN_SECRET")
    bearer_token: str | None = Field(default=None, alias="X_BEARER_TOKEN")
    post_max_chars: int = Field(default=260, alias="X_POST_MAX_CHARS")
    min_severity: str = Field(default="A", alias="X_PUBLISHER_MIN_SEVERITY")
    include_b_events: bool = Field(default=False, alias="X_PUBLISHER_INCLUDE_B_EVENTS")
    max_per_hour: int = Field(default=10, alias="X_PUBLISHER_MAX_PER_HOUR")
    max_per_day: int = Field(default=50, alias="X_PUBLISHER_MAX_PER_DAY")
    max_attempts: int = Field(default=4, alias="X_PUBLISHER_MAX_ATTEMPTS")
    retry_backoff_seconds: int = Field(default=300, alias="X_PUBLISHER_RETRY_BACKOFF_SECONDS")
    poll_interval_seconds: float = Field(default=30.0, alias="PUBLISHER_POLL_INTERVAL_SECONDS")
    batch_size: int = Field(default=1, alias="X_PUBLISHER_BATCH_SIZE")
    provider_timeout_seconds: float = Field(default=10.0, alias="X_PUBLISHER_PROVIDER_TIMEOUT_SECONDS")
    lock_timeout_seconds: int = Field(default=300, alias="X_PUBLISHER_LOCK_TIMEOUT_SECONDS")
    require_source_link: bool = Field(default=True, alias="X_PUBLISHER_REQUIRE_SOURCE_LINK")
    min_generated_at: datetime | None = Field(default=None, alias="X_PUBLISHER_MIN_GENERATED_AT")
    semantic_dedupe_enabled: bool = Field(default=False, alias="X_SEMANTIC_DEDUPE_ENABLED")
    semantic_dedupe_window_minutes: int = Field(default=30, alias="X_SEMANTIC_DEDUPE_WINDOW_MINUTES")
    semantic_dedupe_candidate_limit: int = Field(default=8, alias="X_SEMANTIC_DEDUPE_CANDIDATE_LIMIT")
    semantic_dedupe_threshold: int = Field(default=85, alias="X_SEMANTIC_DEDUPE_THRESHOLD")
    semantic_dedupe_model_base_url: str | None = Field(default=None, alias="X_SEMANTIC_DEDUPE_MODEL_BASE_URL")
    semantic_dedupe_model_api_key: str | None = Field(default=None, alias="X_SEMANTIC_DEDUPE_MODEL_API_KEY")
    semantic_dedupe_model_name: str | None = Field(default=None, alias="X_SEMANTIC_DEDUPE_MODEL_NAME")
    semantic_dedupe_fallback_model_name: str | None = Field(default=None, alias="X_SEMANTIC_DEDUPE_FALLBACK_MODEL_NAME")
    semantic_dedupe_paid_fallback_enabled: bool = Field(
        default=True,
        alias="X_SEMANTIC_DEDUPE_PAID_FALLBACK_ENABLED",
    )
    semantic_dedupe_response_format: str = Field(default="json_object", alias="X_SEMANTIC_DEDUPE_RESPONSE_FORMAT")
    semantic_dedupe_reasoning_effort: str | None = Field(default=None, alias="X_SEMANTIC_DEDUPE_REASONING_EFFORT")
    semantic_dedupe_http_referer: str | None = Field(default=None, alias="X_SEMANTIC_DEDUPE_HTTP_REFERER")
    semantic_dedupe_app_title: str | None = Field(default="XAUUSD Event Radar", alias="X_SEMANTIC_DEDUPE_APP_TITLE")

    translation_model_base_url: str | None = Field(default=None, alias="TRANSLATION_MODEL_BASE_URL")
    translation_model_api_key: str | None = Field(default=None, alias="TRANSLATION_MODEL_API_KEY")
    translation_primary_model_name: str | None = Field(default=None, alias="TRANSLATION_PRIMARY_MODEL_NAME")
    translation_fallback_model_name: str | None = Field(default=None, alias="TRANSLATION_FALLBACK_MODEL_NAME")
    translation_paid_fallback_enabled: bool = Field(default=True, alias="TRANSLATION_PAID_FALLBACK_ENABLED")
    translation_model_response_format: str | None = Field(default=None, alias="TRANSLATION_MODEL_RESPONSE_FORMAT")
    translation_model_reasoning_effort: str | None = Field(default=None, alias="TRANSLATION_MODEL_REASONING_EFFORT")
    translation_http_referer: str | None = Field(default=None, alias="TRANSLATION_HTTP_REFERER")
    translation_app_title: str | None = Field(default=None, alias="TRANSLATION_APP_TITLE")
    openrouter_model_api_key: str | None = Field(default=None, alias="OPENROUTER_MODEL_API_KEY")

    @field_validator(
        "api_key",
        "api_secret",
        "access_token",
        "access_token_secret",
        "bearer_token",
        "semantic_dedupe_model_base_url",
        "semantic_dedupe_model_api_key",
        "semantic_dedupe_model_name",
        "semantic_dedupe_fallback_model_name",
        "semantic_dedupe_reasoning_effort",
        "semantic_dedupe_http_referer",
        "semantic_dedupe_app_title",
        "translation_model_base_url",
        "translation_model_api_key",
        "translation_primary_model_name",
        "translation_fallback_model_name",
        "translation_model_response_format",
        "translation_model_reasoning_effort",
        "translation_http_referer",
        "translation_app_title",
        "openrouter_model_api_key",
    )
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("api_base_url", "semantic_dedupe_model_base_url", "translation_model_base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.rstrip("/")

    @field_validator("min_severity")
    @classmethod
    def validate_min_severity(cls, value: str) -> str:
        if value not in {"S", "A", "B", "C"}:
            raise ValueError("min_severity must be S, A, B, or C")
        return value

    @field_validator("retry_backoff_seconds", "max_per_hour", "max_per_day")
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator(
        "max_attempts",
        "batch_size",
        "lock_timeout_seconds",
        "post_max_chars",
        "semantic_dedupe_window_minutes",
        "semantic_dedupe_candidate_limit",
    )
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("semantic_dedupe_threshold")
    @classmethod
    def validate_similarity_threshold(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("semantic_dedupe_threshold must be between 0 and 100")
        return value

    @field_validator("semantic_dedupe_response_format")
    @classmethod
    def validate_response_format(cls, value: str) -> str:
        allowed = {"none", "json_object", "json_schema", "text"}
        if value not in allowed:
            raise ValueError(f"response format must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("poll_interval_seconds", "provider_timeout_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value
