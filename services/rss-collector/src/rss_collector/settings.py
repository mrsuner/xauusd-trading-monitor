from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    service_name: str = "rss-collector"
    database_url: str = Field(..., alias="DATABASE_URL")
    default_poll_interval_seconds: int = Field(120, alias="DEFAULT_POLL_INTERVAL_SECONDS")
    default_request_timeout_seconds: int = Field(15, alias="DEFAULT_REQUEST_TIMEOUT_SECONDS")
    source_refresh_interval_seconds: int = Field(300, alias="SOURCE_REFRESH_INTERVAL_SECONDS")
    health_update_interval_seconds: int = Field(30, alias="HEALTH_UPDATE_INTERVAL_SECONDS")
    user_agent: str = Field("XAUUSD-Event-Radar/1.0", alias="USER_AGENT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    def psycopg_database_url(self) -> str:
        if self.database_url.startswith("postgresql+psycopg://"):
            return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return self.database_url
