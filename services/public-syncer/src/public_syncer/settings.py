from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    service_name: str = Field(default="public-syncer", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    enabled: bool = Field(default=False, alias="PUBLIC_SYNCER_ENABLED")
    dry_run: bool = Field(default=True, alias="PUBLIC_SYNCER_DRY_RUN")
    public_api_base_url: str | None = Field(default=None, alias="PUBLIC_API_BASE_URL")
    public_ingest_path: str = Field(default="/ingest/events", alias="PUBLIC_INGEST_PATH")
    public_raw_ingest_path: str = Field(default="/ingest/raw-items", alias="PUBLIC_RAW_INGEST_PATH")
    auth_mode: str = Field(default="hmac", alias="PUBLIC_SYNC_AUTH_MODE")
    sync_key_id: str | None = Field(default=None, alias="PUBLIC_SYNC_KEY_ID")
    sync_secret: str | None = Field(default=None, alias="PUBLIC_SYNC_SECRET")
    sync_api_key: str | None = Field(default=None, alias="PUBLIC_SYNC_API_KEY")
    public_sync_languages_raw: str = Field(default="zh-Hant,en", alias="PUBLIC_SYNC_LANGUAGES")

    batch_size: int = Field(default=10, alias="PUBLIC_SYNCER_BATCH_SIZE")
    max_attempts: int = Field(default=5, alias="PUBLIC_SYNCER_MAX_ATTEMPTS")
    retry_backoff_seconds: int = Field(default=60, alias="PUBLIC_SYNCER_RETRY_BACKOFF_SECONDS")
    max_per_minute: int = Field(default=60, alias="PUBLIC_SYNCER_MAX_PER_MINUTE")
    provider_timeout_seconds: float = Field(default=10.0, alias="PUBLIC_SYNCER_PROVIDER_TIMEOUT_SECONDS")
    lock_timeout_seconds: int = Field(default=300, alias="PUBLIC_SYNCER_LOCK_TIMEOUT_SECONDS")
    poll_interval_seconds: float = Field(default=10.0, alias="PUBLIC_SYNCER_POLL_INTERVAL_SECONDS")

    raw_items_enabled: bool = Field(default=False, alias="PUBLIC_SYNC_RAW_ITEMS_ENABLED")
    raw_backfill_enabled: bool = Field(default=False, alias="PUBLIC_RAW_BACKFILL_ENABLED")
    raw_batch_size: int = Field(default=20, alias="PUBLIC_RAW_BATCH_SIZE")
    raw_max_per_minute: int = Field(default=30, alias="PUBLIC_RAW_MAX_PER_MINUTE")
    raw_min_relevance_score: int = Field(default=50, alias="PUBLIC_RAW_MIN_RELEVANCE_SCORE")
    raw_max_original_chars: int = Field(default=4000, alias="PUBLIC_RAW_MAX_ORIGINAL_CHARS")
    raw_max_translation_chars: int = Field(default=8000, alias="PUBLIC_RAW_MAX_TRANSLATION_CHARS")
    public_raw_sync_languages_raw: str = Field(default="zh-Hant,en", alias="PUBLIC_RAW_SYNC_LANGUAGES")

    @field_validator("public_api_base_url", "sync_key_id", "sync_secret", "sync_api_key")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("public_api_base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @field_validator("public_ingest_path", "public_raw_ingest_path")
    @classmethod
    def normalize_ingest_path(cls, value: str) -> str:
        if not value.startswith("/"):
            return f"/{value}"
        return value

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"hmac", "bearer"}:
            raise ValueError("PUBLIC_SYNC_AUTH_MODE must be hmac or bearer")
        return normalized

    @field_validator("batch_size", "max_attempts", "lock_timeout_seconds", "raw_batch_size")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("retry_backoff_seconds", "max_per_minute", "raw_max_per_minute")
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("raw_min_relevance_score")
    @classmethod
    def validate_score(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("value must be between 0 and 100")
        return value

    @field_validator("raw_max_original_chars", "raw_max_translation_chars")
    @classmethod
    def validate_content_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("public_sync_languages_raw", "public_raw_sync_languages_raw")
    @classmethod
    def validate_language_list_raw(cls, value: str) -> str:
        parse_language_list(value, env_name="PUBLIC_SYNC_LANGUAGES")
        return value

    @field_validator("provider_timeout_seconds", "poll_interval_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @property
    def ingest_url(self) -> str:
        if not self.public_api_base_url:
            raise ValueError("PUBLIC_API_BASE_URL is required when public-syncer is enabled")
        return f"{self.public_api_base_url}{self.public_ingest_path}"

    @property
    def raw_ingest_url(self) -> str:
        if not self.public_api_base_url:
            raise ValueError("PUBLIC_API_BASE_URL is required when public-syncer raw items are enabled")
        return f"{self.public_api_base_url}{self.public_raw_ingest_path}"

    @property
    def public_sync_languages(self) -> tuple[str, ...]:
        return parse_language_list(self.public_sync_languages_raw, env_name="PUBLIC_SYNC_LANGUAGES")

    @property
    def public_raw_sync_languages(self) -> tuple[str, ...]:
        return parse_language_list(self.public_raw_sync_languages_raw, env_name="PUBLIC_RAW_SYNC_LANGUAGES")


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
