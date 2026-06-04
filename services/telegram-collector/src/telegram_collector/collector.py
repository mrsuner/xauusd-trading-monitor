from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from telethon import TelegramClient
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel
from telethon.tl.types import Chat
from telethon.tl.types import User

from .db import Database
from .models import TelegramSource
from .settings import Settings
from .telegram_mapping import message_to_raw_item

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedSource:
    source: TelegramSource
    entity: Any
    channel_id: int
    public_username: str | None


class TelegramCollector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.psycopg_database_url())
        session_name = str(settings.telegram_session_path)
        self.client = TelegramClient(session_name, settings.telegram_api_id, settings.telegram_api_hash)
        self._resolved_by_channel_id: dict[int, ResolvedSource] = {}
        self._source_ids: set[str] = set()
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        await self.db.connect()
        await self.client.connect()

        if not await self.client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized. Run `telegram-collector login` first.")

        await self.refresh_sources()
        self.register_handlers()

        backfill_task = self.create_background_task(self.backfill_all_sources(), name="telegram-backfill")
        refresh_task = self.create_background_task(self.refresh_loop(), name="telegram-source-refresh")
        health_task = self.create_background_task(self.health_loop(), name="telegram-health")

        try:
            logger.info("telegram collector started", extra={"sources": len(self._resolved_by_channel_id)})
            await self.client.run_until_disconnected()
        finally:
            self._stop_event.set()
            for task in (backfill_task, refresh_task, health_task):
                task.cancel()
            await asyncio.gather(backfill_task, refresh_task, health_task, return_exceptions=True)
            await self.client.disconnect()
            await self.db.close()

    async def login(self) -> None:
        self.settings.telegram_session_path.parent.mkdir(parents=True, exist_ok=True)
        await self.client.start()
        logger.info("telegram session authorized", extra={"session_path": str(self.settings.telegram_session_path)})
        await self.client.disconnect()

    def register_handlers(self) -> None:
        @self.client.on(events.NewMessage())
        async def new_message_handler(event: events.NewMessage.Event) -> None:
            try:
                await self.handle_message(event.message)
            except Exception:
                logger.exception("failed to handle telegram new message")

        @self.client.on(events.MessageEdited())
        async def edited_message_handler(event: events.MessageEdited.Event) -> None:
            try:
                await self.handle_message(event.message)
            except Exception:
                logger.exception("failed to handle telegram edited message")

    def create_background_task(self, coro: Any, *, name: str) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(self.background_task_done)
        return task

    def background_task_done(self, task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return

        task_name = task.get_name()
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return

        if exc is None:
            logger.info("telegram collector background task finished", extra={"task_name": task_name})
            return

        logger.error(
            "telegram collector background task crashed",
            extra={"task_name": task_name},
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        self._stop_event.set()
        try:
            asyncio.create_task(self.client.disconnect(), name="telegram-background-shutdown")
        except RuntimeError:
            logger.exception("failed to schedule telegram collector shutdown")

    async def refresh_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self.settings.source_refresh_interval_seconds)
            try:
                await self.refresh_sources()
            except Exception:
                logger.exception("telegram source refresh failed")

    async def health_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                now = datetime.now(UTC)
                for resolved in list(self._resolved_by_channel_id.values()):
                    await self.db.upsert_source_health(
                        source_id=resolved.source.id,
                        service_name=self.settings.service_name,
                        status="healthy",
                        last_seen_at=now,
                        metadata={
                            "channel_id": resolved.channel_id,
                            "public_username": resolved.public_username,
                        },
                    )
            except Exception:
                logger.exception("telegram health update failed")
            await asyncio.sleep(self.settings.health_update_interval_seconds)

    async def refresh_sources(self) -> None:
        sources = await self.db.fetch_enabled_telegram_sources()
        active_source_ids = {str(source.id) for source in sources}
        self._source_ids = active_source_ids

        for source in sources:
            if any(str(resolved.source.id) == str(source.id) for resolved in self._resolved_by_channel_id.values()):
                continue
            await self.resolve_source(source)

        disabled_channel_ids = [
            channel_id
            for channel_id, resolved in self._resolved_by_channel_id.items()
            if str(resolved.source.id) not in active_source_ids
        ]
        for channel_id in disabled_channel_ids:
            self._resolved_by_channel_id.pop(channel_id, None)

    async def resolve_source(self, source: TelegramSource) -> None:
        try:
            entity = await self.client.get_entity(source.identifier)
            channel_id = int(getattr(entity, "id"))
            public_username = getattr(entity, "username", None)
            self._resolved_by_channel_id[channel_id] = ResolvedSource(
                source=source,
                entity=entity,
                channel_id=channel_id,
                public_username=public_username,
            )
            await self.db.upsert_source_health(
                source_id=source.id,
                service_name=self.settings.service_name,
                status="healthy",
                last_seen_at=datetime.now(UTC),
                metadata={"channel_id": channel_id, "public_username": public_username},
            )
            logger.info("resolved telegram source", extra={"source": source.name, "identifier": source.identifier})
        except FloodWaitError as exc:
            logger.warning("telegram flood wait while resolving source", extra={"source": source.name, "seconds": exc.seconds})
            await asyncio.sleep(exc.seconds)
        except Exception as exc:
            logger.exception("failed to resolve telegram source", extra={"source": source.name, "identifier": source.identifier})
            await self.db.upsert_source_health(
                source_id=source.id,
                service_name=self.settings.service_name,
                status="failed",
                last_error_at=datetime.now(UTC),
                last_error_message=str(exc),
            )

    async def backfill_all_sources(self) -> None:
        for resolved in sorted(
            list(self._resolved_by_channel_id.values()),
            key=lambda item: item.source.priority,
        ):
            try:
                await self.backfill_source(resolved)
            except Exception:
                logger.exception("telegram backfill source failed", extra={"source": resolved.source.name})

    async def backfill_source(self, resolved: ResolvedSource) -> None:
        started_at = datetime.now(UTC)
        await self.db.upsert_source_health(
            source_id=resolved.source.id,
            service_name=self.settings.service_name,
            status="healthy",
            backfill_status="running",
            backfill_started_at=started_at,
        )
        since = started_at - timedelta(hours=self.settings.backfill_hours)
        ingested_count = 0

        try:
            async for message in self.client.iter_messages(
                resolved.entity,
                limit=self.settings.backfill_limit_per_source,
            ):
                if message.date and message.date < since:
                    break
                await self.persist_message(resolved, message)
                ingested_count += 1

            await self.db.upsert_source_health(
                source_id=resolved.source.id,
                service_name=self.settings.service_name,
                status="healthy",
                backfill_status="completed",
                backfill_completed_at=datetime.now(UTC),
                metadata={"last_backfill_ingested_count": ingested_count},
            )
            logger.info("telegram backfill completed", extra={"source": resolved.source.name, "count": ingested_count})
        except FloodWaitError as exc:
            logger.warning("telegram flood wait during backfill", extra={"source": resolved.source.name, "seconds": exc.seconds})
            await asyncio.sleep(exc.seconds)
        except Exception as exc:
            logger.exception("telegram backfill failed", extra={"source": resolved.source.name})
            await self.db.upsert_source_health(
                source_id=resolved.source.id,
                service_name=self.settings.service_name,
                status="degraded",
                backfill_status="failed",
                last_error_at=datetime.now(UTC),
                last_error_message=str(exc),
            )

    async def handle_message(self, message: Any) -> None:
        channel_id = self.extract_channel_id(message)
        if channel_id is None:
            return

        resolved = self._resolved_by_channel_id.get(channel_id)
        if not resolved:
            return

        await self.persist_message(resolved, message)

    async def persist_message(self, resolved: ResolvedSource, message: Any) -> None:
        values = message_to_raw_item(
            source=resolved.source,
            channel_id=resolved.channel_id,
            public_username=resolved.public_username,
            message=message,
        )
        await self.db.upsert_raw_item(values)
        await self.db.upsert_source_health(
            source_id=resolved.source.id,
            service_name=self.settings.service_name,
            status="healthy",
            last_message_at=getattr(message, "date", None),
            last_success_at=datetime.now(UTC),
            metadata={"last_message_id": getattr(message, "id", None)},
        )
        logger.info(
            "telegram message persisted",
            extra={
                "source": resolved.source.name,
                "message_id": getattr(message, "id", None),
                "media_type": values["media_type"],
            },
        )

    @staticmethod
    def extract_channel_id(message: Any) -> int | None:
        chat = getattr(message, "chat", None)
        if isinstance(chat, (Channel, Chat, User)) and getattr(chat, "id", None) is not None:
            return int(chat.id)
        peer_id = getattr(message, "peer_id", None)
        if peer_id and getattr(peer_id, "channel_id", None) is not None:
            return int(peer_id.channel_id)
        if peer_id and getattr(peer_id, "chat_id", None) is not None:
            return int(peer_id.chat_id)
        return None
