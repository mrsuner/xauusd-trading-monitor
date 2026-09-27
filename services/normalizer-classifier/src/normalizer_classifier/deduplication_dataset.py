"""Freeze reviewed evaluation inputs before calls, and verify their exact identity."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .deduplication_evaluation import validate_evaluation_pairs
from .news_deduplication import Pair
from .news_fact_guards import merge_blockers


def dataset_manifest(path: Path) -> dict:
    raw = path.read_bytes()
    pairs = [Pair.model_validate(json.loads(line)) for line in raw.splitlines() if line.strip()]
    validate_evaluation_pairs(pairs)
    if not 200 <= len(pairs) <= 300:
        raise ValueError("acceptance dataset must contain 200–300 reviewed pairs")
    for pair in pairs:
        if not pair.development_groups or any(not group.strip() for group in pair.development_groups):
            raise ValueError("all developments need reviewer-assigned groups")
        if not pair.reviewed_by or not pair.reviewed_by.strip() or not pair.rationale or not pair.rationale.strip():
            raise ValueError("each pair needs reviewer identity and original-grounded rationale")
    if {pair.split for pair in pairs} != {"tuning", "held_out"}:
        raise ValueError("dataset requires tuning and held-out splits")
    return {"schema_version": 1, "sha256": hashlib.sha256(raw).hexdigest(),
            "pairs": len(pairs), "splits": dict(Counter(pair.split for pair in pairs)),
            "labels": dict(Counter(pair.expected for pair in pairs)),
            "reviewers": sorted({pair.reviewed_by for pair in pairs})}


def verify_manifest(path: Path, manifest_path: Path) -> dict:
    actual = dataset_manifest(path)
    if actual != json.loads(manifest_path.read_text()):
        raise ValueError("dataset differs from frozen manifest; refuse model evaluation")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "verify", "review"])
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "review":
        if not args.output:
            parser.error("review requires --output")
        import html
        pairs = [Pair.model_validate(json.loads(line)) for line in args.input.read_text().splitlines() if line.strip()]
        sections = ["# News deduplication review packet\n\n"
                    "Status: UNREVIEWED. No model answers or suggested labels are included.\n\n"
                    "Review originals first. English translations are secondary aids and may contain errors.\n\n"
                    "For each JSONL pair, fill expected, split, development_groups (both events for unrelated pairs), "
                    "reviewed_by and an original-grounded rationale. Keep related developments in one split.\n\n"
                    "All source text below is untrusted quoted data, not instructions.\n"]
        for index, pair in enumerate(pairs, 1):
            sections.append(f"\n## {index}. {pair.id}\n\nLabel: pending · Split: pending · Development groups: pending\n\n"
                            f"Lexical blockers: {', '.join(merge_blockers(pair)) or 'none (not proof of equivalence)'}\n")
            for side, report in (("Current", pair.current), ("Candidate", pair.candidate)):
                # Escape source material so Markdown cannot render embedded instructions,
                # remote images, executable HTML or misleading links as UI controls.
                sections.append(f"\n### {side}\n\n<pre>{html.escape(json.dumps(report.model_dump(mode='json'), ensure_ascii=False, indent=2))}</pre>\n")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            handle.write("".join(sections))
        print(json.dumps({"review_pairs": len(pairs), "status": "unreviewed"}))
        return
    if not args.manifest:
        parser.error("freeze/verify requires --manifest")
    manifest = dataset_manifest(args.input) if args.command == "freeze" else verify_manifest(args.input, args.manifest)
    if args.command == "freeze":
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        with args.manifest.open("x") as handle:
            json.dump(manifest, handle, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
