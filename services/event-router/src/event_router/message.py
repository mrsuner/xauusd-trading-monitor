from __future__ import annotations

from .models import EventContext


def compact_text(value: str | None, *, limit: int, preserve_lines: bool = False) -> str:
    if not value:
        return ""
    if preserve_lines:
        lines = [" ".join(line.split()) for line in value.splitlines()]
        text = "\n".join(lines).strip()
    else:
        text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def source_label(event: EventContext) -> str:
    source = event.source
    if source.name and source.handle_or_url:
        return f"{source.name} ({source.handle_or_url})"
    if source.name:
        return source.name
    if source.handle_or_url:
        return source.handle_or_url
    return "unknown"


def event_summary(event: EventContext) -> str:
    return (
        event.summary_zh
        or event.summary_en
        or event.raw_item.summary_zh
        or event.raw_item.summary_en
        or event.raw_item.text_clean
        or event.raw_item.text_raw
        or "No summary available."
    )


def event_title(event: EventContext) -> str:
    return event.title or event.raw_item.title or event.event_type


def build_telegram_message(event: EventContext) -> str:
    confidence = "-" if event.confidence is None else str(event.confidence)
    impact = ", ".join(event.xauusd_impact_channel) if event.xauusd_impact_channel else "-"
    confirmation = event.confirmation_state
    if event.requires_confirmation:
        confirmation = f"{confirmation}; requires confirmation"

    lines = [
        f"[{event.severity}] {event.event_type} | relevance {event.relevance_score} | confidence {confidence}",
        "",
        compact_text(event_summary(event), limit=1200),
        "",
        f"Source: {source_label(event)}",
        f"Group: {event.source.source_group or event.source_group or '-'}",
        f"Official: {event.source.official_level or '-'}",
        f"Confirmation: {confirmation}",
        f"Impact: {impact}",
    ]
    if event.raw_item.url:
        lines.extend(["", f"URL: {event.raw_item.url}"])
    return compact_text("\n".join(lines), limit=3900, preserve_lines=True)


def build_pushover_title(event: EventContext) -> str:
    return compact_text(f"[{event.severity}] {event.event_type} relevance {event.relevance_score}", limit=250)


def build_pushover_message(event: EventContext) -> str:
    confirmation = "Requires confirmation." if event.requires_confirmation else event.confirmation_state
    lines = [
        compact_text(event_summary(event), limit=720),
        f"Source: {event.source.name or 'unknown'}",
        confirmation,
    ]
    if event.raw_item.url:
        lines.append(event.raw_item.url)
    return compact_text("\n".join(lines), limit=950, preserve_lines=True)


def build_public_outbox_summary(event: EventContext) -> str | None:
    return event.summary_zh or event.raw_item.summary_zh or event.summary_en or event.raw_item.summary_en
