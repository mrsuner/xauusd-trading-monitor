from __future__ import annotations

from html import escape

from .models import PublicOutboxItem, SourceLink

SEVERITY_LABELS = {
    "S": "[S]",
    "A": "[A]",
    "B": "[Watch]",
    "C": "[Info]",
}


def compact_text(value: str | None, *, limit: int) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def title_for(item: PublicOutboxItem) -> str:
    return (
        item.title
        or first_sentence(item.summary)
        or "Public event update"
    )


def summary_for(item: PublicOutboxItem) -> str:
    return item.summary or "No public summary available."


def first_sentence(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(value.split())
    if not text:
        return None
    for separator in ("。", ".", "！", "?", "？"):
        if separator in text:
            return text.split(separator, 1)[0].strip() + separator
    return compact_text(text, limit=90)


def valid_public_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("https://") or value.startswith("http://")


def render_source_line(link: SourceLink, index: int, *, html: bool) -> str | None:
    if not valid_public_url(link.url):
        return None
    label = compact_text(link.label, limit=80)
    if html:
        return f'{index}. <a href="{escape(link.url or "", quote=True)}">{escape(label)}</a>'
    return f"{index}. {label} {link.url}"


def render_tags(tags: list[str]) -> str:
    normalized = []
    for tag in tags[:5]:
        clean = "".join(ch for ch in tag.strip().replace("-", "_") if ch.isalnum() or ch == "_")
        if clean:
            normalized.append(f"#{clean}")
    return " ".join(normalized)


def build_message(item: PublicOutboxItem, *, parse_mode: str, limit: int) -> str:
    html = parse_mode == "HTML"
    title = compact_text(title_for(item), limit=180)
    summary = compact_text(summary_for(item), limit=1600)
    severity = SEVERITY_LABELS.get(item.severity, f"[{item.severity}]")
    confirmation = item.confirmation_state or "unconfirmed"
    relevance = "-" if item.relevance_score is None else str(item.relevance_score)

    if html:
        header = f"<b>{escape(severity)} {escape(title)}</b>"
        body = escape(summary)
        meta = f"Status: {escape(confirmation)} | Relevance: {escape(relevance)}"
    else:
        header = f"{severity} {title}"
        body = summary
        meta = f"Status: {confirmation} | Relevance: {relevance}"

    lines = [header, "", body, "", meta]

    source_lines = [
        rendered
        for index, link in enumerate(item.public_source_links[:5], start=1)
        if (rendered := render_source_line(link, index, html=html))
    ]
    if source_lines:
        lines.extend(["", "Sources:" if not html else "<b>Sources:</b>", *source_lines])

    tags = render_tags(item.topic_tags)
    if tags:
        lines.extend(["", tags])

    return compact_text("\n".join(lines), limit=limit)
