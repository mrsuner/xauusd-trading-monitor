from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnomalyEvent(BaseModel):
    """One anomaly event as published by tickbase's feed API.

    Field shape matches GET /v1/anomaly-events and the SSE `data:` payload.
    `id` is monotonic and is used as the idempotency key.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    rule_id: str
    asset_class: str
    base: str
    quote: str
    direction: str  # "up" | "down"
    metric: str  # "abs" | "pct"
    window_secs: int
    threshold: float
    change_abs: float
    change_pct: float
    value_start: float
    value_end: float
    obs_count: int
    window_start: datetime
    triggered_at: datetime
