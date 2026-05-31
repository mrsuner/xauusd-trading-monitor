from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import Database
from .repository import (
    DashboardRepository,
    build_alerts_query,
    build_events_query,
    build_processing_query,
    build_raw_items_query,
    build_source_health_query,
    build_sources_query,
)
from .settings import Settings


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app() -> FastAPI:
    settings = Settings()
    db = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await db.connect()
        app.state.settings = settings
        app.state.db = db
        app.state.repository = DashboardRepository(db, max_page_size=settings.max_page_size)
        try:
            yield
        finally:
            await db.close()

    app = FastAPI(title="XAUUSD Event Radar Dashboard API", version="0.1.0", lifespan=lifespan)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Authorization", "X-API-Token", "Content-Type"],
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == status.HTTP_404_NOT_FOUND else "invalid_request"
        if exc.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            code = "unauthorized"
        return error_response(code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        return error_response("internal_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    async def require_token(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
    ) -> None:
        expected = request.app.state.settings.api_token
        if not expected:
            return

        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        elif x_api_token:
            token = x_api_token.strip()

        if token != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")

    def repo(request: Request) -> DashboardRepository:
        return request.app.state.repository

    def page_size_default(request: Request) -> int:
        return request.app.state.settings.default_page_size

    async def list_response(
        repository: DashboardRepository,
        builder: Any,
        page: int,
        page_size: int | None,
        default_page_size: int,
    ) -> dict[str, Any]:
        return await repository.list_page(
            builder,
            page=page,
            page_size=page_size or default_page_size,
        )

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        db_ok = await request.app.state.db.ping()
        return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error", "service": "dashboard-api"}

    @app.get("/stats/overview", dependencies=[Depends(require_token)])
    async def stats_overview(repository: DashboardRepository = Depends(repo)) -> dict[str, Any]:
        return await repository.overview_stats()

    @app.get("/sources", dependencies=[Depends(require_token)])
    async def list_sources(
        repository: DashboardRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        source_type: str | None = None,
        source_group: str | None = None,
        priority: str | None = None,
        enabled: bool | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        builder = build_sources_query(
            {
                "source_type": source_type,
                "source_group": source_group,
                "priority": priority,
                "enabled": enabled,
            }
        )
        return await list_response(repository, builder, page, page_size, default_page_size)

    @app.get("/sources/{source_id}", dependencies=[Depends(require_token)])
    async def get_source(source_id: UUID, repository: DashboardRepository = Depends(repo)) -> dict[str, Any]:
        source = await repository.get_source(source_id)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        return source

    @app.get("/source-health", dependencies=[Depends(require_token)])
    async def list_source_health(
        repository: DashboardRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        service_name: str | None = None,
        status_filter: Annotated[str | None, Query(alias="status")] = None,
        source_type: str | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        builder = build_source_health_query(
            {
                "service_name": service_name,
                "status": status_filter,
                "source_type": source_type,
            }
        )
        return await list_response(repository, builder, page, page_size, default_page_size)

    @app.get("/raw-items", dependencies=[Depends(require_token)])
    async def list_raw_items(
        repository: DashboardRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        source_id: UUID | None = None,
        source_type: str | None = None,
        source_group: str | None = None,
        priority: str | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        ingested_from: datetime | None = None,
        ingested_to: datetime | None = None,
        q: str | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        builder = build_raw_items_query(
            {
                "source_id": source_id,
                "source_type": source_type,
                "source_group": source_group,
                "priority": priority,
                "published_from": published_from,
                "published_to": published_to,
                "ingested_from": ingested_from,
                "ingested_to": ingested_to,
                "q": q,
            }
        )
        return await list_response(repository, builder, page, page_size, default_page_size)

    @app.get("/raw-items/{raw_item_id}", dependencies=[Depends(require_token)])
    async def get_raw_item(raw_item_id: UUID, repository: DashboardRepository = Depends(repo)) -> dict[str, Any]:
        raw_item = await repository.get_raw_item(raw_item_id)
        if not raw_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw item not found")
        return raw_item

    @app.get("/processing", dependencies=[Depends(require_token)])
    async def list_processing(
        repository: DashboardRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        status_filter: Annotated[str | None, Query(alias="status")] = None,
        stage: str | None = None,
        is_relevant: bool | None = None,
        min_relevance_score: Annotated[int | None, Query(ge=0, le=100)] = None,
        model_provider: str | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        builder = build_processing_query(
            {
                "status": status_filter,
                "stage": stage,
                "is_relevant": is_relevant,
                "min_relevance_score": min_relevance_score,
                "model_provider": model_provider,
            }
        )
        return await list_response(repository, builder, page, page_size, default_page_size)

    @app.get("/events", dependencies=[Depends(require_token)])
    async def list_events(
        repository: DashboardRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        severity: str | None = None,
        event_type: str | None = None,
        source_group: str | None = None,
        min_relevance_score: Annotated[int | None, Query(ge=0, le=100)] = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        builder = build_events_query(
            {
                "severity": severity,
                "event_type": event_type,
                "source_group": source_group,
                "min_relevance_score": min_relevance_score,
                "created_from": created_from,
                "created_to": created_to,
            }
        )
        return await list_response(repository, builder, page, page_size, default_page_size)

    @app.get("/events/{event_id}", dependencies=[Depends(require_token)])
    async def get_event(event_id: UUID, repository: DashboardRepository = Depends(repo)) -> dict[str, Any]:
        event = await repository.get_event(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        return event

    @app.get("/alerts", dependencies=[Depends(require_token)])
    async def list_alerts(
        repository: DashboardRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        channel: str | None = None,
        delivery_status: str | None = None,
        priority: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        builder = build_alerts_query(
            {
                "channel": channel,
                "delivery_status": delivery_status,
                "priority": priority,
                "created_from": created_from,
                "created_to": created_to,
            }
        )
        return await list_response(repository, builder, page, page_size, default_page_size)

    return app
