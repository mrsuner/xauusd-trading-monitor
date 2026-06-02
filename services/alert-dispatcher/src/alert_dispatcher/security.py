from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_RE = re.compile(
    r"(authorization|bearer|token|secret|signature|api[_-]?key|user[_-]?key|chat[_-]?id|password|oauth)",
    re.IGNORECASE,
)
TELEGRAM_BOT_URL_RE = re.compile(r"https://api\.telegram\.org/bot[^/\s]+", re.IGNORECASE)
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
OAUTH_PAIR_RE = re.compile(
    r'(oauth_(?:token|consumer_key|signature|nonce)=")[^"]+(")',
    re.IGNORECASE,
)
SECRET_KEY_VALUE_RE = re.compile(
    r"\b((?:X-XER-Signature|Authorization|Bearer|token|secret|signature|api[_-]?key|user[_-]?key|password)=)[^\s&]+",
    re.IGNORECASE,
)
LONG_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{24,}(?![A-Za-z0-9])")


def sanitize_text(value: object, *, limit: int = 2000) -> str:
    text = str(value)
    text = TELEGRAM_BOT_URL_RE.sub("https://api.telegram.org/bot[REDACTED]", text)
    text = BEARER_RE.sub("Bearer [REDACTED]", text)
    text = OAUTH_PAIR_RE.sub(r"\1[REDACTED]\2", text)
    text = SECRET_KEY_VALUE_RE.sub(r"\1[REDACTED]", text)
    text = LONG_SECRET_RE.sub("[REDACTED]", text)
    return text[:limit]


def sanitize_provider_response(value: Any, *, max_string_length: int = 500) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                clean[key] = "[REDACTED]"
            else:
                clean[key] = sanitize_provider_response(item, max_string_length=max_string_length)
        return clean
    if isinstance(value, list):
        return [sanitize_provider_response(item, max_string_length=max_string_length) for item in value[:20]]
    if isinstance(value, str):
        return sanitize_text(value, limit=max_string_length)
    return value
