from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    service_name: str = Field(default="alert-dispatcher", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    enable_telegram_alerts: bool = Field(default=True, alias="ENABLE_TELEGRAM_ALERTS")
    enable_pushover_alerts: bool = Field(default=True, alias="ENABLE_PUSHOVER_ALERTS")
    enable_polling_fallback: bool = Field(default=True, alias="ENABLE_POLLING_FALLBACK")
    alert_dry_run: bool = Field(default=True, alias="ALERT_DRY_RUN")
    dispatch_existing_events_on_start: bool = Field(default=False, alias="DISPATCH_EXISTING_EVENTS_ON_START")
    alert_backfill_mode: str = Field(default="telegram_only", alias="ALERT_BACKFILL_MODE")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    pushover_app_token: str | None = Field(default=None, alias="PUSHOVER_APP_TOKEN")
    pushover_user_key: str | None = Field(default=None, alias="PUSHOVER_USER_KEY")
    pushover_emergency_retry_seconds: int = Field(default=60, alias="PUSHOVER_EMERGENCY_RETRY_SECONDS")
    pushover_emergency_expire_seconds: int = Field(default=600, alias="PUSHOVER_EMERGENCY_EXPIRE_SECONDS")

    poll_interval_seconds: float = Field(default=2.0, alias="POLL_INTERVAL_SECONDS")
    event_lookback_minutes: int = Field(default=120, alias="EVENT_LOOKBACK_MINUTES")
    event_batch_size: int = Field(default=50, alias="EVENT_BATCH_SIZE")
    alert_batch_size: int = Field(default=10, alias="ALERT_BATCH_SIZE")
    max_alerts_per_run: int = Field(default=0, alias="MAX_ALERTS_PER_RUN")

    max_attempts: int = Field(default=3, alias="MAX_ATTEMPTS")
    initial_backoff_seconds: int = Field(default=10, alias="INITIAL_BACKOFF_SECONDS")
    max_backoff_seconds: int = Field(default=300, alias="MAX_BACKOFF_SECONDS")
    provider_timeout_seconds: float = Field(default=10.0, alias="ALERT_PROVIDER_TIMEOUT_SECONDS")

    @field_validator(
        "telegram_bot_token",
        "telegram_chat_id",
        "pushover_app_token",
        "pushover_user_key",
    )
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator(
        "pushover_emergency_retry_seconds",
        "pushover_emergency_expire_seconds",
        "event_lookback_minutes",
        "event_batch_size",
        "alert_batch_size",
        "max_alerts_per_run",
        "max_attempts",
        "initial_backoff_seconds",
        "max_backoff_seconds",
    )
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("poll_interval_seconds", "provider_timeout_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("alert_backfill_mode")
    @classmethod
    def validate_alert_backfill_mode(cls, value: str) -> str:
        if value not in {"skip", "telegram_only", "normal"}:
            raise ValueError("alert_backfill_mode must be skip, telegram_only, or normal")
        return value
