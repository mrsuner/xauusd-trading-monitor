from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    service_name: str = Field(default="event-router", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    enable_private_telegram_route: bool = Field(default=True, alias="ENABLE_PRIVATE_TELEGRAM_ROUTE")
    enable_private_pushover_route: bool = Field(default=True, alias="ENABLE_PRIVATE_PUSHOVER_ROUTE")
    enable_public_telegram_channel_route: bool = Field(default=True, alias="ENABLE_PUBLIC_TELEGRAM_CHANNEL_ROUTE")
    enable_public_website_route: bool = Field(default=False, alias="ENABLE_PUBLIC_WEBSITE_ROUTE")
    enable_public_x_route: bool = Field(default=False, alias="ENABLE_PUBLIC_X_ROUTE")

    dispatch_existing_events_on_start: bool = Field(default=False, alias="EVENT_ROUTER_DISPATCH_EXISTING_EVENTS_ON_START")
    backfill_mode: str = Field(default="telegram_only", alias="EVENT_ROUTER_BACKFILL_MODE")
    poll_interval_seconds: float = Field(default=2.0, alias="EVENT_ROUTER_POLL_INTERVAL_SECONDS")
    event_lookback_minutes: int = Field(default=120, alias="EVENT_ROUTER_LOOKBACK_MINUTES")
    event_batch_size: int = Field(default=50, alias="EVENT_ROUTER_BATCH_SIZE")
    max_events_per_run: int = Field(default=0, alias="EVENT_ROUTER_MAX_EVENTS_PER_RUN")

    private_telegram_threshold: int = Field(default=45, alias="PRIVATE_TELEGRAM_ROUTE_SCORE_THRESHOLD")
    private_telegram_s_threshold: int = Field(default=35, alias="PRIVATE_TELEGRAM_S_ROUTE_SCORE_THRESHOLD")
    private_pushover_threshold: int = Field(default=85, alias="PRIVATE_PUSHOVER_ROUTE_SCORE_THRESHOLD")
    public_telegram_threshold: int = Field(default=65, alias="PUBLIC_TELEGRAM_ROUTE_SCORE_THRESHOLD")
    public_website_threshold: int = Field(default=50, alias="PUBLIC_WEBSITE_ROUTE_SCORE_THRESHOLD")
    public_x_threshold: int = Field(default=85, alias="PUBLIC_X_ROUTE_SCORE_THRESHOLD")

    @field_validator(
        "event_lookback_minutes",
        "event_batch_size",
        "max_events_per_run",
        "private_telegram_threshold",
        "private_telegram_s_threshold",
        "private_pushover_threshold",
        "public_telegram_threshold",
        "public_website_threshold",
        "public_x_threshold",
    )
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("poll_interval_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("backfill_mode")
    @classmethod
    def validate_backfill_mode(cls, value: str) -> str:
        if value not in {"skip", "telegram_only", "normal"}:
            raise ValueError("backfill_mode must be skip, telegram_only, or normal")
        return value
