"""Offline sampling/scoring and explicitly enabled paid Jev evaluation."""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import os
import subprocess
import time
from pathlib import Path
from statistics import median

import httpx
from rapidfuzz.fuzz import token_set_ratio

from .news_deduplication import Decision, JevClient, Pair, Relationship, Report
from .news_fact_guards import merge_blockers


def sample_pairs(reports: list[Report], *, limit: int, window_hours: int = 6, strategy: str = "similar") -> list[Pair]:
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
    ordered = [pair for _, pair in sorted(ranked, key=lambda row: (-row[0], row[1].id))]
    if strategy == "similar" or len(ordered) <= limit:
        return ordered[:limit]
    # Cover the similarity distribution, rather than presenting 300 near-identical
    # positives as a benchmark. Reserve space for actual original headline-only cases.
    headline_pairs = [pair for pair in ordered if not pair.current.content or not pair.candidate.content][:30]
    selected = {pair.id: pair for pair in headline_pairs}
    remaining = limit - len(selected)
    for index in range(remaining):
        pair = ordered[round(index * (len(ordered) - 1) / max(remaining - 1, 1))]
        selected.setdefault(pair.id, pair)
    for pair in ordered:
        if len(selected) >= limit:
            break
        selected.setdefault(pair.id, pair)
    return list(selected.values())


def metrics(rows: list[dict], *, probability: float, confidence: float) -> dict:
    labelled = [row for row in rows if row.get("expected") is not None]
    successful = [row for row in labelled if row.get("decision") is not None]
    merges = [row for row in successful if Decision.model_validate(row["decision"]).can_merge(probability, confidence)]
    correct = sum(row["expected"] == Relationship.DUPLICATE for row in merges)
    guarded = [row for row in merges if "merge_blockers" in row and not row["merge_blockers"]]
    guarded_correct = sum(row["expected"] == Relationship.DUPLICATE for row in guarded)
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
        "guarded_merges": len(guarded),
        "guarded_precision": guarded_correct / len(guarded) if guarded else None,
        "guarded_recall": guarded_correct / duplicates if duplicates else None,
        "guarded_material_updates_suppressed": sum(row["expected"] == Relationship.MATERIAL_UPDATE for row in guarded),
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
    development_memberships: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        identity = tuple(sorted((pair.current.id, pair.candidate.id)))
        if identity in seen_pairs:
            raise ValueError("duplicate or reversed report pair")
        seen_pairs.add(identity)
        for group in pair.development_groups:
            if group in development_memberships and development_memberships[group] != pair.split:
                raise ValueError("development appears in both tuning and held-out splits")
            development_memberships[group] = pair.split
        for report in (pair.current, pair.candidate):
            if report.id in memberships and memberships[report.id] != pair.split:
                raise ValueError("report appears in both tuning and held-out splits")
            memberships[report.id] = pair.split


async def evaluate(args: argparse.Namespace) -> None:
    manifest = None
    if args.manifest:
        from .deduplication_dataset import verify_manifest
        manifest = verify_manifest(args.input, args.manifest)
    raw_input = args.input.read_bytes()
    input_digest = hashlib.sha256(raw_input).hexdigest()
    if manifest and input_digest != manifest["sha256"]:
        raise ValueError("dataset changed after manifest verification")
    pairs = [Pair.model_validate(json.loads(line)) for line in raw_input.splitlines() if line.strip()]
    validate_evaluation_pairs(pairs)
    if len(pairs) >= 200 and not manifest:
        raise ValueError("acceptance-sized evaluation requires a frozen manifest")
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
                   "text_mode": args.text_mode, "merge_blockers": merge_blockers(pair, text_mode=args.text_mode)}
            row["dataset_sha256"] = input_digest
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
    sample.add_argument("--strategy", choices=["similar", "review"], default="similar")
    sample.add_argument("--exclude-input", type=Path)
    run = commands.add_parser("run")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--allow-paid", action="store_true")
    run.add_argument("--manifest", type=Path)
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
        ), selected AS (
          (SELECT r.id FROM public_raw_items r CROSS JOIN latest
           WHERE r.is_visible AND r.published_at >= latest.t - interval '72 hours'
           ORDER BY r.published_at DESC, r.id LIMIT 1200)
          UNION
          SELECT r.id FROM public_raw_items r
          WHERE r.is_visible AND nullif(btrim(r.original_content),'') IS NULL
            AND nullif(btrim(r.title),'') IS NOT NULL
          UNION
          SELECT neighbour.id FROM public_raw_items h
          CROSS JOIN LATERAL (
            SELECT r.id FROM public_raw_items r WHERE r.is_visible
              AND r.source_name <> h.source_name
              AND r.published_at BETWEEN h.published_at - interval '6 hours' AND h.published_at + interval '6 hours'
            ORDER BY abs(extract(epoch FROM (r.published_at-h.published_at))), r.id LIMIT 8
          ) neighbour
          WHERE h.is_visible AND nullif(btrim(h.original_content),'') IS NULL
            AND nullif(btrim(h.title),'') IS NOT NULL
        ), reports AS (
          SELECT r.id::text, r.title, r.original_content AS content,
            coalesce(t.full_translation, t.summary) AS english_content,
            r.language, r.source_name, r.source_url, r.published_at
          FROM public_raw_items r JOIN selected ON selected.id=r.id
          LEFT JOIN public_raw_item_translations t ON t.public_raw_item_id=r.id
            AND t.language='en' AND t.status IN ('completed', 'completed_truncated')
          WHERE nullif(btrim(r.title),'') IS NOT NULL OR nullif(btrim(r.original_content),'') IS NOT NULL
          ORDER BY r.published_at DESC, r.id
        ) SELECT row_to_json(reports) FROM reports
        """
        result = subprocess.run(["docker", "exec", "lukes-postgres", "psql", "-X", "-U", "postgres",
                                 "-d", "xauusd_public", "-At", "-v", "ON_ERROR_STOP=1", "-c", sql],
                                capture_output=True, text=True, check=True)
        reports = [Report.model_validate(json.loads(line)) for line in result.stdout.splitlines() if line]
        if args.exclude_input:
            prior = [Pair.model_validate(json.loads(line)) for line in args.exclude_input.read_text().splitlines() if line.strip()]
            seen_reports = {report.id for pair in prior for report in (pair.current, pair.candidate)}
            reports = [report for report in reports if report.id not in seen_reports]
        pairs = sample_pairs(reports, limit=args.limit, strategy=args.strategy)
        write_jsonl(args.output, [pair.model_dump(mode="json") for pair in pairs])
        print(json.dumps({"reports": len(reports), "unlabelled_pairs": len(pairs),
                          "strategy": args.strategy,
                          "note": "Unlabelled candidates, not ground truth; review originals before evaluating."}))


if __name__ == "__main__":
    main()
