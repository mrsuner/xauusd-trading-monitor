from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from normalizer_classifier.deduplication_evaluation import metrics, sample_pairs, validate_evaluation_pairs, write_jsonl
from normalizer_classifier.news_deduplication import Decision, JevClient, Pair, Report, pair_state


def pair():
    return Pair(id="a:b", current=Report(id="a", title="Fed holds rates", language="en"),
                candidate=Report(id="b", title="Fed leaves rates unchanged", language="en"))


def answer(choice="duplicate", confidence=0.99):
    probabilities = {key: 0.001 for key in (
        "duplicate", "material_update", "unrelated", "insufficient_evidence",
    )}
    probabilities[choice] = 0.997
    return {"type": "choice", "choice": choice, "confidence": confidence, "probabilities": probabilities}


def test_only_high_confidence_duplicate_can_merge():
    assert Decision.model_validate(answer()).can_merge(0.99, 0.99)
    assert not Decision.model_validate(answer(confidence=0.8)).can_merge(0.99, 0.99)
    for choice in ("material_update", "unrelated", "insufficient_evidence"):
        assert not Decision.model_validate(answer(choice)).can_merge(0.99, 0.99)


@pytest.mark.parametrize("mutation", [
    {"confidence": float("nan")}, {"probabilities": {"duplicate": 1}},
    {"choice": "unrelated"}, {"type": "noul"},
    {"probabilities": {key: 0.9 for key in ("duplicate", "material_update", "unrelated", "insufficient_evidence")}},
])
def test_invalid_responses_do_not_merge(mutation):
    with pytest.raises(ValidationError):
        Decision.model_validate(answer() | mutation)


def test_english_mode_does_not_invent_missing_translation():
    sample = pair()
    sample.current.language = "th"
    with pytest.raises(ValueError, match="existing English"):
        pair_state(sample, "english")
    sample.current.english_content = "Fed holds rates"
    assert pair_state(sample, "english")["current"]["content"] == "Fed holds rates"
    assert "source_name" not in pair_state(sample, "original")["current"]


@pytest.mark.asyncio
async def test_jev_request_and_actual_version_usage():
    def handler(request):
        import json
        body = json.loads(request.content)
        assert request.url.path == "/api/alpha/decisions"
        assert body["model"] == "typesafe/jev-1.13"
        assert set(body["questions"]["relationship"]["criteria"]) == set(answer()["probabilities"])
        assert "untrusted data" in body["questions"]["relationship"]["instructions"]
        return httpx.Response(200, json={"answers": {"relationship": answer()},
                                       "model": "typesafe/jev-1.13-version", "usage": {"cost": 0.000042}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JevClient(client, endpoint="https://openrouter.ai/api/alpha/decisions",
                                 api_key="test-only", model="typesafe/jev-1.13").compare(pair())
    assert result["model"] == "typesafe/jev-1.13-version"
    assert result["usage"]["cost"] == 0.000042


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_failures_are_not_decisions(status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await JevClient(client, endpoint="https://openrouter.ai/api/alpha/decisions",
                            api_key="test-only", model="typesafe/jev-1.13").compare(pair())


def test_metrics_expose_wrong_merges_errors_and_empty_results():
    rows = [
        {"expected": "duplicate", "decision": answer(), "latency_ms": 100, "usage": {"cost": 0.1}},
        {"expected": "material_update", "decision": answer(), "latency_ms": 200},
        {"expected": "unrelated", "error": "ReadTimeout", "latency_ms": 1000},
    ]
    result = metrics(rows, probability=0.99, confidence=0.99)
    assert result["merge_precision"] == 0.5
    assert result["merge_recall"] == 1.0
    assert result["material_updates_suppressed"] == 1
    assert result["errors"] == 1
    assert metrics([], probability=0.99, confidence=0.99)["merge_precision"] is None


def test_sampling_is_cross_source_time_bounded_and_unlabelled():
    reports = [Report(id=str(index), title="Fed holds rates", source_name=source,
                      published_at=datetime(2026, 9, 22, hour, tzinfo=timezone.utc))
               for index, (source, hour) in enumerate([("A", 12), ("A", 11), ("B", 10), ("C", 1)])]
    result = sample_pairs(reports, limit=300)
    assert len(result) == 2
    assert all(item.expected is None and item.split is None for item in result)
    assert all(item.current.source_name != item.candidate.source_name for item in result)


def test_same_id_or_empty_original_report_rejected():
    with pytest.raises(ValidationError):
        Report(id="a", english_content="not an original")
    with pytest.raises(ValidationError):
        Pair(id="a:a", current=pair().current, candidate=pair().current)


def test_evaluation_requires_labels_and_disjoint_splits():
    with pytest.raises(ValueError, match="reviewed label"):
        validate_evaluation_pairs([pair()])
    sample = pair().model_copy(update={"expected": "duplicate", "split": "tuning"})
    validate_evaluation_pairs([sample])
    other = Pair(id="a:c", current=sample.current, candidate=Report(id="c", title="another report"),
                 expected="unrelated", split="held_out")
    with pytest.raises(ValueError, match="both tuning"):
        validate_evaluation_pairs([sample, other])


def test_reversed_pair_and_overwritten_labels_rejected(tmp_path):
    sample = pair().model_copy(update={"expected": "duplicate", "split": "held_out"})
    reversed_pair = sample.model_copy(update={"id": "b:a", "current": sample.candidate, "candidate": sample.current})
    with pytest.raises(ValueError, match="reversed"):
        validate_evaluation_pairs([sample, reversed_pair])
    output = tmp_path / "labels.jsonl"
    write_jsonl(output, [{"label": "duplicate"}])
    with pytest.raises(FileExistsError):
        write_jsonl(output, [])


@pytest.mark.asyncio
async def test_timeout_remains_an_error():
    def handler(request):
        raise httpx.ReadTimeout("test timeout", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ReadTimeout):
            await JevClient(client, endpoint="https://openrouter.ai/api/alpha/decisions",
                            api_key="test-only", model="typesafe/jev-1.13").compare(pair())
