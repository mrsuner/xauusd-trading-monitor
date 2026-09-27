import argparse
import importlib.util
from pathlib import Path

import pytest

from normalizer_classifier.deduplication_dataset import dataset_manifest
from normalizer_classifier.deduplication_evaluation import evaluate, metrics, write_jsonl
from normalizer_classifier.news_fact_guards import merge_blockers


def authored_pairs():
    path = Path(__file__).resolve().parents[3] / "db/tools/news_dedup_round2.py"
    spec = importlib.util.spec_from_file_location("round2_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_pairs()


def test_authored_controls_have_all_labels_and_disjoint_actor_groups():
    pairs = authored_pairs()
    assert len(pairs) == 32
    assert {pair.expected for pair in pairs} == {"duplicate", "material_update", "unrelated", "insufficient_evidence"}
    tuning = {group for pair in pairs if pair.split == "tuning" for group in pair.development_groups}
    held_out = {group for pair in pairs if pair.split == "held_out" for group in pair.development_groups}
    assert not tuning.intersection(held_out)
    assert all("not-human-review" in pair.reviewed_by for pair in pairs)


def test_changed_figures_and_periods_are_blocked_but_number_paraphrase_is_not():
    for pair in authored_pairs():
        blockers = merge_blockers(pair)
        if pair.slice in {"authored_numeric_revision", "authored_different_release"}:
            assert blockers
        if pair.expected == "duplicate":
            assert not blockers


def test_small_authored_controls_cannot_be_frozen_as_acceptance(tmp_path):
    path = tmp_path / "controls.jsonl"
    write_jsonl(path, [pair.model_dump(mode="json") for pair in authored_pairs()])
    with pytest.raises(ValueError, match="200–300"):
        dataset_manifest(path)


def test_legacy_results_without_guards_do_not_imply_guarded_safety():
    result = metrics([{"expected": "duplicate", "latency_ms": 1, "decision": {
        "type": "choice", "choice": "duplicate", "confidence": 1,
        "probabilities": {"duplicate": 1, "material_update": 0, "unrelated": 0, "insufficient_evidence": 0},
    }}], probability=0.95, confidence=0.95)
    assert result["automatic_merges"] == 1
    assert result["guarded_merges"] == 0


@pytest.mark.asyncio
async def test_200_pair_run_rejected_before_any_paid_client_without_manifest(tmp_path):
    pairs = []
    template = authored_pairs()[0]
    for index in range(200):
        pair = template.model_copy(update={
            "id": f"pair-{index}",
            "current": template.current.model_copy(update={"id": f"left-{index}"}),
            "candidate": template.candidate.model_copy(update={"id": f"right-{index}"}),
        })
        pairs.append(pair.model_dump(mode="json"))
    source = tmp_path / "pairs.jsonl"
    write_jsonl(source, pairs)
    args = argparse.Namespace(input=source, output=tmp_path / "result.jsonl", manifest=None,
                              allow_paid=True, max_pairs=200, text_mode="original")
    with pytest.raises(ValueError, match="frozen manifest"):
        await evaluate(args)
    assert not args.output.exists()
