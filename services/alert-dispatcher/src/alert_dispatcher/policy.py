from __future__ import annotations

from datetime import datetime, timezone

from .message import build_pushover_message, build_pushover_title, build_telegram_message
from .models import AlertChannelStats, AlertDecision, AlertPolicyRuntime, EventContext


AGGREGATOR_GROUPS = {"osint_aggregator", "market_squawk"}
SEVERITY_ORDER = {"S": 4, "A": 3, "B": 2, "C": 1}
SEVERITY_SCORE = {"S": 50, "A": 35, "B": 15, "C": 0}
PRIORITY_SCORE = {"P0": 20, "P1": 12, "P2": 4, "P3": 0}
OFFICIAL_LEVEL_SCORE = {
    "official": 20,
    "semi_official": 12,
    "unofficial_mirror": 6,
    "unofficial": 0,
    "aggregator": -8,
}


def severity_at_least(actual: str, minimum: str) -> bool:
    return SEVERITY_ORDER.get(actual, 0) >= SEVERITY_ORDER.get(minimum, 0)


def alert_score(event: EventContext) -> int:
    source_group = event.source.source_group or event.source_group
    score = 0
    score += SEVERITY_SCORE.get(event.severity, 0)
    score += max(0, min(event.relevance_score, 100)) // 5
    score += PRIORITY_SCORE.get(event.source.priority or "", 0)
    score += OFFICIAL_LEVEL_SCORE.get(event.source.official_level or "", 0)
    score += max(0, min(event.source.alert_weight, 100)) // 5

    if event.requires_confirmation and event.confirmation_state not in {"confirmed", "partially_confirmed"}:
        score -= 15
    if source_group in AGGREGATOR_GROUPS:
        score -= 20
    if event.confidence is not None and event.confidence < 60:
        score -= 10
    return max(0, score)


def rate_limited(event: EventContext, stats: AlertChannelStats, *, now: datetime | None = None) -> bool:
    if event.source.alert_rate_limit_per_hour is not None:
        if stats.sent_or_pending_1h >= event.source.alert_rate_limit_per_hour:
            return True

    if event.source.alert_cooldown_minutes and stats.last_alert_at:
        current = now or datetime.now(timezone.utc)
        last_alert_at = stats.last_alert_at
        if last_alert_at.tzinfo is None:
            last_alert_at = last_alert_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = (current - last_alert_at).total_seconds()
        if elapsed_seconds < event.source.alert_cooldown_minutes * 60:
            return True

    return False


def should_send_telegram(event: EventContext, runtime: AlertPolicyRuntime, score: int) -> bool:
    if runtime.is_backfill and runtime.backfill_mode == "skip":
        return False
    if not event.source.telegram_alert_enabled:
        return False
    if not severity_at_least(event.severity, event.source.telegram_min_severity):
        return False
    if rate_limited(event, runtime.telegram_stats):
        return False
    if event.severity == "S":
        return score >= 35
    return score >= 45


def should_send_pushover(event: EventContext, runtime: AlertPolicyRuntime, score: int) -> bool:
    if runtime.is_backfill and runtime.backfill_mode in {"skip", "telegram_only"}:
        return False
    if not event.source.pushover_alert_enabled:
        return False
    if not severity_at_least(event.severity, event.source.pushover_min_severity):
        return False
    source_group = event.source.source_group or event.source_group
    if source_group in AGGREGATOR_GROUPS:
        return False
    if event.source.official_level == "aggregator":
        return False
    if rate_limited(event, runtime.pushover_stats):
        return False
    return score >= 85


def is_emergency_candidate(event: EventContext, score: int) -> bool:
    source_group = event.source.source_group or event.source_group
    if event.severity != "S":
        return False
    if score < 95:
        return False
    if event.source.priority not in {"P0", "P1"}:
        return False
    if source_group in AGGREGATOR_GROUPS:
        return False
    if event.source.official_level not in {"official", "semi_official"}:
        return False
    return not event.requires_confirmation or event.confirmation_state in {"confirmed", "partially_confirmed"}


def pushover_priority(event: EventContext, score: int) -> str:
    if is_emergency_candidate(event, score):
        return "emergency"
    if event.severity == "S" or score >= 95:
        return "high"
    return "normal"


def notification_decisions(event: EventContext, runtime: AlertPolicyRuntime | None = None) -> list[AlertDecision]:
    runtime = runtime or AlertPolicyRuntime()
    score = alert_score(event)
    decisions: list[AlertDecision] = []

    if should_send_telegram(event, runtime, score):
        decisions.append(
            AlertDecision(
                event_id=event.id,
                channel="telegram",
                priority="high" if event.severity == "S" else "normal",
                delivery_status="pending",
                message=build_telegram_message(event),
                dedupe_key=f"alert:{event.id}:telegram",
                alert_score=score,
            )
        )
    else:
        decisions.append(
            AlertDecision(
                event_id=event.id,
                channel="telegram",
                priority="normal",
                delivery_status="skipped",
                message="Skipped by notification policy.",
                dedupe_key=f"alert:{event.id}:telegram",
                alert_score=score,
                error_message="policy_not_notify",
            )
        )

    if should_send_pushover(event, runtime, score):
        decisions.append(
            AlertDecision(
                event_id=event.id,
                channel="pushover",
                priority=pushover_priority(event, score),
                delivery_status="pending",
                message=f"{build_pushover_title(event)}\n\n{build_pushover_message(event)}",
                dedupe_key=f"alert:{event.id}:pushover",
                alert_score=score,
            )
        )
    else:
        decisions.append(
            AlertDecision(
                event_id=event.id,
                channel="pushover",
                priority="normal",
                delivery_status="skipped",
                message="Skipped by notification policy.",
                dedupe_key=f"alert:{event.id}:pushover",
                alert_score=score,
                error_message="policy_not_notify",
            )
        )

    return decisions
