from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    service_name: str = Field(default="telegram-channel-publisher", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    enabled: bool = Field(default=False, alias="TELEGRAM_CHANNEL_PUBLISHER_ENABLED")
    dry_run: bool = Field(default=True, alias="TELEGRAM_CHANNEL_DRY_RUN")
    bot_token: str | None = Field(default=None, alias="TELEGRAM_CHANNEL_BOT_TOKEN")
    channel_id: str | None = Field(default=None, alias="TELEGRAM_CHANNEL_ID")
    parse_mode: str = Field(default="HTML", alias="TELEGRAM_CHANNEL_PARSE_MODE")
    disable_web_page_preview: bool = Field(default=False, alias="TELEGRAM_CHANNEL_DISABLE_WEB_PAGE_PREVIEW")
    min_severity: str = Field(default="A", alias="TELEGRAM_CHANNEL_MIN_SEVERITY")
    include_b_events: bool = Field(default=False, alias="TELEGRAM_CHANNEL_INCLUDE_B_EVENTS")
    max_per_hour: int = Field(default=30, alias="TELEGRAM_CHANNEL_MAX_PER_HOUR")
    max_attempts: int = Field(default=5, alias="TELEGRAM_CHANNEL_MAX_ATTEMPTS")
    retry_backoff_seconds: int = Field(default=60, alias="TELEGRAM_CHANNEL_RETRY_BACKOFF_SECONDS")
    poll_interval_seconds: float = Field(default=10.0, alias="PUBLISHER_POLL_INTERVAL_SECONDS")
    batch_size: int = Field(default=5, alias="TELEGRAM_CHANNEL_BATCH_SIZE")
    provider_timeout_seconds: float = Field(default=10.0, alias="TELEGRAM_CHANNEL_PROVIDER_TIMEOUT_SECONDS")
    lock_timeout_seconds: int = Field(default=300, alias="TELEGRAM_CHANNEL_LOCK_TIMEOUT_SECONDS")
    message_limit_chars: int = Field(default=3900, alias="TELEGRAM_CHANNEL_MESSAGE_LIMIT_CHARS")

    @field_validator("bot_token", "channel_id")
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("parse_mode")
    @classmethod
    def validate_parse_mode(cls, value: str) -> str:
        if value not in {"HTML", "plain"}:
            raise ValueError("parse_mode must be HTML or plain")
        return value

    @field_validator("min_severity")
    @classmethod
    def validate_min_severity(cls, value: str) -> str:
        if value not in {"S", "A", "B", "C"}:
            raise ValueError("min_severity must be S, A, B, or C")
        return value

    @field_validator(
        "retry_backoff_seconds",
        "max_per_hour",
    )
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("max_attempts", "batch_size", "lock_timeout_seconds", "message_limit_chars")
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
