from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from event_router.models import AlertChannelStats, EventContext, RawItemContext, RoutePolicyRuntime, SourceContext
from event_router.policy import route_results
from event_router.settings import Settings


def make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {"DATABASE_URL": "postgresql://example"}
    defaults.update(overrides)
    return Settings(**defaults)


def make_event(
    *,
    severity: str,
    relevance_score: int,
    title: str | None = None,
    summary_en: str | None = None,
    source_group: str = "iran_government",
    official_level: str = "official",
    priority: str = "P0",
    requires_confirmation: bool = False,
    confirmation_state: str = "confirmed",
    pushover_alert_enabled: bool = True,
    telegram_min_severity: str = "B",
    pushover_min_severity: str = "A",
    alert_weight: int = 90,
    url: str | None = "https://example.com/item",
) -> EventContext:
    return EventContext(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        event_type="IRAN_NUCLEAR",
        severity=severity,
        relevance_score=relevance_score,
        confidence=80,
        confirmation_state=confirmation_state,
        title=title,
        summary_zh="測試事件摘要。",
        summary_en=summary_en,
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
        raw_item=RawItemContext(title="Source title", url=url),
        topic_tags=["iran", "nuclear"],
    )


def by_route(results: list, route_key: str):
    return next(result for result in results if result.route_key == route_key)


def test_a_event_routes_private_and_public_telegram() -> None:
    event = make_event(severity="A", relevance_score=82)

    results = route_results(event, RoutePolicyRuntime(), make_settings())

    assert by_route(results, "private.telegram").queued is True
    assert by_route(results, "private.pushover").queued is True
    assert by_route(results, "public.telegram_channel").queued is True
    assert by_route(results, "public.website").queued is False
    assert by_route(results, "public.x").queued is False


def test_b_event_can_skip_public_channel_below_relevance_policy() -> None:
    event = make_event(severity="B", relevance_score=72, pushover_min_severity="S")

    results = route_results(event, RoutePolicyRuntime(), make_settings())

    assert by_route(results, "private.telegram").queued is True
    assert by_route(results, "private.pushover").queued is False
    assert by_route(results, "public.telegram_channel").queued is False
    assert by_route(results, "public.telegram_channel").reason == "below_public_severity_policy"


def test_aggregator_does_not_route_pushover_or_public_without_confirmation() -> None:
    event = make_event(
        severity="S",
        relevance_score=95,
        source_group="osint_aggregator",
        official_level="aggregator",
        priority="P2",
        requires_confirmation=True,
        confirmation_state="unconfirmed",
        pushover_alert_enabled=False,
        telegram_min_severity="A",
        alert_weight=45,
    )

    results = route_results(event, RoutePolicyRuntime(), make_settings())

    assert by_route(results, "private.telegram").queued is True
    assert by_route(results, "private.pushover").queued is False
    assert by_route(results, "public.telegram_channel").queued is False
    assert by_route(results, "public.telegram_channel").reason == "aggregator_requires_confirmation"


def test_source_rate_limit_suppresses_private_channel() -> None:
    event = make_event(severity="A", relevance_score=88, alert_weight=70)
    event.source.alert_rate_limit_per_hour = 1
    runtime = RoutePolicyRuntime(
        telegram_stats=AlertChannelStats(sent_or_pending_1h=1),
        pushover_stats=AlertChannelStats(sent_or_pending_1h=0),
    )

    results = route_results(event, runtime, make_settings())

    assert by_route(results, "private.telegram").queued is False
    assert by_route(results, "private.telegram").reason == "source_rate_limited"
    assert by_route(results, "private.pushover").queued is True


def test_public_channel_requires_public_url() -> None:
    event = make_event(severity="A", relevance_score=90, url=None)

    results = route_results(event, RoutePolicyRuntime(), make_settings())

    assert by_route(results, "public.telegram_channel").queued is False
    assert by_route(results, "public.telegram_channel").reason == "missing_public_source_url"


def test_public_website_title_falls_back_when_raw_title_is_full_text() -> None:
    event = make_event(severity="A", relevance_score=90)
    event.title = None
    event.raw_item.title = " ".join(["long-source-post"] * 80)

    results = route_results(event, RoutePolicyRuntime(), make_settings(ENABLE_PUBLIC_WEBSITE_ROUTE=True))
    public_website = by_route(results, "public.website")

    assert public_website.queued is True
    assert public_website.public_outbox is not None
    assert public_website.public_outbox.public_title_zh == "IRAN_NUCLEAR"
    assert public_website.public_outbox.public_title_en is None


def test_public_outbox_preserves_english_public_content() -> None:
    event = make_event(
        severity="A",
        relevance_score=90,
        title="Fed rhetoric turns more hawkish",
        summary_en="Fed-linked remarks emphasized persistent inflation and policy restraint.",
    )

    results = route_results(event, RoutePolicyRuntime(), make_settings(ENABLE_PUBLIC_WEBSITE_ROUTE=True))
    public_website = by_route(results, "public.website")

    assert public_website.queued is True
    assert public_website.public_outbox is not None
    assert public_website.public_outbox.public_title_en == "Fed rhetoric turns more hawkish"
    assert public_website.public_outbox.public_summary_en == (
        "Fed-linked remarks emphasized persistent inflation and policy restraint."
    )


def test_public_outbox_summary_falls_back_to_raw_item_translation_summary() -> None:
    event = make_event(severity="A", relevance_score=90)
    event.summary_zh = ""
    event.summary_en = None
    event.raw_item.summary_zh = "Raw item translation summary."

    results = route_results(event, RoutePolicyRuntime(), make_settings(ENABLE_PUBLIC_WEBSITE_ROUTE=True))
    public_website = by_route(results, "public.website")

    assert public_website.queued is True
    assert public_website.public_outbox is not None
    assert public_website.public_outbox.public_summary_zh == "Raw item translation summary."


def test_public_outbox_does_not_copy_chinese_title_into_english_field() -> None:
    event = make_event(severity="A", relevance_score=90, title="伊朗談判出現新進展")
    event.raw_item.title = "伊朗官方媒體提及談判進展"

    results = route_results(event, RoutePolicyRuntime(), make_settings(ENABLE_PUBLIC_WEBSITE_ROUTE=True))
    public_website = by_route(results, "public.website")

    assert public_website.queued is True
    assert public_website.public_outbox is not None
    assert public_website.public_outbox.public_title_zh == "伊朗談判出現新進展"
    assert public_website.public_outbox.public_title_en is None


def test_public_x_uses_configured_a_relevance_threshold() -> None:
    event = make_event(severity="A", relevance_score=85)

    default_results = route_results(event, RoutePolicyRuntime(), make_settings(ENABLE_PUBLIC_X_ROUTE=True))
    relaxed_results = route_results(
        event,
        RoutePolicyRuntime(),
        make_settings(ENABLE_PUBLIC_X_ROUTE=True, PUBLIC_X_A_RELEVANCE_THRESHOLD=85),
    )

    assert by_route(default_results, "public.x").queued is False
    assert by_route(default_results, "public.x").reason == "below_public_severity_policy"
    assert by_route(relaxed_results, "public.x").queued is True
