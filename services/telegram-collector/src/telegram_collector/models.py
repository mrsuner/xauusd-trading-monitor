from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class TelegramSource:
    id: UUID
    name: str
    handle_or_url: str
    source_group: str
    official_level: str
    language: str | None
    priority: str
    source_config: dict[str, Any]

    @property
    def identifier(self) -> str:
        configured_username = self.source_config.get("telegram_username")
        if configured_username:
            return normalize_telegram_identifier(str(configured_username))
        return normalize_telegram_identifier(self.handle_or_url)


def normalize_telegram_identifier(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("https://t.me/"):
        normalized = normalized.removeprefix("https://t.me/")
    elif normalized.startswith("http://t.me/"):
        normalized = normalized.removeprefix("http://t.me/")
    if normalized.startswith("t.me/"):
        normalized = normalized.removeprefix("t.me/")
    normalized = normalized.split("/", 1)[0]
    normalized = normalized.removeprefix("@")
    return normalized
