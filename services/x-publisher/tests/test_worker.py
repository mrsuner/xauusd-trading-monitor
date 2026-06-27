from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from x_publisher.models import PublicOutboxItem
from x_publisher.semantic_dedupe import SemanticDedupeResult
from x_publisher.settings import Settings
from x_publisher.worker import XPublisher


def make_item(**overrides: object) -> PublicOutboxItem:
    data = {
        "id": uuid4(),
        "event_id": uuid4(),
        "title": "IRGC 聲稱攻擊美軍基地",
        "summary": "IRGC聲稱對科威特與巴林的美軍基地及第五艦隊設施發動打擊。",
        "public_source_links": [{"source_name": "Press TV", "url": "https://example.com/news"}],
        "severity": "S",
        "confirmation_state": "unconfirmed",
        "topic_tags": ["geopolitics", "iran"],
        "generated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return PublicOutboxItem.model_validate(data)


@pytest.mark.asyncio
async def test_publish_item_skips_semantic_duplicate_before_provider_send() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x:y@localhost/db",
        X_PUBLISHER_ENABLED=True,
        X_PUBLISHER_DRY_RUN=False,
        X_SEMANTIC_DEDUPE_ENABLED=True,
    )
    publisher = XPublisher(settings)
    fake_db = FakeDb()
    fake_provider = FakeProvider()
    publisher.db = fake_db  # type: ignore[assignment]

    item = make_item()
    candidate = make_item()
    fake_db.candidates = [candidate]
    semantic_dedupe = FakeSemanticDedupe(
        SemanticDedupeResult(
            is_duplicate=True,
            similarity_score=93,
            matched_item_id=str(candidate.id),
            reason="same claim",
        )
    )

    await publisher._publish_item(item, fake_provider, semantic_dedupe)  # type: ignore[arg-type]

    assert fake_provider.sent_posts == []
    assert fake_db.skipped == [
        {
            "item_id": item.id,
            "reason": "semantic_duplicate_x",
            "provider_response": {
                "semantic_duplicate": True,
                "matched_item_id": str(candidate.id),
                "similarity_score": 93,
                "reason": "same claim",
                "model": None,
            },
        }
    ]


class FakeDb:
    def __init__(self) -> None:
        self.candidates: list[PublicOutboxItem] = []
        self.skipped: list[dict[str, object]] = []

    async def recent_sent_x_items(self, **_: object) -> list[PublicOutboxItem]:
        return self.candidates

    async def mark_skipped(self, **kwargs: object) -> None:
        self.skipped.append(kwargs)


class FakeProvider:
    def __init__(self) -> None:
        self.sent_posts: list[str] = []

    async def send(self, post: str) -> object:
        self.sent_posts.append(post)
        raise AssertionError("provider should not be called for semantic duplicates")


class FakeSemanticDedupe:
    def __init__(self, result: SemanticDedupeResult) -> None:
        self.result = result

    async def compare(
        self,
        item: PublicOutboxItem,
        candidates: list[PublicOutboxItem],
    ) -> SemanticDedupeResult:
        return self.result
