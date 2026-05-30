from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from normalizer_classifier.models import RawItem, SourceMetadata
from normalizer_classifier.normalization import clean_text, normalize_item, severity_for


def source(priority: str = "P0", official_level: str = "official") -> SourceMetadata:
    return SourceMetadata(
        id=uuid4(),
        name="Tasnim",
        handle_or_url="@Tasnimnews",
        source_type="telegram",
        source_group="iran_irgc_adjacent",
        official_level=official_level,
        priority=priority,
        reliability_score=75,
        latency_score=85,
        requires_confirmation=True,
    )


def raw_item(title: str | None, text: str | None) -> RawItem:
    return RawItem(
        id=uuid4(),
        source_id=uuid4(),
        published_at=None,
        ingested_at=datetime.now(timezone.utc),
        title=title,
        text_raw=text,
        media_type="none",
        raw_json={},
        dedupe_key="telegram:1:1",
    )


def test_clean_text_removes_urls_and_collapses_space() -> None:
    assert clean_text("A  title", "Body https://example.com/a\n\nnext") == "A title Body next"


def test_normalize_item_prefilter_passes_high_value_keywords() -> None:
    normalized = normalize_item(raw_item("Iran nuclear deal", "IRGC warns about sanctions"), source())

    assert normalized.prefilter_passed is True
    assert "iran" in normalized.matched_keywords
    assert "irgc" in normalized.matched_keywords
    assert normalized.keyword_score >= 60


def test_normalize_item_skips_empty_text() -> None:
    normalized = normalize_item(raw_item(None, None), source())

    assert normalized.prefilter_passed is False
    assert normalized.filter_reason == "empty_text"


def test_severity_uses_score_and_source_level() -> None:
    assert severity_for(92, source("P0", "official")) == "S"
    assert severity_for(92, source("P2", "aggregator")) == "A"
    assert severity_for(72, source("P0", "official")) == "B"
