from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)
REDACTED = "[REDACTED]"
SENSITIVE_LOG_KEY_PARTS = ("authorization", "api_key", "bearer", "credential", "password", "secret", "signature", "token")


class ChatCompletionTransport:
    def __init__(self, *, base_url: str, api_key: str | None, timeout_seconds: float,
                 provider: str, api_provider: str, model: str, extra_headers: dict[str, str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.provider = provider
        self.api_provider = api_provider
        self.model = model
        self.extra_headers = extra_headers

    async def post(
        self,
        payload: dict[str, Any],
        *,
        ai_layer: str,
        request_kind: str,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/chat/completions"
        request_started = time.perf_counter()
        logger.debug(
            "ai_model_api_request",
            extra={
                "ai_layer": ai_layer,
                "request_kind": request_kind,
                "route_name": self.provider,
                "api_provider": self.api_provider,
                "model": self.model,
                "endpoint": endpoint,
                "timeout_seconds": self.timeout_seconds,
                "headers": _sanitize_for_log(headers),
                "payload": _sanitize_for_log(payload),
            },
        )
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
            except Exception as exc:
                latency_ms = int((time.perf_counter() - request_started) * 1000)
                logger.debug(
                    "ai_model_api_error",
                    extra={
                        "ai_layer": ai_layer,
                        "request_kind": request_kind,
                        "route_name": self.provider,
                        "api_provider": self.api_provider,
                        "model": self.model,
                        "endpoint": endpoint,
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    exc_info=True,
                )
                raise

            latency_ms = int((time.perf_counter() - request_started) * 1000)
            response_text = response.text
            try:
                response_body = response.json()
            except json.JSONDecodeError:
                response_body = None

            logger.debug(
                "ai_model_api_response",
                extra={
                    "ai_layer": ai_layer,
                    "request_kind": request_kind,
                    "route_name": self.provider,
                    "api_provider": self.api_provider,
                    "model": self.model,
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "response_headers": _sanitize_for_log(dict(response.headers)),
                    "response_body": _sanitize_for_log(response_body if response_body is not None else response_text),
                },
            )
            response.raise_for_status()
            if not isinstance(response_body, dict):
                raise ValueError("chat completion response must be a JSON object")
            return response_body

def _sanitize_for_log(value: Any, *, key: str = "") -> Any:
    if _is_sensitive_log_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {str(item_key): _sanitize_for_log(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_log(item, key=key) for item in value]
    return value

def _is_sensitive_log_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized.endswith("_tokens") or normalized == "tokens":
        return False
    return any(part in normalized.split("_") for part in SENSITIVE_LOG_KEY_PARTS) or any(
        part in normalized
        for part in (
            "api_key",
            "access_token",
            "bearer_token",
        )
    )
