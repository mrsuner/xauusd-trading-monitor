from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    public_database_url: str = Field(alias="PUBLIC_DATABASE_URL")
    service_name: str = Field(default="public-api", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")

    ingest_auth_mode: str = Field(default="hmac", alias="PUBLIC_INGEST_AUTH_MODE")
    public_api_token: str | None = Field(default=None, alias="PUBLIC_API_TOKEN")
    ingest_key_id: str | None = Field(default=None, alias="PUBLIC_INGEST_KEY_ID")
    ingest_secret: str | None = Field(default=None, alias="PUBLIC_INGEST_SECRET")
    ingest_max_body_bytes: int = Field(default=262_144, alias="PUBLIC_INGEST_MAX_BODY_BYTES")
    ingest_timestamp_skew_seconds: int = Field(default=300, alias="PUBLIC_INGEST_TIMESTAMP_SKEW_SECONDS")
    max_summary_chars: int = Field(default=4000, alias="PUBLIC_INGEST_MAX_SUMMARY_CHARS")
    max_title_chars: int = Field(default=500, alias="PUBLIC_INGEST_MAX_TITLE_CHARS")
    max_original_content_chars: int = Field(default=4000, alias="PUBLIC_INGEST_MAX_ORIGINAL_CONTENT_CHARS")
    max_full_translation_chars: int = Field(default=8000, alias="PUBLIC_INGEST_MAX_FULL_TRANSLATION_CHARS")

    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    default_page_size: int = Field(default=20, alias="DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=100, alias="MAX_PAGE_SIZE")
    public_default_language: str = Field(default="en", alias="PUBLIC_DEFAULT_LANGUAGE")
    public_language_priority_raw: str = Field(default="en,zh-Hant", alias="PUBLIC_LANGUAGE_PRIORITY")

    @field_validator("public_api_token", "ingest_key_id", "ingest_secret")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("ingest_auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"hmac", "bearer"}:
            raise ValueError("PUBLIC_INGEST_AUTH_MODE must be hmac or bearer")
        return normalized

    @field_validator("default_page_size", "max_page_size", "ingest_max_body_bytes", "ingest_timestamp_skew_seconds")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("max_summary_chars", "max_title_chars", "max_original_content_chars", "max_full_translation_chars")
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("public_default_language")
    @classmethod
    def validate_public_default_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not LANGUAGE_CODE_RE.match(normalized):
            raise ValueError("PUBLIC_DEFAULT_LANGUAGE must be a valid BCP 47 language code")
        return normalized

    @field_validator("public_language_priority_raw")
    @classmethod
    def validate_public_language_priority_raw(cls, value: str) -> str:
        parse_language_list(value, env_name="PUBLIC_LANGUAGE_PRIORITY")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def public_language_priority(self) -> tuple[str, ...]:
        return parse_language_list(self.public_language_priority_raw, env_name="PUBLIC_LANGUAGE_PRIORITY")


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
