from __future__ import annotations

from typing import Any

import httpx

from .message import compact_text
from .models import AlertDelivery, ProviderResult
from .security import sanitize_provider_response, sanitize_text
from .settings import Settings


class AlertProvider:
    async def send(self, alert: AlertDelivery) -> ProviderResult:
        raise NotImplementedError


class TelegramProvider(AlertProvider):
    def __init__(self, *, bot_token: str | None, chat_id: str | None, client: httpx.AsyncClient) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = client

    async def send(self, alert: AlertDelivery) -> ProviderResult:
        if not self._bot_token or not self._chat_id:
            return ProviderResult(success=False, error_message="missing_telegram_config", is_transient=False)

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": compact_text(alert.message, limit=3900),
            "disable_web_page_preview": True,
        }
        try:
            response = await self._client.post(url, json=payload)
            response_json = _telegram_response(response, _response_json(response))
        except httpx.HTTPError as exc:
            return ProviderResult(success=False, error_message=sanitize_text(exc), is_transient=True)

        if response.status_code == 200 and response_json.get("ok") is True:
            return ProviderResult(success=True, status_code=response.status_code, response_json=response_json)

        retry_after = _telegram_retry_after(response_json)
        return ProviderResult(
            success=False,
            status_code=response.status_code,
            response_json=response_json,
            retry_after_seconds=retry_after,
            error_message=_provider_error(response_json) or sanitize_text(response.text),
            is_transient=response.status_code == 429 or response.status_code >= 500,
        )


class PushoverProvider(AlertProvider):
    def __init__(
        self,
        *,
        app_token: str | None,
        user_key: str | None,
        emergency_retry_seconds: int,
        emergency_expire_seconds: int,
        client: httpx.AsyncClient,
    ) -> None:
        self._app_token = app_token
        self._user_key = user_key
        self._emergency_retry_seconds = emergency_retry_seconds
        self._emergency_expire_seconds = emergency_expire_seconds
        self._client = client

    async def send(self, alert: AlertDelivery) -> ProviderResult:
        if not self._app_token or not self._user_key:
            return ProviderResult(success=False, error_message="missing_pushover_config", is_transient=False)

        title, message = _split_pushover_message(alert.message)
        priority = _pushover_priority_value(alert.priority)
        payload: dict[str, Any] = {
            "token": self._app_token,
            "user": self._user_key,
            "title": compact_text(title, limit=250),
            "message": compact_text(message, limit=950),
            "priority": priority,
        }
        if priority == 2:
            payload["retry"] = self._emergency_retry_seconds
            payload["expire"] = self._emergency_expire_seconds

        try:
            response = await self._client.post("https://api.pushover.net/1/messages.json", data=payload)
            response_json = _pushover_response(response, _response_json(response))
        except httpx.HTTPError as exc:
            return ProviderResult(success=False, error_message=sanitize_text(exc), is_transient=True)

        if response.status_code == 200 and response_json.get("status") == 1:
            return ProviderResult(success=True, status_code=response.status_code, response_json=response_json)

        return ProviderResult(
            success=False,
            status_code=response.status_code,
            response_json=response_json,
            error_message=_provider_error(response_json) or sanitize_text(response.text),
            is_transient=response.status_code == 429 or response.status_code >= 500,
        )


def build_providers(settings: Settings, client: httpx.AsyncClient) -> dict[str, AlertProvider]:
    providers: dict[str, AlertProvider] = {}
    if settings.enable_telegram_alerts:
        providers["telegram"] = TelegramProvider(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            client=client,
        )
    if settings.enable_pushover_alerts:
        providers["pushover"] = PushoverProvider(
            app_token=settings.pushover_app_token,
            user_key=settings.pushover_user_key,
            emergency_retry_seconds=settings.pushover_emergency_retry_seconds,
            emergency_expire_seconds=settings.pushover_emergency_expire_seconds,
            client=client,
        )
    return providers


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {"raw_text": sanitize_text(response.text)}
    return sanitize_provider_response(data if isinstance(data, dict) else {"response": data})


def _telegram_response(response: httpx.Response, data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("result")
    clean: dict[str, Any] = {
        "provider": "telegram",
        "status_code": response.status_code,
        "ok": data.get("ok"),
    }
    if isinstance(result, dict) and result.get("message_id") is not None:
        clean["result"] = {"message_id": result["message_id"]}
    if data.get("description"):
        clean["description"] = data["description"]
    parameters = data.get("parameters")
    if isinstance(parameters, dict) and parameters.get("retry_after") is not None:
        clean["parameters"] = {"retry_after": parameters["retry_after"]}
    return clean


def _pushover_response(response: httpx.Response, data: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {
        "provider": "pushover",
        "status_code": response.status_code,
        "status": data.get("status"),
    }
    for key in ("request", "receipt", "errors", "error"):
        if key in data:
            clean[key] = data[key]
    return sanitize_provider_response(clean)


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
    errors = response_json.get("errors")
    if isinstance(errors, list):
        return "; ".join(str(error) for error in errors)
    if isinstance(errors, str):
        return errors
    return None


def _pushover_priority_value(priority: str) -> int:
    if priority == "emergency":
        return 2
    if priority == "high":
        return 1
    return 0


def _split_pushover_message(message: str) -> tuple[str, str]:
    if "\n\n" not in message:
        return "XAUUSD Event Radar", message
    title, body = message.split("\n\n", 1)
    return title, body
