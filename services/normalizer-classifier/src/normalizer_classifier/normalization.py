from __future__ import annotations

import re

from .models import NormalizedItem, RawItem, SourceMetadata

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")

KEYWORD_GROUPS: dict[str, list[str]] = {
    "trump": ["trump", "truth social", "deal", "no deal", "taco"],
    "iran": ["iran", "iranian", "tehran", "nuclear", "enrichment", "uranium", "sanction"],
    "irgc": ["irgc", "revolutionary guard", "sepah", "سپاه", "موشک", "تنگه هرمز"],
    "israel": ["israel", "idf", "strike", "missile", "drone", "air defense"],
    "us_military": ["centcom", "vessel", "red sea", "strait of hormuz", "hormuz"],
    "fed": ["fed", "fomc", "powell", "rate cut", "inflation", "restrictive", "higher for longer"],
    "market": ["gold", "xauusd", "oil", "brent", "wti", "dxy", "treasury", "yield", "vix"],
}

PRIORITY_BONUS = {
    "P0": 30,
    "P1": 20,
    "P2": 10,
    "P3": 0,
}


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


def keyword_matches(text_clean: str) -> list[str]:
    lowered = text_clean.lower()
    matches: list[str] = []
    for group, keywords in KEYWORD_GROUPS.items():
        if any(keyword in lowered for keyword in keywords):
            matches.append(group)
    return matches


def normalize_item(raw_item: RawItem, source: SourceMetadata) -> NormalizedItem:
    text_clean = clean_text(raw_item.title, raw_item.text_clean or raw_item.text_raw)
    language = detect_language(raw_item, source, text_clean)

    if not text_clean:
        return NormalizedItem(
            text_clean="",
            language=language,
            keyword_score=0,
            prefilter_passed=False,
            filter_reason="empty_text",
        )

    matches = keyword_matches(text_clean)
    keyword_score = min(70, len(matches) * 18) + PRIORITY_BONUS.get(source.priority, 0)
    prefilter_passed = keyword_score >= 25 or (source.priority in {"P0", "P1"} and bool(matches))
    filter_reason = None if prefilter_passed else "low_keyword_relevance"

    return NormalizedItem(
        text_clean=text_clean,
        language=language,
        keyword_score=min(keyword_score, 100),
        matched_keywords=matches,
        prefilter_passed=prefilter_passed,
        filter_reason=filter_reason,
    )


def severity_for(score: int, source: SourceMetadata) -> str:
    if score >= 90 and source.priority in {"P0", "P1"} and source.official_level != "aggregator":
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    return "C"
