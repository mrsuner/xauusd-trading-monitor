from __future__ import annotations

from public_syncer.catalog import build_catalog_payload, catalog_revision_for


def catalog_rows() -> tuple[list[dict], list[dict]]:
    return (
        [
            {
                "key": "fed",
                "label_en": "Federal Reserve",
                "label_zh": "聯準會",
                "description": "Federal Reserve policy.",
                "sort_order": 10,
            }
        ],
        [
            {
                "key": "inflation",
                "label_en": "Inflation",
                "label_zh": "通膨",
                "tag_type": "topic",
                "aliases": [],
            }
        ],
    )


def test_catalog_revision_is_deterministic_and_payload_is_versioned() -> None:
    categories, tags = catalog_rows()
    revision = catalog_revision_for(categories=categories, tags=tags)
    payload = build_catalog_payload(categories=list(reversed(categories)), tags=list(reversed(tags)))

    assert len(revision) == 64
    assert payload["revision"] == revision
    assert payload["idempotency_key"] == f"subscription_catalog:{revision}"
    assert payload["schema_version"] == "subscription_catalog.v1"


def test_catalog_revision_changes_when_visible_label_changes() -> None:
    categories, tags = catalog_rows()
    base = catalog_revision_for(categories=categories, tags=tags)
    tags[0]["label_en"] = "Consumer inflation"

    assert catalog_revision_for(categories=categories, tags=tags) != base
