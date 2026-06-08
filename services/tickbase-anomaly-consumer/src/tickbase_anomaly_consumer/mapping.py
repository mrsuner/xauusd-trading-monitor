from __future__ import annotations

from dataclasses import dataclass

from .models import AnomalyEvent

# Deterministic relevance per severity band (0-100). Anomalies are pre-vetted
# numeric facts, so relevance is a fixed function of severity rather than a
# news-style score.
RELEVANCE_BY_SEVERITY = {"S": 95, "A": 85, "B": 70, "C": 55}

# Public Telegram channel only carries the larger moves.
PUBLIC_SEVERITIES = frozenset({"S", "A"})

# Friendly display names for common instruments; falls back to BASE/QUOTE.
_INSTRUMENT_NAMES = {
    ("metal", "XAU", "USD"): "黃金",
    ("metal", "XAG", "USD"): "白銀",
}

_DIRECTION_ZH = {"up": "上漲", "down": "下跌"}


@dataclass(frozen=True)
class SeverityThresholds:
    s_multiplier: float
    a_multiplier: float
    b_multiplier: float


@dataclass(frozen=True)
class MappedAnomaly:
    severity: str
    relevance_score: int
    title_zh: str
    summary_zh: str
    alert_message: str
    topic_tags: list[str]
    to_public: bool


def instrument_label(event: AnomalyEvent) -> str:
    name = _INSTRUMENT_NAMES.get((event.asset_class, event.base, event.quote))
    pair = f"{event.base}/{event.quote}"
    return f"{name} ({pair})" if name else pair


def window_label(window_secs: int) -> str:
    if window_secs % 3600 == 0:
        return f"{window_secs // 3600} 小時"
    if window_secs % 60 == 0:
        return f"{window_secs // 60} 分鐘"
    return f"{window_secs} 秒"


def change_ratio(event: AnomalyEvent) -> float:
    """observed change / rule threshold; >= 1.0 because the rule fired."""
    observed = abs(event.change_abs) if event.metric == "abs" else abs(event.change_pct)
    threshold = abs(event.threshold)
    if threshold == 0:
        return 1.0
    return observed / threshold


def classify_severity(event: AnomalyEvent, thresholds: SeverityThresholds) -> str:
    ratio = change_ratio(event)
    if ratio >= thresholds.s_multiplier:
        return "S"
    if ratio >= thresholds.a_multiplier:
        return "A"
    if ratio >= thresholds.b_multiplier:
        return "B"
    return "C"


def _magnitude_phrase(event: AnomalyEvent) -> str:
    if event.metric == "abs":
        return f"{event.change_abs:g} {event.quote}（{event.change_pct:+.2f}%）"
    return f"{event.change_pct:+.2f}%（{event.change_abs:g} {event.quote}）"


def build_summary_zh(event: AnomalyEvent) -> str:
    direction = _DIRECTION_ZH.get(event.direction, event.direction)
    return (
        f"{instrument_label(event)} 於 {window_label(event.window_secs)}內{direction} "
        f"{_magnitude_phrase(event)}，{event.value_start:g} → {event.value_end:g}"
        f"（rule={event.rule_id}）"
    )


def map_anomaly(event: AnomalyEvent, thresholds: SeverityThresholds) -> MappedAnomaly:
    severity = classify_severity(event, thresholds)
    summary = build_summary_zh(event)
    title = f"[{severity}] {instrument_label(event)} 行情異常"
    tags = ["market_anomaly", event.asset_class, f"{event.base}{event.quote}"]
    return MappedAnomaly(
        severity=severity,
        relevance_score=RELEVANCE_BY_SEVERITY[severity],
        title_zh=title,
        summary_zh=summary,
        alert_message=f"{title}\n\n{summary}",
        topic_tags=tags,
        to_public=severity in PUBLIC_SEVERITIES,
    )
