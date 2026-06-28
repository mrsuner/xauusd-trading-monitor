from __future__ import annotations

from datetime import datetime

from event_router.settings import Settings
from event_router.worker import EventRouter


class FakeDatabase:
    def __init__(self) -> None:
        self.enrichment_calls: list[dict[str, object]] = []

    async def unrouted_event_ids(self, *, since: datetime, limit: int) -> list[object]:
        return []

    async def enrich_public_outbox_translations(
        self,
        *,
        languages: tuple[str, ...],
        limit: int,
        lookback_hours: int,
    ) -> tuple[int, int]:
        self.enrichment_calls.append(
            {
                "languages": languages,
                "limit": limit,
                "lookback_hours": lookback_hours,
            }
        )
        return 0, 0


async def test_run_once_enriches_public_outbox_translations_when_public_website_enabled() -> None:
    db = FakeDatabase()
    settings = Settings(
        DATABASE_URL="postgresql://example",
        ENABLE_PUBLIC_WEBSITE_ROUTE=True,
        PUBLIC_OUTBOX_LANGUAGES="zh-Hant,en,ja,th",
        PUBLIC_OUTBOX_TRANSLATION_ENRICHMENT_BATCH_SIZE=25,
        PUBLIC_OUTBOX_TRANSLATION_ENRICHMENT_LOOKBACK_HOURS=12,
    )
    router = EventRouter(settings, db)  # type: ignore[arg-type]

    assert await router.run_once() == 0
    assert db.enrichment_calls == [
        {
            "languages": ("zh-Hant", "en", "ja", "th"),
            "limit": 25,
            "lookback_hours": 12,
        }
    ]


async def test_run_once_skips_enrichment_when_public_website_disabled() -> None:
    db = FakeDatabase()
    settings = Settings(
        DATABASE_URL="postgresql://example",
        ENABLE_PUBLIC_WEBSITE_ROUTE=False,
        PUBLIC_OUTBOX_TRANSLATION_ENRICHMENT_ENABLED=True,
    )
    router = EventRouter(settings, db)  # type: ignore[arg-type]

    assert await router.run_once() == 0
    assert db.enrichment_calls == []
