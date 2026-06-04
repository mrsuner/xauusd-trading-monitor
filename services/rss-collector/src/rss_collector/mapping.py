from __future__ import annotations

import hashlib
import re
from datetime import UTC
from datetime import datetime
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any
from urllib.parse import urljoin

import feedparser
from selectolax.parser import HTMLParser

from .models import PollingSource


WHITESPACE_RE = re.compile(r"\s+")
HTML_TAG_RE = re.compile(r"<[a-zA-Z/!][^>]*>")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    if not HTML_TAG_RE.search(value):
        return normalize_text(value)
    text = HTMLParser(value).text(separator=" ")
    text = re.sub(r"@\s+", "@", text)
    return normalize_text(text)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def short_hash(value: str) -> str:
    return sha256_text(value)[:24]


def content_hash(title: str | None, text: str | None, url: str | None) -> str:
    return sha256_text("\n".join(part for part in (title, text, url) if part))


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        return datetime(*value[:6], tzinfo=UTC)
    if isinstance(value, str):
        normalized = normalize_text(value)
        try:
            parsed = parsedate_to_datetime(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError, IndexError):
            try:
                parsed_iso = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
                return parsed_iso if parsed_iso.tzinfo else parsed_iso.replace(tzinfo=UTC)
            except ValueError:
                pass
        for date_format in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(normalized, date_format).replace(tzinfo=UTC)
            except ValueError:
                continue
        return None
    return None


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, struct_time):
        return datetime(*value[:6], tzinfo=UTC).isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def external_id_for_entry(entry: dict[str, Any]) -> str:
    for key in ("id", "guid", "link"):
        value = entry.get(key)
        if value:
            return str(value)
    title = str(entry.get("title") or "")
    published = str(entry.get("published") or entry.get("updated") or "")
    return short_hash(f"{title}:{published}")


def feed_dedupe_key(source: PollingSource, external_id: str) -> str:
    feed_hash = short_hash(source.handle_or_url.lower())
    item_hash = short_hash(external_id)
    prefix = "atom" if source.source_type == "atom" else "rss"
    return f"{prefix}:{feed_hash}:{item_hash}"


def entry_text(entry: dict[str, Any]) -> str:
    if entry.get("summary"):
        return html_to_text(str(entry["summary"]))
    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value") if isinstance(content[0], dict) else str(content[0])
        return html_to_text(str(value))
    if entry.get("description"):
        return html_to_text(str(entry["description"]))
    return ""


def feed_entry_to_raw_item(source: PollingSource, entry: dict[str, Any], feed_metadata: dict[str, Any]) -> dict[str, Any]:
    external_id = external_id_for_entry(entry)
    title = normalize_text(str(entry.get("title") or ""))
    text = entry_text(entry)
    url = str(entry.get("link") or "") or None
    published_at = parse_datetime(entry.get("published_parsed") or entry.get("published"))
    edited_at = parse_datetime(entry.get("updated_parsed") or entry.get("updated"))

    return {
        "source_id": source.id,
        "external_id": external_id,
        "published_at": published_at or edited_at,
        "edited_at": edited_at,
        "title": title or None,
        "text_raw": text,
        "text_clean": text,
        "language": source.language or feed_metadata.get("language"),
        "url": url,
        "media_type": "webpage" if url else "none",
        "raw_json": json_safe({"entry": dict(entry), "feed": feed_metadata}),
        "content_hash": content_hash(title, text, url),
        "dedupe_key": feed_dedupe_key(source, external_id),
    }


def parse_feed_items(source: PollingSource, body: bytes) -> list[dict[str, Any]]:
    parsed = feedparser.parse(body)
    feed_metadata = dict(parsed.get("feed", {}))
    return [feed_entry_to_raw_item(source, dict(entry), feed_metadata) for entry in parsed.entries]


def html_dedupe_key(source: PollingSource, external_id: str) -> str:
    source_hash = short_hash(str(source.id))
    item_hash = short_hash(external_id)
    return f"html:{source_hash}:{item_hash}"


def first_text(node: Any, selector: str | None) -> str:
    if selector:
        selected = node.css_first(selector)
        if not selected:
            return ""
        return normalize_text(selected.text())
    return normalize_text(node.text())


def first_attr(node: Any, selector: str | None, attr: str) -> str | None:
    selected = node.css_first(selector) if selector else node
    if not selected:
        return None
    value = selected.attributes.get(attr)
    return str(value) if value else None


def configured_text(node: Any, *, selector: str | None, attr: str | None = None, pattern: str | None = None) -> str:
    if attr:
        value = first_attr(node, selector, attr) or ""
    else:
        value = first_text(node, selector)
    if pattern:
        match = re.search(pattern, value)
        if match:
            return normalize_text(match.group(1) if match.groups() else match.group(0))
    return normalize_text(value)


def parse_html_items(source: PollingSource, body: bytes) -> list[dict[str, Any]]:
    config = source.source_config
    list_selector = config.get("list_selector")
    if not list_selector:
        raise ValueError("html_polling source requires source_config.list_selector")

    parser = HTMLParser(body)
    items: list[dict[str, Any]] = []
    for node in parser.css(str(list_selector)):
        title = first_text(node, config.get("title_selector"))
        href = first_attr(node, config.get("url_selector") or config.get("title_selector"), "href")
        url = urljoin(source.handle_or_url, href) if href else None
        published_text = configured_text(
            node,
            selector=config.get("published_selector"),
            attr=config.get("published_attr"),
            pattern=config.get("published_regex"),
        )
        published_at = parse_datetime(published_text)
        external_id = url or f"{title}:{published_text}"

        if not title and not url:
            continue

        items.append(
            {
                "source_id": source.id,
                "external_id": external_id,
                "published_at": published_at,
                "edited_at": None,
                "title": title or None,
                "text_raw": title,
                "text_clean": title,
                "language": source.language,
                "url": url,
                "media_type": "webpage" if url else "none",
                "raw_json": {
                    "html_item": {
                        "title": title,
                        "url": url,
                        "published_text": published_text,
                    }
                },
                "content_hash": content_hash(title, title, url),
                "dedupe_key": html_dedupe_key(source, external_id),
            }
        )
    return items
