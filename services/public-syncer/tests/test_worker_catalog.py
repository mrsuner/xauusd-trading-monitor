from __future__ import annotations

from public_syncer.models import PublicApiResult
from public_syncer.settings import Settings
from public_syncer.worker import PublicSyncer


class FakeDatabase:
    async def get_subscription_catalog(self):  # noqa: ANN201
        return (
            [
                {
                    "key": "fed",
                    "label_en": "Federal Reserve",
                    "label_zh": "聯準會",
                    "description": None,
                    "sort_order": 10,
                }
            ],
            [
                {
                    "key": "inflation",
                    "label_en": "Inflation",
                    "label_zh": "通膨",
                    "tag_type": "topic",
                    "aliases": [],
                }
            ],
        )


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, str, str | None]] = []

    async def send(self, payload: dict, *, idempotency_key: str, ingest_path: str | None = None) -> PublicApiResult:
        self.calls.append((payload, idempotency_key, ingest_path))
        return PublicApiResult(success=True, status_code=202)


async def test_catalog_sync_sends_only_when_revision_changes(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://xauusd:secret@postgres:5432/xauusd")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "https://news.example.com")
    monkeypatch.setenv("PUBLIC_SUBSCRIPTION_CATALOG_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_SYNCER_DRY_RUN", "false")
    syncer = PublicSyncer(Settings())
    syncer.db = FakeDatabase()  # type: ignore[assignment]
    provider = FakeProvider()

    assert await syncer._sync_catalog(provider) is True  # type: ignore[arg-type]
    assert await syncer._sync_catalog(provider) is False  # type: ignore[arg-type]
    assert len(provider.calls) == 1
    assert provider.calls[0][2] == "/ingest/subscription-catalog"
