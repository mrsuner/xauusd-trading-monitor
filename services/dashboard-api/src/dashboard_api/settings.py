from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    api_token: str | None = Field(default=None, alias="API_TOKEN")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    default_page_size: int = Field(default=50, alias="DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=200, alias="MAX_PAGE_SIZE")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("api_token")
    @classmethod
    def normalize_api_token(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("default_page_size", "max_page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page size must be >= 1")
        return value

    @field_validator("cors_origins")
    @classmethod
    def normalize_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
