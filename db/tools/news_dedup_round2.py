"""Build authored diagnostic controls, not human-reviewed production ground truth."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from normalizer_classifier.deduplication_evaluation import validate_evaluation_pairs, write_jsonl
from normalizer_classifier.news_deduplication import Pair, Report


def build_pairs() -> list[Pair]:
    pairs = []
    for entity in ("Aster", "Birch", "Cedar", "Dahlia"):
        # Fictional organizations prevent authored controls being mistaken for real news.
        actor = f"Fictional {entity} Central Bank"
        cases = [
            ("duplicate_paraphrase", "duplicate",
             f"{actor} keeps its policy rate at 3.25% at the September meeting.",
             f"{actor} leaves the policy rate unchanged at 3.25% at September's meeting."),
            ("duplicate_number_word", "duplicate",
             f"{actor} publishes eight research papers at its annual conference.",
             f"{actor} releases 8 research papers at its annual conference."),
            ("numeric_revision", "material_update",
             f"{actor} corrects September inflation to 3.5% after a calculation error.",
             f"{actor} reports September inflation at 3.25%."),
            ("denial", "material_update",
             f"{actor} officially denies plans to sell its gold reserves.",
             f"Unconfirmed sources claim {actor} plans to sell its gold reserves."),
            ("different_release", "unrelated",
             f"{actor} reports August inflation of 3.25%.",
             f"{actor} reports September inflation of 3.25%."),
            ("shared_actor", "unrelated",
             f"{actor} keeps its policy rate unchanged at September's meeting.",
             f"{actor} opens a new museum about the history of banknotes."),
            ("missing_fact", "insufficient_evidence",
             f"Important news from {actor}.",
             f"{actor} keeps its policy rate unchanged at September's meeting."),
            ("vague_same_topic", "insufficient_evidence",
             f"There is an important development concerning {actor}.",
             f"An important matter involving {actor} is being reported."),
        ]
        for index, (slice_name, label, left, right) in enumerate(cases):
            group = f"round2-{entity.lower()}-{index}"
            # Actor groups never cross splits, including the unrelated-pair developments.
            groups = [f"round2-{entity.lower()}"]
            pair = Pair(id=group,
                        current=Report(id=f"{group}-a", title=left, language="en",
                                       published_at=datetime(2026, 9, 27, 8, tzinfo=timezone.utc)),
                        candidate=Report(id=f"{group}-b", title=right, language="en",
                                         published_at=datetime(2026, 9, 27, 7, tzinfo=timezone.utc)),
                        expected=label, split="tuning" if entity in {"Aster", "Birch"} else "held_out",
                        slice=f"authored_{slice_name}", development_groups=groups,
                        reviewed_by="assistant-authored-control-not-human-review",
                        rationale=f"Authored diagnostic condition: {slice_name}. Not a production report.")
            pairs.append(pair)
    validate_evaluation_pairs(pairs)
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pairs = build_pairs()
    write_jsonl(args.output, [pair.model_dump(mode="json") for pair in pairs])
    print(json.dumps({"pairs": len(pairs), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      "source": "authored diagnostic controls", "human_reviewed": False}))


if __name__ == "__main__":
    main()
