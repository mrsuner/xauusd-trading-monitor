from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from uuid import uuid4

from telegram_collector.models import TelegramSource
from telegram_collector.models import normalize_telegram_identifier
from telegram_collector.telegram_mapping import dedupe_key
from telegram_collector.telegram_mapping import message_to_raw_item
from telegram_collector.telegram_mapping import public_message_url


@dataclass
class FakeMessage:
    id: int
    message: str
    date: datetime
    edit_date: datetime | None = None
    photo: object | None = None
    document: object | None = None
    web_preview: object | None = None
    media: object | None = None

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "message": self.message, "date": self.date}


def source() -> TelegramSource:
    return TelegramSource(
        id=uuid4(),
        name="IRNA English",
        handle_or_url="@Irna_en",
        source_group="iran_government",
        official_level="official",
        language="en",
        priority="P0",
        source_config={"telegram_username": "Irna_en"},
    )


def test_normalize_telegram_identifier() -> None:
    assert normalize_telegram_identifier("@Irna_en") == "Irna_en"
    assert normalize_telegram_identifier("https://t.me/Irna_en/123") == "Irna_en"
    assert normalize_telegram_identifier("t.me/Irna_en") == "Irna_en"


def test_dedupe_key() -> None:
    assert dedupe_key(123, 456) == "telegram:123:456"


def test_public_message_url() -> None:
    assert public_message_url("Irna_en", 456) == "https://t.me/Irna_en/456"
    assert public_message_url(None, 456) is None


def test_message_to_raw_item() -> None:
    message = FakeMessage(id=456, message="Test text", date=datetime(2026, 5, 30, tzinfo=UTC))

    raw_item = message_to_raw_item(
        source=source(),
        channel_id=123,
        public_username="Irna_en",
        message=message,
    )

    assert raw_item["external_id"] == "456"
    assert raw_item["text_raw"] == "Test text"
    assert raw_item["language"] == "en"
    assert raw_item["url"] == "https://t.me/Irna_en/456"
    assert raw_item["media_type"] == "none"
    assert raw_item["dedupe_key"] == "telegram:123:456"
    assert raw_item["content_hash"]
