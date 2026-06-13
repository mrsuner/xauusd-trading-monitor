from __future__ import annotations

import json
import time
from uuid import uuid4

import httpx

from .models import PublicApiResult
from .security import sign_ingest_request
from .security_scrub import sanitize_provider_response, sanitize_text
from .settings import Settings


class PublicApiProvider:
    def __init__(self, *, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    async def send(self, payload: dict, *, idempotency_key: str, ingest_path: str | None = None) -> PublicApiResult:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        if self.settings.auth_mode == "bearer":
            if not self.settings.sync_api_key:
                return PublicApiResult(success=False, error_message="PUBLIC_SYNC_API_KEY is not configured")
            headers["Authorization"] = f"Bearer {self.settings.sync_api_key}"
        else:
            if not self.settings.sync_key_id or not self.settings.sync_secret:
                return PublicApiResult(success=False, error_message="PUBLIC_SYNC_KEY_ID/SECRET is not configured")
            timestamp = str(int(time.time()))
            nonce = str(uuid4())
            headers.update(
                {
                    "X-XER-Key-Id": self.settings.sync_key_id,
                    "X-XER-Timestamp": timestamp,
                    "X-XER-Nonce": nonce,
                    "X-XER-Signature": sign_ingest_request(
                        secret=self.settings.sync_secret,
                        timestamp=timestamp,
                        nonce=nonce,
                        idempotency_key=idempotency_key,
                        body=body,
                    ),
                }
            )

        try:
            response = await self.client.post(self._ingest_url(ingest_path), content=body, headers=headers)
        except httpx.TimeoutException as exc:
            return PublicApiResult(success=False, is_transient=True, error_message=sanitize_text(f"timeout:{exc}"))
        except httpx.HTTPError as exc:
            return PublicApiResult(success=False, is_transient=True, error_message=sanitize_text(f"http_error:{exc}"))

        response_json = _public_api_response(response, _response_json(response))
        public_event_id = _public_event_id(response_json)
        public_raw_item_id = _public_raw_item_id(response_json)
        if response.status_code in {200, 201, 202}:
            status = str(response_json.get("status") or "")
            return PublicApiResult(
                success=True,
                status_code=response.status_code,
                response_json=response_json,
                public_event_id=public_event_id,
                public_raw_item_id=public_raw_item_id,
                is_duplicate=status == "duplicate",
            )
        if response.status_code == 409 and (public_event_id or public_raw_item_id):
            return PublicApiResult(
                success=True,
                status_code=response.status_code,
                response_json=response_json,
                public_event_id=public_event_id,
                public_raw_item_id=public_raw_item_id,
                is_duplicate=True,
            )
        retry_after = _retry_after(response.headers.get("Retry-After"))
        return PublicApiResult(
            success=False,
            status_code=response.status_code,
            response_json=response_json,
            error_message=_error_message(response, response_json),
            is_transient=response.status_code in {408, 429} or response.status_code >= 500,
            retry_after_seconds=retry_after,
        )

    def _ingest_url(self, ingest_path: str | None) -> str:
        if ingest_path is None:
            return self.settings.ingest_url
        if not self.settings.public_api_base_url:
            raise ValueError("PUBLIC_API_BASE_URL is required")
        path = ingest_path if ingest_path.startswith("/") else f"/{ingest_path}"
        return f"{self.settings.public_api_base_url}{path}"


def _response_json(response: httpx.Response) -> dict:
    try:
        value = response.json()
    except ValueError:
        return {"text": sanitize_text(response.text)}
    return value if isinstance(value, dict) else {"data": sanitize_provider_response(value)}


def _public_api_response(response: httpx.Response, data: dict) -> dict:
    clean: dict = {
        "provider": "public-api",
        "status_code": response.status_code,
    }
    for key in ("status", "public_event_id", "public_raw_item_id", "idempotency_key", "schema_version", "error", "detail"):
        if key in data:
            clean[key] = sanitize_provider_response(data[key]) if key in {"error", "detail"} else data[key]
    return clean


def _public_event_id(response_json: dict) -> str | None:
    value = response_json.get("public_event_id")
    return str(value) if value else None


def _public_raw_item_id(response_json: dict) -> str | None:
    value = response_json.get("public_raw_item_id")
    return str(value) if value else None


def _error_message(response: httpx.Response, response_json: dict) -> str:
    error = response_json.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if response_json.get("detail"):
        return str(response_json["detail"])
    return f"public_api_http_{response.status_code}"


def _retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
