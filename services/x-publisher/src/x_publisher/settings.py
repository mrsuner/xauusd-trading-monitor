from __future__ import annotations

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

    @field_validator("api_key", "api_secret", "access_token", "access_token_secret", "bearer_token")
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("api_base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
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

    @field_validator("max_attempts", "batch_size", "lock_timeout_seconds", "post_max_chars")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("poll_interval_seconds", "provider_timeout_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value
