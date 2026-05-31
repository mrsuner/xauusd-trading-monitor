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
    local_model_response_format: str = Field(default="none", alias="LOCAL_MODEL_RESPONSE_FORMAT")
    local_model_reasoning_effort: str | None = Field(default=None, alias="LOCAL_MODEL_REASONING_EFFORT")

    cloud_model_base_url: str | None = Field(default="https://api.openai.com/v1", alias="CLOUD_MODEL_BASE_URL")
    cloud_model_api_key: str | None = Field(default=None, alias="CLOUD_MODEL_API_KEY")
    cloud_model_name: str | None = Field(default=None, alias="CLOUD_MODEL_NAME")
    cloud_model_response_format: str = Field(default="json_object", alias="CLOUD_MODEL_RESPONSE_FORMAT")
    cloud_model_reasoning_effort: str | None = Field(default=None, alias="CLOUD_MODEL_REASONING_EFFORT")

    model_timeout_seconds: float = Field(default=30.0, alias="MODEL_TIMEOUT_SECONDS")
    max_model_calls_per_run: int = Field(default=0, alias="MAX_MODEL_CALLS_PER_RUN")
    relevance_threshold_event: int = Field(default=70, alias="RELEVANCE_THRESHOLD_EVENT")
    max_attempts: int = Field(default=3, alias="MAX_ATTEMPTS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("worker_concurrency")
    @classmethod
    def validate_worker_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("WORKER_CONCURRENCY must be >= 1")
        return value

    @field_validator("max_model_calls_per_run")
    @classmethod
    def validate_max_model_calls_per_run(cls, value: int) -> int:
        if value < 0:
            raise ValueError("MAX_MODEL_CALLS_PER_RUN must be >= 0")
        return value

    @field_validator("relevance_threshold_event")
    @classmethod
    def validate_threshold(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("RELEVANCE_THRESHOLD_EVENT must be between 0 and 100")
        return value

    @field_validator("local_model_response_format", "cloud_model_response_format")
    @classmethod
    def validate_response_format(cls, value: str) -> str:
        allowed = {"none", "json_object", "json_schema", "text"}
        if value not in allowed:
            raise ValueError(f"response format must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("local_model_reasoning_effort", "cloud_model_reasoning_effort")
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value
