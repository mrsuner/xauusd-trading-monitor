from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PollingSource:
    id: UUID
    name: str
    handle_or_url: str
    source_type: str
    source_group: str
    official_level: str
    language: str | None
    priority: str
    source_config: dict[str, Any]

    def poll_interval_seconds(self, default: int) -> int:
        return int(self.source_config.get("poll_interval_seconds") or default)

    def request_timeout_seconds(self, default: int) -> int:
        return int(self.source_config.get("request_timeout_seconds") or default)

    @property
    def etag(self) -> str | None:
        value = self.source_config.get("etag")
        return str(value) if value else None

    @property
    def last_modified(self) -> str | None:
        value = self.source_config.get("last_modified")
        return str(value) if value else None
