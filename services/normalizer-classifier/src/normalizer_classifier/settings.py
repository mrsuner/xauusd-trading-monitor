from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")
    poll_interval_seconds: float = Field(default=2.0, alias="POLL_INTERVAL_SECONDS")
    model_route: str = Field(default="cloud_small", alias="MODEL_ROUTE")

    local_model_base_url: str | None = Field(default=None, alias="LOCAL_MODEL_BASE_URL")
    local_model_api_key: str | None = Field(default=None, alias="LOCAL_MODEL_API_KEY")
    local_model_name: str | None = Field(default=None, alias="LOCAL_MODEL_NAME")

    cloud_model_base_url: str | None = Field(default="https://api.openai.com/v1", alias="CLOUD_MODEL_BASE_URL")
    cloud_model_api_key: str | None = Field(default=None, alias="CLOUD_MODEL_API_KEY")
    cloud_model_name: str | None = Field(default=None, alias="CLOUD_MODEL_NAME")

    model_timeout_seconds: float = Field(default=30.0, alias="MODEL_TIMEOUT_SECONDS")
    relevance_threshold_event: int = Field(default=70, alias="RELEVANCE_THRESHOLD_EVENT")
    max_attempts: int = Field(default=3, alias="MAX_ATTEMPTS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("worker_concurrency")
    @classmethod
    def validate_worker_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("WORKER_CONCURRENCY must be >= 1")
        return value

    @field_validator("relevance_threshold_event")
    @classmethod
    def validate_threshold(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("RELEVANCE_THRESHOLD_EVENT must be between 0 and 100")
        return value
