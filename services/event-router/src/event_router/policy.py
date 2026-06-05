from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from .message import (
    build_public_outbox_summary,
    build_pushover_message,
    build_pushover_title,
    build_telegram_message,
    compact_text,
)
from .models import AlertChannelStats, AlertDecision, EventContext, PublicOutboxDraft, RoutePolicyRuntime, RouteResult


class Thresholds(Protocol):
    enable_private_telegram_route: bool
    enable_private_pushover_route: bool
    enable_public_telegram_channel_route: bool
    enable_public_website_route: bool
    enable_public_x_route: bool
    private_telegram_threshold: int
    private_telegram_s_threshold: int
    private_pushover_threshold: int
    public_telegram_threshold: int
    public_website_threshold: int
    public_x_threshold: int
    public_x_a_relevance_threshold: int


AGGREGATOR_GROUPS = {"osint_aggregator", "market_squawk"}
MAX_PUBLIC_TITLE_CHARS = 180
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


def route_score(event: EventContext) -> int:
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
    return max(0, min(score, 150))


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


def private_telegram_route(event: EventContext, runtime: RoutePolicyRuntime, settings: Thresholds, score: int) -> RouteResult:
    route_key = "private.telegram"
    if not settings.enable_private_telegram_route:
        return skipped(event, route_key, score, "route_disabled")
    if runtime.is_backfill and runtime.backfill_mode == "skip":
        return skipped(event, route_key, score, "backfill_skipped")
    if not event.source.telegram_alert_enabled:
        return skipped(event, route_key, score, "source_telegram_disabled")
    if not severity_at_least(event.severity, event.source.telegram_min_severity):
        return skipped(event, route_key, score, "below_source_min_severity")
    if rate_limited(event, runtime.telegram_stats):
        return skipped(event, route_key, score, "source_rate_limited")

    threshold = settings.private_telegram_s_threshold if event.severity == "S" else settings.private_telegram_threshold
    if score < threshold:
        return skipped(event, route_key, score, "below_route_score_threshold")

    return RouteResult(
        route_key=route_key,
        event_id=event.id,
        queued=True,
        route_score=score,
        reason="queued",
        alert=AlertDecision(
            event_id=event.id,
            channel="telegram",
            priority="high" if event.severity == "S" else "normal",
            message=build_telegram_message(event),
            dedupe_key=f"alert:{event.id}:telegram",
            alert_score=score,
        ),
    )


def private_pushover_route(event: EventContext, runtime: RoutePolicyRuntime, settings: Thresholds, score: int) -> RouteResult:
    route_key = "private.pushover"
    if not settings.enable_private_pushover_route:
        return skipped(event, route_key, score, "route_disabled")
    if runtime.is_backfill and runtime.backfill_mode in {"skip", "telegram_only"}:
        return skipped(event, route_key, score, "backfill_skipped")
    if not event.source.pushover_alert_enabled:
        return skipped(event, route_key, score, "source_pushover_disabled")
    if not severity_at_least(event.severity, event.source.pushover_min_severity):
        return skipped(event, route_key, score, "below_source_min_severity")

    source_group = event.source.source_group or event.source_group
    if source_group in AGGREGATOR_GROUPS:
        return skipped(event, route_key, score, "aggregator_source")
    if event.source.official_level == "aggregator":
        return skipped(event, route_key, score, "aggregator_official_level")
    if rate_limited(event, runtime.pushover_stats):
        return skipped(event, route_key, score, "source_rate_limited")
    if score < settings.private_pushover_threshold:
        return skipped(event, route_key, score, "below_route_score_threshold")

    return RouteResult(
        route_key=route_key,
        event_id=event.id,
        queued=True,
        route_score=score,
        reason="queued",
        alert=AlertDecision(
            event_id=event.id,
            channel="pushover",
            priority=pushover_priority(event, score),
            message=f"{build_pushover_title(event)}\n\n{build_pushover_message(event)}",
            dedupe_key=f"alert:{event.id}:pushover",
            alert_score=score,
        ),
    )


def public_telegram_channel_route(event: EventContext, settings: Thresholds, score: int) -> RouteResult:
    route_key = "public.telegram_channel"
    if not settings.enable_public_telegram_channel_route:
        return skipped(event, route_key, score, "route_disabled")
    if not has_public_source_url(event):
        return skipped(event, route_key, score, "missing_public_source_url")
    if event.severity not in {"S", "A"} and not (event.severity == "B" and event.relevance_score >= 80):
        return skipped(event, route_key, score, "below_public_severity_policy")
    if public_confirmation_blocked(event):
        return skipped(event, route_key, score, "aggregator_requires_confirmation")
    if score < settings.public_telegram_threshold:
        return skipped(event, route_key, score, "below_route_score_threshold")

    return RouteResult(
        route_key=route_key,
        event_id=event.id,
        queued=True,
        route_score=score,
        reason="queued",
        public_outbox=build_public_outbox_draft(
            event,
            approved_for_public=True,
            publish_status_telegram="pending",
            publish_status_web="skipped",
            publish_status_x="skipped",
        ),
    )


def public_website_route(event: EventContext, settings: Thresholds, score: int) -> RouteResult:
    route_key = "public.website"
    if not settings.enable_public_website_route:
        return skipped(event, route_key, score, "route_disabled")
    if event.severity not in {"S", "A", "B"}:
        return skipped(event, route_key, score, "below_public_severity_policy")
    if not build_public_outbox_summary(event):
        return skipped(event, route_key, score, "missing_public_summary")
    if score < settings.public_website_threshold:
        return skipped(event, route_key, score, "below_route_score_threshold")

    return RouteResult(
        route_key=route_key,
        event_id=event.id,
        queued=True,
        route_score=score,
        reason="queued",
        public_outbox=build_public_outbox_draft(
            event,
            approved_for_public=has_public_source_url(event),
            publish_status_telegram="skipped",
            publish_status_web="pending",
            publish_status_x="skipped",
        ),
    )


def public_x_route(event: EventContext, settings: Thresholds, score: int) -> RouteResult:
    route_key = "public.x"
    if not settings.enable_public_x_route:
        return skipped(event, route_key, score, "route_disabled")
    if not has_public_source_url(event):
        return skipped(event, route_key, score, "missing_public_source_url")
    if not (
        event.severity == "S"
        or (event.severity == "A" and event.relevance_score >= settings.public_x_a_relevance_threshold)
    ):
        return skipped(event, route_key, score, "below_public_severity_policy")
    if score < settings.public_x_threshold:
        return skipped(event, route_key, score, "below_route_score_threshold")

    return RouteResult(
        route_key=route_key,
        event_id=event.id,
        queued=True,
        route_score=score,
        reason="queued",
        public_outbox=build_public_outbox_draft(
            event,
            approved_for_public=True,
            publish_status_telegram="skipped",
            publish_status_web="skipped",
            publish_status_x="pending",
        ),
    )


def route_results(event: EventContext, runtime: RoutePolicyRuntime, settings: Thresholds) -> list[RouteResult]:
    score = route_score(event)
    return [
        private_telegram_route(event, runtime, settings, score),
        private_pushover_route(event, runtime, settings, score),
        public_telegram_channel_route(event, settings, score),
        public_website_route(event, settings, score),
        public_x_route(event, settings, score),
    ]


def pushover_priority(event: EventContext, score: int) -> str:
    if is_emergency_candidate(event, score):
        return "emergency"
    if event.severity == "S" or score >= 95:
        return "high"
    return "normal"


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


def public_confirmation_blocked(event: EventContext) -> bool:
    source_group = event.source.source_group or event.source_group
    if source_group not in AGGREGATOR_GROUPS:
        return False
    if event.confirmation_state in {"confirmed", "partially_confirmed"}:
        return False
    independent_claims = {claim.stance or claim.claim_direction for claim in event.claims}
    return len(independent_claims) < 2


def has_public_source_url(event: EventContext) -> bool:
    return bool(event.raw_item.url and event.raw_item.url.startswith(("http://", "https://")))


def build_public_outbox_draft(
    event: EventContext,
    *,
    approved_for_public: bool,
    publish_status_web: str,
    publish_status_telegram: str,
    publish_status_x: str,
) -> PublicOutboxDraft:
    links: list[dict[str, str | None]] = []
    if event.raw_item.url:
        links.append({"source_name": event.source.name, "url": event.raw_item.url})
    public_title_zh = public_outbox_title(event)
    public_title_en = public_outbox_title_en(event)
    return PublicOutboxDraft(
        event_id=event.id,
        public_title_zh=public_title_zh,
        public_summary_zh=build_public_outbox_summary(event),
        public_title_en=public_title_en,
        public_summary_en=event.summary_en or event.raw_item.summary_en,
        public_source_links=links,
        severity=event.severity,
        relevance_score=event.relevance_score,
        confirmation_state=event.confirmation_state,
        topic_tags=event.topic_tags,
        approved_for_public=approved_for_public,
        publish_status_web=publish_status_web,
        publish_status_telegram=publish_status_telegram,
        publish_status_x=publish_status_x,
    )


def public_outbox_title(event: EventContext) -> str:
    for candidate in (event.title, event.raw_item.title):
        title = public_outbox_raw_title_from_value(candidate)
        if title:
            return title
    return compact_text(event.event_type, limit=MAX_PUBLIC_TITLE_CHARS)


def public_outbox_raw_title(event: EventContext) -> str | None:
    return public_outbox_raw_title_from_value(event.raw_item.title)


def public_outbox_title_en(event: EventContext) -> str | None:
    for candidate in (event.title, event.raw_item.title):
        title = public_outbox_raw_title_from_value(candidate)
        if title and is_likely_english_public_title(title):
            return title
    return None


def public_outbox_raw_title_from_value(value: str | None) -> str | None:
    if not value:
        return None
    title = " ".join(value.split())
    if not title or len(title) > MAX_PUBLIC_TITLE_CHARS:
        return None
    return compact_text(title, limit=MAX_PUBLIC_TITLE_CHARS)


def is_likely_english_public_title(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return False
    ascii_letters = [char for char in letters if char.isascii()]
    return len(ascii_letters) / len(letters) >= 0.8


def skipped(event: EventContext, route_key: str, score: int, reason: str) -> RouteResult:
    return RouteResult(event_id=event.id, route_key=route_key, queued=False, route_score=score, reason=reason)
