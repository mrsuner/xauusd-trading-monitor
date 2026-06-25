from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


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
    public_x_a_relevance_threshold: int = Field(default=90, alias="PUBLIC_X_A_RELEVANCE_THRESHOLD")
    public_outbox_languages_raw: str = Field(default="zh-Hant,en", alias="PUBLIC_OUTBOX_LANGUAGES")
    public_outbox_default_language: str = Field(default="en", alias="PUBLIC_OUTBOX_DEFAULT_LANGUAGE")

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
        "public_x_a_relevance_threshold",
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

    @field_validator("public_outbox_languages_raw")
    @classmethod
    def validate_public_outbox_languages_raw(cls, value: str) -> str:
        parse_language_list(value, env_name="PUBLIC_OUTBOX_LANGUAGES")
        return value

    @field_validator("public_outbox_default_language")
    @classmethod
    def validate_public_outbox_default_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not LANGUAGE_CODE_RE.match(normalized):
            raise ValueError("PUBLIC_OUTBOX_DEFAULT_LANGUAGE must be a valid BCP 47 language code")
        return normalized

    @property
    def public_outbox_languages(self) -> tuple[str, ...]:
        return parse_language_list(self.public_outbox_languages_raw, env_name="PUBLIC_OUTBOX_LANGUAGES")


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
