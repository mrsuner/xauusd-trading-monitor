from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

import tiktoken


PRICE_PER_MILLION: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("openai_compatible", "gpt-5.4-mini"): (Decimal("0.75"), Decimal("4.5")),
    ("openrouter", "openai/gpt-oss-20b"): (Decimal("0.029"), Decimal("0.14")),
    ("openrouter", "openai/gpt-oss-20b:free"): (Decimal("0"), Decimal("0")),
}


def infer_api_provider(base_url: str) -> str:
    if "openrouter.ai" in base_url:
        return "openrouter"
    return "openai_compatible"


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
    usage = body.get("usage") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    return {
        "input_tokens": int(input_tokens) if input_tokens is not None else None,
        "output_tokens": int(output_tokens) if output_tokens is not None else None,
        "total_tokens": int(total_tokens) if total_tokens is not None else None,
    }


def estimated_cost_usd(provider: str, model_name: str, input_tokens: int | None, output_tokens: int | None) -> Decimal | None:
    pricing = PRICE_PER_MILLION.get((provider, model_name))
    if pricing is None:
        return None
    input_price, output_price = pricing
    cost = Decimal(input_tokens or 0) * input_price / Decimal(1_000_000)
    cost += Decimal(output_tokens or 0) * output_price / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))
