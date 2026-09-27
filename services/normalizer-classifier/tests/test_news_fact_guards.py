import json

import pytest

from normalizer_classifier.deduplication_dataset import dataset_manifest, verify_manifest
from normalizer_classifier.deduplication_evaluation import validate_evaluation_pairs, write_jsonl
from normalizer_classifier.news_deduplication import Pair, Report
from normalizer_classifier.news_fact_guards import figures, merge_blockers, periods


def make_pair(left, right):
    return Pair(id="a:b", current=Report(id="a", title=left), candidate=Report(id="b", title=right))


@pytest.mark.parametrize("left,right", [
    ("168 killed", "198 killed"), ("CPI 3.2%", "CPI 3.1%"),
    ("rate -1%", "rate 1%"), ("increase 25 bps", "increase 25%"),
    ("10 USD", "10 EUR"), ("20 barrels", "20 tonnes"),
    ("USD 10", "EUR 10"), ("$10", "€10"), ("1 million barrels", "1 billion barrels"),
])
def test_numeric_and_unit_difference_blocks_merge(left, right):
    assert "original_numeric_or_unit_difference" in merge_blockers(make_pair(left, right))


def test_unicode_and_literal_format_equivalence():
    assert figures("۱۶۸ killed") == figures("168 killed")
    assert figures("１，０００ barrels") == figures("1000 barrels")
    assert figures("۳٫۲٪") == figures("3.20 percent")
    assert figures("3.2% https://example.test/198 @Source123") == figures("3.2%")
    assert figures("1 million barrels") == figures("1000000 barrels")
    assert "month:5" not in periods("Fed may cut rates")
    assert figures("eight Palestinians") == figures("8 Palestinians")
    assert figures("two thousand barrels") == figures("2000 barrels")
    assert figures("eighty people") != figures("eight people")
    assert figures("TEHRAN, Sep. 19 (MNA) – 168 killed") == figures("168 killed")
    assert figures("The meeting on September 19 approved 168 units") != figures("168 units")


@pytest.mark.parametrize("left,right", [
    ("August CPI 3.2%", "September CPI 3.2%"),
    ("2025 CPI 3.2%", "2026 CPI 3.2%"),
    ("Q3 CPI 3.2%", "Q4 CPI 3.2%"),
])
def test_period_difference_blocks_merge(left, right):
    assert "original_period_difference" in merge_blockers(make_pair(left, right))


def test_known_months_normalize_and_translations_cannot_authorize_merges():
    assert periods("September") == periods("9月")
    assert periods("September") == periods("九月")
    assert figures("9月 CPI 3.2%") == figures("September CPI 3.2%")
    sample = make_pair("Fed holds rates", "Federal Reserve holds rates")
    assert merge_blockers(sample) == []
    assert merge_blockers(sample, text_mode="english") == ["translation_only_decision"]


def test_different_reports_in_same_development_cannot_leak_across_splits():
    a = make_pair("headline", "another headline").model_copy(update={
        "expected": "duplicate", "split": "tuning", "development_groups": ["fed-september"],
    })
    b = Pair(id="c:d", current=Report(id="c", title="same development"),
             candidate=Report(id="d", title="same development translated"),
             expected="duplicate", split="held_out", development_groups=["fed-september"])
    with pytest.raises(ValueError, match="development appears"):
        validate_evaluation_pairs([a, b])


def reviewed_rows():
    return [Pair(id=f"pair-{i}", current=Report(id=f"a-{i}", title="Fed holds rates"),
                 candidate=Report(id=f"b-{i}", title="Fed holds rates"), expected="duplicate",
                 split="tuning" if i < 100 else "held_out", development_groups=[f"event-{i}"],
                 reviewed_by="test-reviewer", rationale="Original reports describe the same fact.").model_dump(mode="json")
            for i in range(200)]


def test_freeze_and_verify_reject_changed_labels_or_text(tmp_path):
    source, manifest_path = tmp_path / "pairs.jsonl", tmp_path / "manifest.json"
    rows = reviewed_rows()
    write_jsonl(source, rows)
    manifest = dataset_manifest(source)
    with manifest_path.open("x") as handle:
        json.dump(manifest, handle)
    assert verify_manifest(source, manifest_path)["pairs"] == 200
    changed = tmp_path / "changed.jsonl"
    rows[0]["expected"] = "material_update"
    write_jsonl(changed, rows)
    with pytest.raises(ValueError, match="differs from frozen"):
        verify_manifest(changed, manifest_path)


def test_freeze_requires_review_metadata(tmp_path):
    rows = reviewed_rows()
    rows[0]["rationale"] = None
    source = tmp_path / "unreviewed.jsonl"
    write_jsonl(source, rows)
    with pytest.raises(ValueError, match="reviewer identity"):
        dataset_manifest(source)
