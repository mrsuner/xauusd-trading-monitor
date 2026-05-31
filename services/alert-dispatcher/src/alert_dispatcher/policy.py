from __future__ import annotations

from .message import build_pushover_message, build_pushover_title, build_telegram_message
from .models import AlertDecision, EventContext


AGGREGATOR_GROUPS = {"osint_aggregator", "market_squawk"}


def should_send_telegram(event: EventContext) -> bool:
    if event.severity in {"S", "A", "B"}:
        return True
    if event.relevance_score >= 85 and event.source.priority in {"P0", "P1"}:
        return True
    return event.relevance_score >= 70


def should_send_pushover(event: EventContext) -> bool:
    source_group = event.source.source_group or event.source_group
    if source_group in AGGREGATOR_GROUPS:
        return False
    if event.severity in {"S", "A"}:
        return True
    return event.relevance_score >= 85 and event.source.priority in {"P0", "P1"}


def is_emergency_candidate(event: EventContext) -> bool:
    source_group = event.source.source_group or event.source_group
    if event.severity != "S":
        return False
    if event.source.priority not in {"P0", "P1"}:
        return False
    if event.source.official_level not in {"official", "semi_official"}:
        return False
    if source_group in AGGREGATOR_GROUPS:
        return False
    return not event.requires_confirmation or event.confirmation_state in {"confirmed", "partially_confirmed"}


def pushover_priority(event: EventContext) -> str:
    if is_emergency_candidate(event):
        return "emergency"
    if event.severity == "S" or event.relevance_score >= 90:
        return "high"
    return "normal"


def notification_decisions(event: EventContext) -> list[AlertDecision]:
    decisions: list[AlertDecision] = []

    if should_send_telegram(event):
        decisions.append(
            AlertDecision(
                event_id=event.id,
                channel="telegram",
                priority="high" if event.severity == "S" else "normal",
                delivery_status="pending",
                message=build_telegram_message(event),
                dedupe_key=f"alert:{event.id}:telegram",
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
                error_message="policy_not_notify",
            )
        )

    if should_send_pushover(event):
        decisions.append(
            AlertDecision(
                event_id=event.id,
                channel="pushover",
                priority=pushover_priority(event),
                delivery_status="pending",
                message=f"{build_pushover_title(event)}\n\n{build_pushover_message(event)}",
                dedupe_key=f"alert:{event.id}:pushover",
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
                error_message="policy_not_notify",
            )
        )

    return decisions
