from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from event_router.message import build_telegram_message
from event_router.models import EventContext, RawItemContext, SourceContext


def test_telegram_message_preserves_readable_lines() -> None:
    event = EventContext(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        event_type="TRUMP_TRUTH",
        severity="A",
        relevance_score=90,
        confidence=75,
        confirmation_state="unconfirmed",
        summary_zh="Trump 發布與伊朗談判相關消息。",
        xauusd_impact_channel=["safe_haven"],
        requires_confirmation=True,
        source=SourceContext(
            id=uuid4(),
            name="Trump Truth tracker",
            handle_or_url="@TrumpTruthSocial_Alert",
            source_group="us_trump",
            official_level="unofficial_mirror",
            priority="P0",
        ),
        raw_item=RawItemContext(url="https://example.com/truth"),
    )

    message = build_telegram_message(event)

    assert "[A] TRUMP_TRUTH" in message
    assert "\n\nTrump 發布" in message
    assert "\nSource: Trump Truth tracker" in message
    assert "https://example.com/truth" in message


def test_telegram_message_falls_back_to_raw_item_translation_summary() -> None:
    event = EventContext(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        event_type="TRUMP_TRUTH",
        severity="A",
        relevance_score=90,
        confidence=75,
        confirmation_state="unconfirmed",
        summary_zh="",
        summary_en=None,
        xauusd_impact_channel=["safe_haven"],
        requires_confirmation=True,
        source=SourceContext(
            id=uuid4(),
            name="Trump Truth tracker",
            handle_or_url="@TrumpTruthSocial_Alert",
            source_group="us_trump",
            official_level="unofficial_mirror",
            priority="P0",
        ),
        raw_item=RawItemContext(summary_zh="Raw item translation summary.", url="https://example.com/truth"),
    )

    message = build_telegram_message(event)

    assert "Raw item translation summary." in message
