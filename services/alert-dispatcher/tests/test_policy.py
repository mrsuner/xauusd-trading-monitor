from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from alert_dispatcher.models import EventContext, SourceContext
from alert_dispatcher.policy import notification_decisions


def make_event(
    *,
    severity: str,
    relevance_score: int,
    source_group: str = "iran_government",
    official_level: str = "official",
    priority: str = "P0",
    requires_confirmation: bool = True,
) -> EventContext:
    return EventContext(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        event_type="IRAN_NUCLEAR",
        severity=severity,
        relevance_score=relevance_score,
        confidence=80,
        confirmation_state="unconfirmed",
        summary_zh="測試事件摘要。",
        requires_confirmation=requires_confirmation,
        source_group=source_group,
        source=SourceContext(
            id=uuid4(),
            name="IRNA",
            handle_or_url="@Irna_en",
            source_group=source_group,
            official_level=official_level,
            priority=priority,
        ),
    )


def test_a_event_sends_telegram_and_pushover() -> None:
    event = make_event(severity="A", relevance_score=82)

    decisions = notification_decisions(event)

    assert {(decision.channel, decision.delivery_status) for decision in decisions} == {
        ("telegram", "pending"),
        ("pushover", "pending"),
    }


def test_b_event_only_sends_telegram() -> None:
    event = make_event(severity="B", relevance_score=72)

    decisions = notification_decisions(event)

    assert next(decision for decision in decisions if decision.channel == "telegram").delivery_status == "pending"
    assert next(decision for decision in decisions if decision.channel == "pushover").delivery_status == "skipped"


def test_aggregator_does_not_send_pushover() -> None:
    event = make_event(
        severity="S",
        relevance_score=95,
        source_group="osint_aggregator",
        official_level="aggregator",
        priority="P2",
    )

    decisions = notification_decisions(event)

    assert next(decision for decision in decisions if decision.channel == "telegram").delivery_status == "pending"
    assert next(decision for decision in decisions if decision.channel == "pushover").delivery_status == "skipped"


def test_c_low_relevance_event_skips_all_channels() -> None:
    event = make_event(severity="C", relevance_score=35)

    decisions = notification_decisions(event)

    assert all(decision.delivery_status == "skipped" for decision in decisions)
