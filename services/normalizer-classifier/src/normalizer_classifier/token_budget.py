from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import tiktoken


class ModelBudgetError(RuntimeError):
    pass


def source_tokens(text: str) -> int:
    try:
        return len(tiktoken.get_encoding("o200k_base").encode(text, disallowed_special=()))
    except Exception as exc:
        raise ModelBudgetError("token_estimation_failed") from exc


@dataclass
class RequestTokenBudget:
    db: Any
    raw_item_id: Any
    item_limit: int
    daily_limit: int

    async def reserve(self, tokens: int) -> None:
        try:
            reason = await self.db.reserve_ai_tokens(
                raw_item_id=self.raw_item_id, tokens=tokens,
                item_limit=self.item_limit, daily_limit=self.daily_limit,
            )
        except Exception as exc:
            raise ModelBudgetError("token_budget_store_unavailable") from exc
        if reason:
            raise ModelBudgetError(reason)


async def prepare_bounded_request(
    client: Any, payload: dict[str, Any], *, output_limit: int,
    token_budget: RequestTokenBudget | None,
) -> None:
    payload["max_tokens"] = output_limit
    # Include schema and repair feedback as well as messages, with estimation headroom.
    estimated = source_tokens(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    input_reserved = math.ceil(estimated * 1.25) + 256
    if input_reserved > client.max_input_tokens:
        raise ModelBudgetError("request_input_token_limit_exceeded")
    if token_budget is not None:
        await token_budget.reserve(input_reserved + output_limit)
