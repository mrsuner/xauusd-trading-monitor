from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    service_name: str = "telegram-collector"
    database_url: str = Field(..., alias="DATABASE_URL")
    telegram_api_id: int = Field(..., alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(..., alias="TELEGRAM_API_HASH")
    telegram_session_path: Path = Field(
        Path("/app/sessions/xauusd-event-radar.session"),
        alias="TELEGRAM_SESSION_PATH",
    )
    backfill_hours: int = Field(6, alias="BACKFILL_HOURS")
    backfill_limit_per_source: int = Field(500, alias="BACKFILL_LIMIT_PER_SOURCE")
    source_refresh_interval_seconds: int = Field(300, alias="SOURCE_REFRESH_INTERVAL_SECONDS")
    health_update_interval_seconds: int = Field(30, alias="HEALTH_UPDATE_INTERVAL_SECONDS")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    def psycopg_database_url(self) -> str:
        if self.database_url.startswith("postgresql+psycopg://"):
            return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return self.database_url
