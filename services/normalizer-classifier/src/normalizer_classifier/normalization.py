from __future__ import annotations

import re

from .models import NormalizedItem, RawItem, SourceMetadata
from .routing import RoutingContext

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")

def clean_text(title: str | None, text: str | None) -> str:
    parts = [part for part in (title, text) if part]
    combined = "\n".join(parts)
    combined = URL_RE.sub(" ", combined)
    return SPACE_RE.sub(" ", combined).strip()


def detect_language(raw_item: RawItem, source: SourceMetadata, text_clean: str) -> str:
    if raw_item.language:
        return raw_item.language
    if source.language:
        return source.language
    if re.search(r"[\u0600-\u06ff]", text_clean):
        return "fa"
    if re.search(r"[\u0590-\u05ff]", text_clean):
        return "he"
    return "en" if text_clean else "unknown"


def normalize_item(
    raw_item: RawItem,
    source: SourceMetadata,
    routing_context: RoutingContext,
) -> NormalizedItem:
    text_clean = clean_text(raw_item.title, raw_item.text_clean or raw_item.text_raw)
    language = detect_language(raw_item, source, text_clean)

    if not text_clean:
        return NormalizedItem(
            text_clean="",
            language=language,
            keyword_score=0,
            prefilter_passed=False,
            filter_reason="empty_text",
            routing_config_version=routing_context.config_version,
        )

    decision = routing_context.route(text_clean)
    return NormalizedItem(
        text_clean=text_clean,
        language=language,
        keyword_score=max(decision.scores.values(), default=0),
        matched_keywords=[
            f"{domain}:{group}"
            for domain, groups in decision.matched_groups.items()
            for group in groups
        ],
        prefilter_passed=decision.passed,
        filter_reason=None if decision.passed else "no_domain_match",
        matched_domains=list(decision.matched_domains),
        selected_domains=list(decision.selected_domains),
        routing_config_version=decision.config_version,
    )


def severity_for(score: int, source: SourceMetadata) -> str:
    if score >= 90 and source.priority in {"P0", "P1"} and source.official_level != "aggregator":
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    return "C"
