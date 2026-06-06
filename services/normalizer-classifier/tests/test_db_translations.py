from __future__ import annotations

from normalizer_classifier.db import (
    DEFAULT_RAW_ITEM_TRANSLATION_LANGUAGES,
    aggregate_raw_item_translation_status,
    raw_item_translation_rows_for_result,
)
from normalizer_classifier.models import AuxiliaryTextResult


def test_raw_item_translation_rows_include_default_languages_for_legacy_dual_write() -> None:
    result = AuxiliaryTextResult.model_validate(
        {
            "summary_zh": "中文摘要",
            "summary_en": "English summary",
            "full_translation_zh": "中文全文",
            "full_translation_en": "English full text",
        }
    )

    rows = raw_item_translation_rows_for_result(
        result,
        status="completed",
        model_provider="provider",
        model="model",
        input_chars=123,
    )

    assert DEFAULT_RAW_ITEM_TRANSLATION_LANGUAGES == ("zh-Hant", "en")
    assert [row["language"] for row in rows] == ["zh-Hant", "en"]
    assert rows[0]["summary"] == "中文摘要"
    assert rows[0]["full_translation"] == "中文全文"
    assert rows[1]["summary"] == "English summary"
    assert rows[1]["input_chars"] == 123


def test_raw_item_translation_rows_include_additional_languages() -> None:
    result = AuxiliaryTextResult.model_validate(
        {
            "translations": [
                {"language": "zh-Hant", "summary": "中文摘要", "full_translation": "中文全文"},
                {"language": "en", "summary": "English summary", "full_translation": "English full text"},
                {"language": "ja", "summary": "日本語要約", "full_translation": "日本語全文"},
            ],
        }
    )

    rows = raw_item_translation_rows_for_result(
        result,
        status="completed",
        model_provider="provider",
        model="model",
        input_chars=123,
    )

    assert [row["language"] for row in rows] == ["zh-Hant", "en", "ja"]
    assert rows[2]["summary"] == "日本語要約"
    assert rows[2]["full_translation"] == "日本語全文"


def test_aggregate_raw_item_translation_status_complete_sets() -> None:
    assert aggregate_raw_item_translation_status([]) == "pending"
    assert aggregate_raw_item_translation_status(["pending", "pending"]) == "pending"
    assert aggregate_raw_item_translation_status(["completed", "completed"]) == "completed"
    assert aggregate_raw_item_translation_status(["completed", "completed_truncated"]) == "completed_truncated"
    assert aggregate_raw_item_translation_status(["skipped", "skipped"]) == "skipped"
    assert aggregate_raw_item_translation_status(["failed", "failed"]) == "failed"


def test_aggregate_raw_item_translation_status_partial_completion() -> None:
    assert aggregate_raw_item_translation_status(["completed", "pending"]) == "partial_completed"
    assert aggregate_raw_item_translation_status(["completed_truncated", "failed"]) == "partial_completed"
    assert aggregate_raw_item_translation_status(["completed", "skipped"]) == "partial_completed"
    assert aggregate_raw_item_translation_status(["failed", "pending"]) == "pending"
    assert aggregate_raw_item_translation_status(["failed", "skipped"]) == "failed"
