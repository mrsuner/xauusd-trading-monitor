from __future__ import annotations

from typing import Any

import httpx

from .message import build_message, compact_text
from .models import ProviderResult, PublicOutboxItem
from .settings import Settings


class TelegramChannelProvider:
    def __init__(self, *, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def send(self, item: PublicOutboxItem, message: str) -> ProviderResult:
        if not self._settings.bot_token or not self._settings.channel_id:
            return ProviderResult(success=False, error_message="missing_telegram_channel_config", is_transient=False)

        result = await self._send_message(message, parse_mode=self._settings.parse_mode)
        if _is_parse_error(result) and self._settings.parse_mode == "HTML":
            fallback = build_message(item, parse_mode="plain", limit=self._settings.message_limit_chars)
            fallback_result = await self._send_message(fallback, parse_mode="plain")
            fallback_result.response_json = {
                "primary_error": result.response_json,
                "fallback": fallback_result.response_json,
            }
            return fallback_result
        return result

    async def _send_message(self, message: str, *, parse_mode: str) -> ProviderResult:
        assert self._settings.bot_token is not None
        assert self._settings.channel_id is not None

        url = f"https://api.telegram.org/bot{self._settings.bot_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self._settings.channel_id,
            "text": compact_text(message, limit=self._settings.message_limit_chars),
            "disable_web_page_preview": self._settings.disable_web_page_preview,
        }
        if parse_mode != "plain":
            payload["parse_mode"] = parse_mode

        try:
            response = await self._client.post(url, json=payload)
            response_json = _response_json(response)
        except httpx.HTTPError as exc:
            return ProviderResult(success=False, error_message=str(exc), is_transient=True)

        if response.status_code == 200 and response_json.get("ok") is True:
            return ProviderResult(success=True, status_code=response.status_code, response_json=response_json)

        retry_after = _telegram_retry_after(response_json)
        return ProviderResult(
            success=False,
            status_code=response.status_code,
            response_json=response_json,
            retry_after_seconds=retry_after,
            error_message=_provider_error(response_json) or response.text,
            is_transient=response.status_code == 429 or response.status_code >= 500,
        )


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {"raw_text": response.text}
    return data if isinstance(data, dict) else {"response": data}


def _telegram_retry_after(response_json: dict[str, Any]) -> int | None:
    parameters = response_json.get("parameters")
    if not isinstance(parameters, dict):
        return None
    retry_after = parameters.get("retry_after")
    return retry_after if isinstance(retry_after, int) else None


def _provider_error(response_json: dict[str, Any]) -> str | None:
    description = response_json.get("description")
    if isinstance(description, str):
        return description
    return None


def _is_parse_error(result: ProviderResult) -> bool:
    if result.success or result.status_code != 400:
        return False
    error = (result.error_message or "").lower()
    return "parse" in error or "can't find end tag" in error or "unsupported start tag" in error
