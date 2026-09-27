import json

import httpx
import pytest

from normalizer_classifier.deduplication_comparison import ChatComparisonClient, comparison_summary, preflight
from normalizer_classifier.news_deduplication import Pair, Report
from normalizer_classifier.news_fact_guards import merge_blockers


def pair():
    return Pair(id="a:b", current=Report(id="a", title="Fed holds rates"),
                candidate=Report(id="b", title="Fed keeps rates unchanged"),
                expected="duplicate", split="tuning")


@pytest.mark.parametrize("spent,budget,reserve", [(4.95, 5, 0.05), (0, 6, 0.05),
                                                  (0, 5, 0.01), (float("nan"), 5, 0.05)])
def test_reject_unsafe_budget_before_calls(spent, budget, reserve):
    with pytest.raises(ValueError):
        preflight([pair()], spent=spent, budget=budget, reserve=reserve)


def test_reserve_and_source_limits():
    assert preflight([pair()], spent=0.2, budget=5, reserve=0.05) == pytest.approx(0.3)
    sample = pair()
    sample.current.content = "x" * 20001
    with pytest.raises(ValueError, match="input size"):
        preflight([sample], spent=0, budget=5, reserve=0.05)


def test_summary_excludes_errors_and_rejects_hash_mismatch():
    row = {"id": "a:b", "engine": "jev", "dataset_sha256": "abc", "slice": "snapshot",
           "expected": "duplicate", "latency_ms": 1, "error": "ValueError"}
    assert comparison_summary([row])["comparable_pairs"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        comparison_summary([row, row])
    decision = {"type": "choice", "choice": "duplicate", "confidence": 1,
                "probabilities": {"duplicate": 1, "material_update": 0, "unrelated": 0, "insufficient_evidence": 0}}
    left = row | {"decision": decision, "merge_blockers": []}
    right = left | {"engine": "generative", "merge_blockers": ["numeric_difference"]}
    result = comparison_summary([left, right])
    assert result["choice_agreement"] == 1
    assert result["guarded_merge_disagreement_ids"] == ["a:b"]
    with pytest.raises(ValueError, match="hashes differ"):
        comparison_summary([left, right | {"dataset_sha256": "changed"}])


@pytest.mark.parametrize("current,candidate", [
    ("The minister has met the counterpart in Tehran.", "The minister arrived in Tehran for talks."),
    ("The minister arrived in Tehran.", "The minister departed Islamabad for Tehran."),
    ("The bank denied gold sales.", "Rumors suggest the bank sold gold."),
    ("The bank confirmed gold sales.", "Unconfirmed reports say the bank sold gold."),
])
def test_original_progress_and_uncertainty_veto(current, candidate):
    sample = Pair(id="a:b", current=Report(id="a", content=current), candidate=Report(id="b", content=candidate))
    assert "original_status_cue_difference" in merge_blockers(sample)


def test_matching_status_cues_do_not_prove_same_event():
    sample = Pair(id="a:b", current=Report(id="a", content="The minister arrived in Tehran."),
                  candidate=Report(id="b", content="A football team arrived in Tehran."))
    assert "original_status_cue_difference" not in merge_blockers(sample)


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["stop", "length"])
async def test_chat_criteria_no_labels_and_truncation_rejected(finish):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 1024
        assert payload["reasoning"] == {"effort": "none"}
        assert "expected" not in payload["messages"][1]["content"]
        assert "different reporting periods" in payload["messages"][0]["content"]
        decision = {"type": "choice", "choice": "duplicate", "confidence": 1,
                    "probabilities": {"duplicate": 1, "material_update": 0,
                                      "unrelated": 0, "insufficient_evidence": 0}}
        return httpx.Response(200, json={"id": "test-id", "model": "test-model",
            "usage": {"cost": 0.001}, "choices": [{"finish_reason": finish,
            "message": {"content": json.dumps({"decision": decision, "rationale": "Same fact"})}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ChatComparisonClient(client, api_key="test-only", model="test-model")
        if finish == "length":
            with pytest.raises(ValueError, match="incomplete"):
                await adapter.compare(pair())
        else:
            assert (await adapter.compare(pair()))["decision"]["choice"] == "duplicate"
