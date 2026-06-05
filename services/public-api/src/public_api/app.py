from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .db import Database, PublicRepository
from .models import PublicEventIngestRequest
from .security import timestamp_age_seconds, verify_signature
from .settings import Settings


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def create_app() -> FastAPI:
    settings = Settings()
    db = Database(settings.public_database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await db.connect()
        app.state.settings = settings
        app.state.db = db
        app.state.repository = PublicRepository(db, max_page_size=settings.max_page_size)
        try:
            yield
        finally:
            await db.close()

    app = FastAPI(title="XAUUSD Event Radar Public API", version="0.1.0", lifespan=lifespan)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-XER-Key-Id",
                "X-XER-Timestamp",
                "X-XER-Nonce",
                "X-XER-Signature",
            ],
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == status.HTTP_404_NOT_FOUND else "invalid_request"
        if exc.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            code = "unauthorized"
        if exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            code = "payload_too_large"
        return error_response(code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        return error_response("internal_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def repo(request: Request) -> PublicRepository:
        return request.app.state.repository

    def page_size_default(request: Request) -> int:
        return request.app.state.settings.default_page_size

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        db_ok = await request.app.state.db.ping()
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "error",
            "service": "public-api",
        }

    @app.post("/ingest/events")
    async def ingest_event(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        xer_key_id: Annotated[str | None, Header(alias="X-XER-Key-Id")] = None,
        xer_timestamp: Annotated[str | None, Header(alias="X-XER-Timestamp")] = None,
        xer_nonce: Annotated[str | None, Header(alias="X-XER-Nonce")] = None,
        xer_signature: Annotated[str | None, Header(alias="X-XER-Signature")] = None,
        repository: PublicRepository = Depends(repo),
    ) -> dict[str, Any]:
        body = await request.body()
        settings: Settings = request.app.state.settings
        if len(body) > settings.ingest_max_body_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

        try:
            body_obj = json.loads(body)
            idempotency_key = str(body_obj.get("idempotency_key") or idempotency_header or "")
        except json.JSONDecodeError:
            idempotency_key = idempotency_header or None
            await repository.record_rejected_ingest(
                raw_body=body,
                key_id=xer_key_id,
                nonce=xer_nonce,
                error_message="invalid_json",
                idempotency_key=idempotency_key,
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

        try:
            await _authorize_ingest(
                settings=settings,
                repository=repository,
                body=body,
                authorization=authorization,
                idempotency_key=idempotency_key,
                key_id=xer_key_id,
                timestamp=xer_timestamp,
                nonce=xer_nonce,
                signature=xer_signature,
            )
        except HTTPException as exc:
            await repository.record_rejected_ingest(
                raw_body=body,
                key_id=xer_key_id,
                nonce=xer_nonce,
                error_message=str(exc.detail),
                idempotency_key=idempotency_key,
            )
            raise

        try:
            payload = PublicEventIngestRequest.model_validate(body_obj)
            _validate_public_text_lengths(payload, settings)
        except (ValidationError, ValueError) as exc:
            await repository.record_rejected_ingest(
                raw_body=body,
                key_id=xer_key_id,
                nonce=xer_nonce,
                error_message=str(exc),
                idempotency_key=idempotency_key,
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid public event payload") from exc

        if idempotency_header and idempotency_header != payload.idempotency_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header mismatch")

        result = await repository.ingest_event(payload, raw_body=body, key_id=xer_key_id, nonce=xer_nonce)
        return result

    @app.get("/events")
    async def list_events(
        repository: PublicRepository = Depends(repo),
        default_page_size: int = Depends(page_size_default),
        severity: str | None = None,
        confirmation_state: str | None = None,
        tag: str | None = None,
        category: str | None = None,
        q: str | None = None,
        lang: str | None = None,
        from_time: Annotated[str | None, Query(alias="from")] = None,
        to_time: Annotated[str | None, Query(alias="to")] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        return await repository.list_events(
            page=page,
            page_size=page_size or default_page_size,
            lang=lang,
            severity=severity,
            confirmation_state=confirmation_state,
            tag=tag,
            category=category,
            q=q,
            from_time=from_time,
            to_time=to_time,
        )

    @app.get("/events/{public_event_id}")
    async def get_event(
        public_event_id: UUID,
        repository: PublicRepository = Depends(repo),
        lang: str | None = None,
    ) -> dict[str, Any]:
        event = await repository.get_event(public_event_id, lang=lang)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        return event

    @app.get("/tags")
    async def list_tags(repository: PublicRepository = Depends(repo)) -> dict[str, Any]:
        return {"items": await repository.list_tags()}

    @app.get("/categories")
    async def list_categories(repository: PublicRepository = Depends(repo)) -> dict[str, Any]:
        return {"items": await repository.list_categories()}

    @app.get("/stats/overview")
    async def stats_overview(repository: PublicRepository = Depends(repo)) -> dict[str, Any]:
        return await repository.overview_stats()

    return app


async def _authorize_ingest(
    *,
    settings: Settings,
    repository: PublicRepository,
    body: bytes,
    authorization: str | None,
    idempotency_key: str,
    key_id: str | None,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
) -> None:
    if settings.ingest_auth_mode == "bearer":
        if not settings.public_api_token:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PUBLIC_API_TOKEN is not configured")
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        token = authorization[7:].strip()
        if token != settings.public_api_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
        return

    if not settings.ingest_key_id or not settings.ingest_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PUBLIC_INGEST_KEY_ID/SECRET is not configured")
    if key_id != settings.ingest_key_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key id")
    if not timestamp or not nonce or not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing HMAC headers")
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing idempotency key")
    try:
        if timestamp_age_seconds(timestamp) > settings.ingest_timestamp_skew_seconds:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired timestamp")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid timestamp") from exc
    if await repository.nonce_seen(key_id=key_id, nonce=nonce):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Replay nonce")
    if not verify_signature(
        secret=settings.ingest_secret,
        timestamp=timestamp,
        nonce=nonce,
        idempotency_key=idempotency_key,
        body=body,
        signature=signature,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")


def _validate_public_text_lengths(payload: PublicEventIngestRequest, settings: Settings) -> None:
    title_fields = [payload.public_title_zh, payload.public_title_en]
    summary_fields = [payload.public_summary_zh, payload.public_summary_en]
    if settings.max_title_chars:
        for value in title_fields:
            if value and len(value) > settings.max_title_chars:
                raise ValueError("public title is too long")
    if settings.max_summary_chars:
        for value in summary_fields:
            if value and len(value) > settings.max_summary_chars:
                raise ValueError("public summary is too long")
