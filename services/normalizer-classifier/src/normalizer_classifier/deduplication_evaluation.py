"""Offline sampling/scoring and explicitly enabled paid Jev evaluation."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from statistics import median

import httpx
from rapidfuzz.fuzz import token_set_ratio

from .news_deduplication import Decision, JevClient, Pair, Relationship, Report


def sample_pairs(reports: list[Report], *, limit: int, window_hours: int = 6) -> list[Pair]:
    """Generate unlabelled cross-source candidates, not ground truth or adoption evidence."""
    reports = sorted((item for item in reports if item.published_at is not None),
                     key=lambda item: (item.published_at, item.id), reverse=True)
    ranked = []
    for index, current in enumerate(reports):
        for candidate in reports[index + 1:]:
            if not current.published_at or not candidate.published_at:
                continue
            if (current.published_at - candidate.published_at).total_seconds() > window_hours * 3600:
                break
            # Unknown source provenance does not establish a cross-source pair.
            if not current.source_name or not candidate.source_name or current.source_name == candidate.source_name:
                continue
            left = current.english_content or current.content or current.title or ""
            right = candidate.english_content or candidate.content or candidate.title or ""
            score = token_set_ratio(left, right)
            ranked.append((score, Pair(
                id=f"{current.id}:{candidate.id}", current=current, candidate=candidate,
            )))
    # Similarity is only a sampling heuristic; cannot establish factual identity.
    return [pair for _, pair in sorted(ranked, key=lambda row: (-row[0], row[1].id))[:limit]]


def metrics(rows: list[dict], *, probability: float, confidence: float) -> dict:
    labelled = [row for row in rows if row.get("expected") is not None]
    successful = [row for row in labelled if row.get("decision") is not None]
    merges = [row for row in successful if Decision.model_validate(row["decision"]).can_merge(probability, confidence)]
    correct = sum(row["expected"] == Relationship.DUPLICATE for row in merges)
    duplicates = sum(row["expected"] == Relationship.DUPLICATE for row in labelled)
    updates = [row for row in labelled if row["expected"] == Relationship.MATERIAL_UPDATE]
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "pairs": len(rows), "labelled": len(labelled), "errors": sum("error" in row for row in rows),
        "accuracy": (sum(row["decision"]["choice"] == row["expected"] for row in successful) / len(successful)) if successful else None,
        "automatic_merges": len(merges),
        "merge_precision": correct / len(merges) if merges else None,
        "expected_duplicates": duplicates,
        "merge_recall": correct / duplicates if duplicates else None,
        "material_updates": len(updates),
        "material_updates_suppressed": sum(row["expected"] == Relationship.MATERIAL_UPDATE for row in merges),
        "cost_usd": sum(float(row.get("usage", {}).get("cost", 0)) for row in rows),
        "cost_is_partial": any("error" in row for row in rows),
        "latency_p50_ms": median(latencies) if latencies else None,
        "probability_threshold": probability, "confidence_threshold": confidence,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an earlier evaluation or a manually labelled sample.
    with path.open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_evaluation_pairs(pairs: list[Pair]) -> None:
    """Reject unreviewed inputs and report leakage before spending model credits."""
    if len({pair.id for pair in pairs}) != len(pairs):
        raise ValueError("duplicate pair IDs")
    if any(pair.expected is None or pair.split is None for pair in pairs):
        raise ValueError("every evaluation pair needs a reviewed label and split")
    memberships: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        identity = tuple(sorted((pair.current.id, pair.candidate.id)))
        if identity in seen_pairs:
            raise ValueError("duplicate or reversed report pair")
        seen_pairs.add(identity)
        for report in (pair.current, pair.candidate):
            if report.id in memberships and memberships[report.id] != pair.split:
                raise ValueError("report appears in both tuning and held-out splits")
            memberships[report.id] = pair.split


async def evaluate(args: argparse.Namespace) -> None:
    pairs = [Pair.model_validate(json.loads(line)) for line in args.input.read_text().splitlines() if line.strip()]
    validate_evaluation_pairs(pairs)
    if args.output.exists():
        raise ValueError("output already exists")
    if not args.allow_paid or not 0 < len(pairs) <= args.max_pairs:
        raise ValueError("paid evaluation requires --allow-paid and a bounded input")
    # No model/API-key/URL fallback to other services' unrelated configuration.
    async with httpx.AsyncClient(timeout=15) as client:
        jev = JevClient(client, endpoint=os.environ["NEWS_DEDUP_MODEL_ENDPOINT"],
                        api_key=os.environ["NEWS_DEDUP_MODEL_API_KEY"], model=os.environ["NEWS_DEDUP_MODEL_NAME"])
        rows = []
        for pair in pairs:
            row = {"id": pair.id, "expected": pair.expected, "split": pair.split, "slice": pair.slice,
                   "text_mode": args.text_mode}
            start = time.perf_counter()
            try:
                row.update(await jev.compare(pair, text_mode=args.text_mode))
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                # Exception strings may contain endpoint details; retain only the error class.
                row["error"] = type(exc).__name__
            row["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            rows.append(row)
        write_jsonl(args.output, rows)
        print(json.dumps({
            "overall": metrics(rows, probability=args.probability, confidence=args.confidence),
            "by_split": {split: metrics([row for row in rows if row["split"] == split],
                                       probability=args.probability, confidence=args.confidence)
                         for split in sorted({row["split"] for row in rows})},
            "by_slice": {slice_name: metrics([row for row in rows if row["slice"] == slice_name],
                                            probability=args.probability, confidence=args.confidence)
                         for slice_name in sorted({row["slice"] for row in rows})},
        }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample")
    sample.add_argument("--output", type=Path, required=True)
    sample.add_argument("--limit", type=int, default=300)
    run = commands.add_parser("run")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--allow-paid", action="store_true")
    run.add_argument("--max-pairs", type=int, default=300)
    run.add_argument("--text-mode", choices=["original", "english"], default="original")
    run.add_argument("--probability", type=float, required=True)
    run.add_argument("--confidence", type=float, required=True)
    args = parser.parse_args()
    if args.command == "run":
        # Validate thresholds before any paid request, including non-finite values.
        import math
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in (args.probability, args.confidence)):
            parser.error("thresholds must be finite and between zero and one")
        asyncio.run(evaluate(args))
    else:
        if not 1 <= args.limit <= 300 or args.output.exists():
            parser.error("sample limit must be 1–300 and output must not exist")
        # Explicit local container/database only; no production URL or database writes.
        sql = """
        WITH latest AS (
          SELECT max(published_at) AS t FROM public_raw_items WHERE is_visible
        ), reports AS (
          SELECT r.id::text, r.title, r.original_content AS content,
            coalesce(t.full_translation, t.summary) AS english_content,
            r.language, r.source_name, r.source_url, r.published_at
          FROM public_raw_items r CROSS JOIN latest
          LEFT JOIN public_raw_item_translations t ON t.public_raw_item_id=r.id
            AND t.language='en' AND t.status IN ('completed', 'completed_truncated')
          WHERE r.is_visible AND r.published_at >= latest.t - interval '72 hours'
            AND (nullif(btrim(r.title),'') IS NOT NULL OR nullif(btrim(r.original_content),'') IS NOT NULL)
          ORDER BY r.published_at DESC, r.id LIMIT 1200
        ) SELECT row_to_json(reports) FROM reports
        """
        result = subprocess.run(["docker", "exec", "lukes-postgres", "psql", "-X", "-U", "postgres",
                                 "-d", "xauusd_public", "-At", "-v", "ON_ERROR_STOP=1", "-c", sql],
                                capture_output=True, text=True, check=True)
        reports = [Report.model_validate(json.loads(line)) for line in result.stdout.splitlines() if line]
        pairs = sample_pairs(reports, limit=args.limit)
        write_jsonl(args.output, [pair.model_dump(mode="json") for pair in pairs])
        print(json.dumps({"reports": len(reports), "unlabelled_pairs": len(pairs),
                          "note": "Similarity-selected sample; add hard negatives and human labels before evaluating."}))


if __name__ == "__main__":
    main()
