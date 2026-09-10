from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from alert_dispatcher.models import AlertChannelStats, AlertPolicyRuntime, EventContext, EventTranslationContext, SourceContext
from alert_dispatcher.policy import notification_decisions


def make_event(
    *,
    severity: str,
    relevance_score: int,
    source_group: str = "iran_government",
    official_level: str = "official",
    priority: str = "P0",
    requires_confirmation: bool = True,
    pushover_alert_enabled: bool = True,
    telegram_min_severity: str = "B",
    pushover_min_severity: str = "A",
    alert_weight: int = 90,
) -> EventContext:
    return EventContext(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        event_type="IRAN_NUCLEAR",
        severity=severity,
        relevance_score=relevance_score,
        confidence=80,
        confirmation_state="unconfirmed",
        translations=[EventTranslationContext(language="zh-Hant", summary="測試事件摘要。")],
        requires_confirmation=requires_confirmation,
        source_group=source_group,
        source=SourceContext(
            id=uuid4(),
            name="IRNA",
            handle_or_url="@Irna_en",
            source_group=source_group,
            official_level=official_level,
            priority=priority,
            pushover_alert_enabled=pushover_alert_enabled,
            telegram_min_severity=telegram_min_severity,
            pushover_min_severity=pushover_min_severity,
            alert_weight=alert_weight,
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
    event = make_event(severity="B", relevance_score=72, pushover_min_severity="S")

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
        pushover_alert_enabled=False,
        telegram_min_severity="A",
        alert_weight=45,
    )

    decisions = notification_decisions(event)

    assert next(decision for decision in decisions if decision.channel == "telegram").delivery_status == "pending"
    assert next(decision for decision in decisions if decision.channel == "pushover").delivery_status == "skipped"


def test_c_low_relevance_event_skips_all_channels() -> None:
    event = make_event(severity="C", relevance_score=35)

    decisions = notification_decisions(event)

    assert all(decision.delivery_status == "skipped" for decision in decisions)


def test_pushover_respects_source_allowlist() -> None:
    event = make_event(severity="S", relevance_score=95, pushover_alert_enabled=False)

    decisions = notification_decisions(event)

    assert next(decision for decision in decisions if decision.channel == "telegram").delivery_status == "pending"
    assert next(decision for decision in decisions if decision.channel == "pushover").delivery_status == "skipped"


def test_backfill_telegram_only_mode_suppresses_pushover() -> None:
    event = make_event(severity="S", relevance_score=95)
    runtime = AlertPolicyRuntime(is_backfill=True, backfill_mode="telegram_only")

    decisions = notification_decisions(event, runtime=runtime)

    assert next(decision for decision in decisions if decision.channel == "telegram").delivery_status == "pending"
    assert next(decision for decision in decisions if decision.channel == "pushover").delivery_status == "skipped"


def test_source_rate_limit_suppresses_channel() -> None:
    event = make_event(
        severity="A",
        relevance_score=88,
        alert_weight=70,
    )
    event.source.alert_rate_limit_per_hour = 1
    runtime = AlertPolicyRuntime(
        telegram_stats=AlertChannelStats(sent_or_pending_1h=1),
        pushover_stats=AlertChannelStats(sent_or_pending_1h=0),
    )

    decisions = notification_decisions(event, runtime=runtime)

    assert next(decision for decision in decisions if decision.channel == "telegram").delivery_status == "skipped"
    assert next(decision for decision in decisions if decision.channel == "pushover").delivery_status == "pending"
