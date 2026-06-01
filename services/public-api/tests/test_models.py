from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from public_api.models import PublicEventIngestRequest


def test_public_event_ingest_request_normalizes_taxonomy() -> None:
    payload = PublicEventIngestRequest.model_validate(
        {
            "schema_version": "public_event.v1",
            "idempotency_key": "event:1:v1",
            "upstream_event_id": str(uuid4()),
            "severity": "A",
            "topic_tags": [" Iran ", "iran", "", "Gold"],
            "mentioned_actors": ["Trump", " trump "],
            "public_source_links": [{"url": "https://example.com/news", "source_name": "Example"}],
        }
    )

    assert payload.topic_tags == ["Iran", "Gold"]
    assert payload.mentioned_actors == ["Trump"]


def test_public_event_ingest_request_rejects_unsupported_schema() -> None:
    with pytest.raises(ValidationError):
        PublicEventIngestRequest.model_validate(
            {
                "schema_version": "public_event.v2",
                "idempotency_key": "event:1:v2",
                "upstream_event_id": str(uuid4()),
                "severity": "A",
            }
        )
