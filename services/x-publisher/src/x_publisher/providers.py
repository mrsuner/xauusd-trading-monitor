from __future__ import annotations

import time
from typing import Any

import httpx

from .models import ProviderResult
from .oauth import build_oauth1_header
from .settings import Settings


class XProvider:
    def __init__(self, *, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def send(self, post: str) -> ProviderResult:
        if not self._has_oauth1_config:
            return ProviderResult(success=False, error_message="missing_x_oauth1_config", is_transient=False)

        url = f"{self._settings.api_base_url}/tweets"
        headers = {
            "Authorization": build_oauth1_header(
                method="POST",
                url=url,
                consumer_key=self._settings.api_key or "",
                consumer_secret=self._settings.api_secret or "",
                token=self._settings.access_token or "",
                token_secret=self._settings.access_token_secret or "",
            ),
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"text": post}

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response_json = _response_json(response)
        except httpx.HTTPError as exc:
            return ProviderResult(success=False, error_message=str(exc), is_transient=True)

        if response.status_code in {200, 201} and _has_post_id(response_json):
            return ProviderResult(success=True, status_code=response.status_code, response_json=response_json)

        duplicate = _is_duplicate_error(response_json)
        retry_after = _retry_after_seconds(response)
        return ProviderResult(
            success=False,
            status_code=response.status_code,
            response_json=response_json,
            retry_after_seconds=retry_after,
            error_message=_provider_error(response_json) or response.text,
            is_transient=response.status_code == 429 or response.status_code >= 500,
            is_duplicate=duplicate,
        )

    @property
    def _has_oauth1_config(self) -> bool:
        return all(
            [
                self._settings.api_key,
                self._settings.api_secret,
                self._settings.access_token,
                self._settings.access_token_secret,
            ]
        )


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {"raw_text": response.text}
    return data if isinstance(data, dict) else {"response": data}


def _has_post_id(response_json: dict[str, Any]) -> bool:
    data = response_json.get("data")
    return isinstance(data, dict) and data.get("id") is not None


def _retry_after_seconds(response: httpx.Response) -> int | None:
    retry_after = response.headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return int(retry_after)
    reset_at = response.headers.get("x-rate-limit-reset")
    if reset_at and reset_at.isdigit():
        return max(1, int(reset_at) - int(time.time()))
    return None


def _provider_error(response_json: dict[str, Any]) -> str | None:
    detail = response_json.get("detail")
    if isinstance(detail, str):
        return detail
    title = response_json.get("title")
    if isinstance(title, str):
        return title
    errors = response_json.get("errors")
    if isinstance(errors, list) and errors:
        return str(errors[0])
    return None


def _is_duplicate_error(response_json: dict[str, Any]) -> bool:
    serialized = str(response_json).lower()
    return "duplicate" in serialized or "already" in serialized
