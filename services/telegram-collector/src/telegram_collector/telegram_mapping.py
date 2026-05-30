from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from .models import TelegramSource


def content_hash(text: str | None, title: str | None = None) -> str:
    payload = "\n".join(part for part in (title, text) if part)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dedupe_key(channel_id: int | str, message_id: int | str) -> str:
    return f"telegram:{channel_id}:{message_id}"


def public_message_url(username: str | None, message_id: int | str) -> str | None:
    if not username:
        return None
    return f"https://t.me/{username}/{message_id}"


def media_type_from_message(message: Any) -> str:
    if getattr(message, "photo", None):
        return "photo"
    document = getattr(message, "document", None)
    if document:
        mime_type = getattr(document, "mime_type", "") or ""
        if mime_type.startswith("video/"):
            return "video"
        return "document"
    if getattr(message, "web_preview", None):
        return "webpage"
    if getattr(message, "media", None):
        return "unknown"
    return "none"


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "to_dict"):
        return json_safe(value.to_dict())
    return value


def message_to_raw_item(
    *,
    source: TelegramSource,
    channel_id: int,
    public_username: str | None,
    message: Any,
) -> dict[str, Any]:
    message_id = getattr(message, "id")
    text = getattr(message, "message", None) or getattr(message, "text", None) or ""
    edit_date = getattr(message, "edit_date", None)
    message_date = getattr(message, "date", None)

    return {
        "source_id": source.id,
        "external_id": str(message_id),
        "published_at": message_date,
        "edited_at": edit_date,
        "title": None,
        "text_raw": text,
        "text_clean": text,
        "language": source.language,
        "url": public_message_url(public_username, message_id),
        "media_type": media_type_from_message(message),
        "raw_json": json_safe(message),
        "content_hash": content_hash(text),
        "dedupe_key": dedupe_key(channel_id, message_id),
    }
