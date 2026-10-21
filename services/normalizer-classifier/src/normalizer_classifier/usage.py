from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal
from typing import Any

import tiktoken

from .models import AIModelCallUsage


PRICE_PER_MILLION: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("openrouter", "openai/gpt-6-luna"): (Decimal("0.10"), Decimal("0.50")),
    ("openai_compatible", "gpt-5.4-mini"): (Decimal("0.75"), Decimal("4.5")),
    ("openrouter", "openai/gpt-oss-20b"): (Decimal("0.029"), Decimal("0.14")),
    ("openrouter", "openai/gpt-oss-20b:free"): (Decimal("0"), Decimal("0")),
}


def request_hash(payload: dict[str, Any]) -> str:
    safe_payload = {
        "model": payload.get("model"),
        "messages": payload.get("messages", []),
        "response_format": payload.get("response_format"),
    }
    encoded = json.dumps(safe_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def estimate_messages_tokens(model: str, messages: list[dict[str, Any]]) -> int:
    encoding = encoding_for_model(model)
    total = 0
    for message in messages:
        total += 4
        total += len(encoding.encode(str(message.get("role") or "")))
        total += len(encoding.encode(content_to_text(message.get("content"))))
    return total + 2


def estimate_text_tokens(model: str, text: str) -> int:
    return len(encoding_for_model(model).encode(text))


def encoding_for_model(model: str):
    normalized_model = normalize_model_name(model)
    try:
        return tiktoken.encoding_for_model(normalized_model)
    except KeyError:
        try:
            return tiktoken.get_encoding("o200k_base")
        except ValueError:
            return tiktoken.get_encoding("cl100k_base")


def normalize_model_name(model: str) -> str:
    if "/" in model:
        model = model.rsplit("/", 1)[-1]
    if model.endswith(":free"):
        model = model.removesuffix(":free")
    return model


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def usage_from_response(body: dict[str, Any]) -> dict[str, int | None]:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    result: dict[str, int | None] = {}
    for field, key in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"),
                       ("total_tokens", "total_tokens")):
        value = usage.get(key)
        try:
            count = int(value) if value is not None and not isinstance(value, bool) else None
        except (ValueError, TypeError, OverflowError):
            count = None
        result[field] = count if count is not None and count >= 0 else None
    return result


def estimated_cost_usd(provider: str, model_name: str, input_tokens: int | None, output_tokens: int | None) -> Decimal | None:
    pricing = PRICE_PER_MILLION.get((provider, model_name))
    if pricing is None or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = pricing
    cost = Decimal(input_tokens or 0) * input_price / Decimal(1_000_000)
    cost += Decimal(output_tokens or 0) * output_price / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


def build_model_call_usage(
    *,
    route_name: str,
    api_provider: str,
    model: str,
    response_format: str,
    payload: dict[str, Any],
    ai_layer: str,
    request_kind: str,
    started: float,
    success: bool,
    body: dict[str, Any] | None = None,
    output_text: str | None = None,
    error: Exception | None = None,
) -> AIModelCallUsage:
    latency_ms = int((time.perf_counter() - started) * 1000)
    response_usage = usage_from_response(body or {})
    input_tokens = response_usage["input_tokens"]
    output_tokens = response_usage["output_tokens"]
    total_tokens = response_usage["total_tokens"]
    raw_usage = (body or {}).get("usage")
    usage_json = dict(raw_usage) if isinstance(raw_usage, dict) else {}
    usage_estimated = False
    estimation_errors: dict[str, str] = {}

    if input_tokens is None:
        try:
            input_tokens = estimate_messages_tokens(model, payload.get("messages") or [])
        except Exception as exc:
            # Tokenizer/cache failures must not replace the original model error
            # or prevent an already-issued request from being recorded.
            estimation_errors["input_tokens"] = type(exc).__name__
        usage_estimated = True
    if output_tokens is None and output_text is not None:
        try:
            output_tokens = estimate_text_tokens(model, output_text)
        except Exception as exc:
            estimation_errors["output_tokens"] = type(exc).__name__
        usage_estimated = True
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
        usage_estimated = True

    if usage_estimated:
        usage_json["estimated"] = True
    if estimation_errors:
        usage_json["estimation_errors"] = estimation_errors

    return AIModelCallUsage(
        ai_layer=ai_layer,
        route_name=route_name,
        provider=api_provider,
        model_name=model,
        request_kind=request_kind,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd(api_provider, model, input_tokens, output_tokens),
        latency_ms=latency_ms,
        success=success,
        error_type=type(error).__name__ if error else None,
        error_message=str(error)[:2000] if error else None,
        response_format=response_format,
        usage_json=usage_json,
        request_hash=request_hash(payload),
    )
