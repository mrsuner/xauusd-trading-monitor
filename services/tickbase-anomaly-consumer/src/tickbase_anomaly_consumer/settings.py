from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    service_name: str = Field(default="tickbase-anomaly-consumer", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    enabled: bool = Field(default=False, alias="ANOMALY_CONSUMER_ENABLED")

    # tickbase feed
    api_base_url: str = Field(default="https://api.thetickbase.com", alias="TICKBASE_API_BASE_URL")
    api_key: str | None = Field(default=None, alias="TICKBASE_API_KEY")
    request_timeout_seconds: float = Field(default=15.0, alias="TICKBASE_REQUEST_TIMEOUT_SECONDS")
    rest_page_size: int = Field(default=200, alias="ANOMALY_REST_PAGE_SIZE")

    # First-run cursor: "tail" (start from current head, no history),
    # "earliest" (replay from id 0), or a numeric tickbase id string.
    start_mode: str = Field(default="tail", alias="ANOMALY_CONSUMER_START")

    # Reconnect backoff for the SSE stream.
    reconnect_initial_backoff_seconds: float = Field(
        default=1.0, alias="ANOMALY_SSE_RECONNECT_INITIAL_BACKOFF_SECONDS"
    )
    reconnect_max_backoff_seconds: float = Field(
        default=30.0, alias="ANOMALY_SSE_RECONNECT_BACKOFF_SECONDS"
    )

    # Severity = f(ratio) where ratio = observed_change / rule_threshold (>= 1.0
    # because the rule already fired). Bands are inclusive lower bounds.
    severity_s_multiplier: float = Field(default=3.0, alias="ANOMALY_SEVERITY_S_MULTIPLIER")
    severity_a_multiplier: float = Field(default=2.0, alias="ANOMALY_SEVERITY_A_MULTIPLIER")
    severity_b_multiplier: float = Field(default=1.5, alias="ANOMALY_SEVERITY_B_MULTIPLIER")

    @field_validator("api_key")
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or value == "" or value == "change-me":
            return None
        return value

    @field_validator("start_mode")
    @classmethod
    def validate_start_mode(cls, value: str) -> str:
        if value in {"tail", "earliest"}:
            return value
        try:
            int(value)
        except ValueError as exc:
            raise ValueError("start_mode must be 'tail', 'earliest', or a numeric id") from exc
        return value

    @field_validator("rest_page_size")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("request_timeout_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator(
        "severity_s_multiplier",
        "severity_a_multiplier",
        "severity_b_multiplier",
    )
    @classmethod
    def validate_multiplier(cls, value: float) -> float:
        if value < 1.0:
            raise ValueError("severity multiplier must be >= 1.0")
        return value

    @property
    def start_id(self) -> int | None:
        """Explicit numeric start id, or None for tail/earliest."""
        if self.start_mode in {"tail", "earliest"}:
            return None
        return int(self.start_mode)
