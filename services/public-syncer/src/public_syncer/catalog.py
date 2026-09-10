from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def catalog_revision_for(*, categories: list[dict[str, Any]], tags: list[dict[str, Any]]) -> str:
    payload = {
        "categories": sorted(categories, key=lambda item: item["key"]),
        "tags": sorted(tags, key=lambda item: item["key"]),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_catalog_payload(*, categories: list[dict[str, Any]], tags: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_categories = sorted(categories, key=lambda item: item["key"])
    ordered_tags = sorted(tags, key=lambda item: item["key"])
    revision = catalog_revision_for(categories=ordered_categories, tags=ordered_tags)
    return {
        "schema_version": "subscription_catalog.v1",
        "idempotency_key": f"subscription_catalog:{revision}",
        "revision": revision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": ordered_categories,
        "tags": ordered_tags,
    }
