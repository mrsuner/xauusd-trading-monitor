from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import UTC
from datetime import datetime
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "authorization",
    "bearer",
    "credential",
    "database_url",
    "dsn",
    "password",
    "secret",
    "session",
    "signature",
    "telegram_api_hash",
    "token",
    "user_key",
    "api_key",
    "chat_id",
    "oauth",
)
STANDARD_LOG_ATTRS = frozenset(logging.LogRecord("x", 0, "x", 0, "x", (), None).__dict__)
URL_CREDENTIALS_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@")
TELEGRAM_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)[^/\s]+", re.IGNORECASE)
BEARER_RE = re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
OAUTH_RE = re.compile(r'(oauth_(?:token|consumer_key|signature|nonce)=")[^"]+(")', re.IGNORECASE)
KEY_VALUE_RE = re.compile(
    r"\b((?:authorization|token|secret|signature|api[_-]?key|user[_-]?key|chat[_-]?id|password|oauth)"
    r"\s*[=:]\s*)[^\s&,;]+",
    re.IGNORECASE,
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized.endswith("_tokens") or normalized == "tokens":
        return False
    return any(part in normalized.split("_") for part in SENSITIVE_KEY_PARTS) or any(
        part in normalized
        for part in (
            "api_key",
            "access_token",
            "bearer_token",
            "database_url",
            "telegram_api_hash",
            "user_key",
            "chat_id",
        )
    )


def _redact_text(value: str) -> str:
    value = URL_CREDENTIALS_RE.sub(r"\1[REDACTED]:[REDACTED]@", value)
    value = TELEGRAM_BOT_URL_RE.sub(r"\1[REDACTED]", value)
    value = BEARER_RE.sub(r"\1[REDACTED]", value)
    value = OAUTH_RE.sub(r'\1[REDACTED]\2', value)
    return KEY_VALUE_RE.sub(r"\1[REDACTED]", value)


def _redact_value(key: str, value: Any) -> Any:
    if _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {str(item_key): _redact_value(str(item_key), item_value) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(key, item) for item in value]
    return value


class JsonLogFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": _redact_text(record.getMessage()),
        }
        extras = {
            key: _redact_value(key, value)
            for key, value in record.__dict__.items()
            if key not in STANDARD_LOG_ATTRS and not key.startswith("_")
        }
        payload.update(extras)
        if record.exc_info:
            payload["exception"] = _redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(os.environ.get("SERVICE_NAME", "x-publisher")))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
