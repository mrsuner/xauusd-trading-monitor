from __future__ import annotations

import re

from .models import PublicOutboxItem, SourceLink

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

SEVERITY_LABELS = {
    "S": "[S]",
    "A": "[A]",
    "B": "[Watch]",
    "C": "[Info]",
}

TOPIC_HASHTAGS = {
    "xauusd": "#XAUUSD",
    "gold": "#Gold",
    "fed": "#Fed",
    "iran": "#Iran",
    "trump": "#Trump",
    "geopolitics": "#Geopolitics",
    "oil": "#Oil",
    "israel": "#Israel",
}

CONFIRMATION_LABELS = {
    "unconfirmed": "未確認",
    "partially_confirmed": "部分確認",
    "contradicted": "相互矛盾",
}

TRADE_ADVICE_PATTERNS = (
    "做多",
    "做空",
    "買入",
    "卖出",
    "賣出",
    "入場",
    "long ",
    "short ",
    "buy ",
    "sell ",
)


def compact_text(value: str | None, *, limit: int) -> str:
    if not value:
        return ""
    text = " ".join(URL_RE.sub("", value).strip().split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def title_for(item: PublicOutboxItem) -> str:
    return (
        item.public_title_zh
        or first_sentence(item.public_summary_zh)
        or "公開事件更新"
    )


def summary_for(item: PublicOutboxItem) -> str:
    return item.public_summary_zh or ""


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


def contains_url(value: str) -> bool:
    return URL_RE.search(value) is not None


def canonical_source_link(item: PublicOutboxItem) -> SourceLink | None:
    for link in item.public_source_links:
        if valid_public_url(link.url):
            return link
    return None


def render_hashtags(tags: list[str], *, limit: int = 2) -> str:
    rendered: list[str] = []
    for raw in tags:
        key = raw.strip().lower().replace("-", "_")
        tag = TOPIC_HASHTAGS.get(key)
        if not tag:
            clean = re.sub(r"[^A-Za-z0-9_]", "", raw.strip().replace("-", "_"))
            if not clean:
                continue
            tag = f"#{clean[:30]}"
        if tag not in rendered:
            rendered.append(tag)
        if len(rendered) >= limit:
            break
    if "#XAUUSD" not in rendered:
        rendered.insert(0, "#XAUUSD")
    return " ".join(rendered[:limit])


def contains_trade_advice(text: str) -> bool:
    lowered = f" {text.lower()} "
    return any(pattern in lowered for pattern in TRADE_ADVICE_PATTERNS)


def build_post(item: PublicOutboxItem, *, limit: int) -> str:
    severity = SEVERITY_LABELS.get(item.severity, f"[{item.severity}]")
    title = compact_text(title_for(item), limit=96)
    summary = compact_text(summary_for(item), limit=120)
    confirmation = item.confirmation_state or "unconfirmed"
    source_link = canonical_source_link(item)
    source_name = compact_text(source_link.label, limit=32) if source_link else None
    hashtags = render_hashtags(item.topic_tags)

    lines = [f"{severity} {title}"]
    if summary and summary != title:
        lines.extend(["", summary])
    if confirmation in CONFIRMATION_LABELS:
        lines.extend(["", f"狀態：{CONFIRMATION_LABELS[confirmation]}"])
    if source_name:
        lines.extend(["", f"來源：{source_name}"])
    if hashtags:
        lines.extend(["", hashtags])

    post = "\n".join(lines)
    if len(post) <= limit:
        return post

    compact_summary = compact_text(summary, limit=72)
    lines = [f"{severity} {compact_text(title, limit=82)}"]
    if compact_summary and compact_summary != title:
        lines.extend(["", compact_summary])
    if source_name:
        lines.extend(["", f"來源：{source_name}"])
    post = "\n".join(lines)
    if len(post) <= limit:
        return post

    fixed_lines = []
    if source_name:
        fixed_lines.append(f"來源：{source_name}")
    fixed_tail = "\n\n".join(fixed_lines)
    reserved = len(fixed_tail) + (2 if fixed_tail else 0)
    header = f"{severity} {compact_text(title, limit=max(20, limit - reserved))}"
    if fixed_tail:
        return compact_text(f"{header}\n\n{fixed_tail}", limit=limit)
    return compact_text(header, limit=limit)
