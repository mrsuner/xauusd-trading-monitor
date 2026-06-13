from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
