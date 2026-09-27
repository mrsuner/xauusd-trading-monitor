# Jev cross-source deduplication pilot — 2026-09-26

Status: Pilot completed; adoption gate NOT passed. No production suppression, schema migration, UI change or notification delivery.

## Method and limits

- Actual OpenRouter model: `typesafe/jev-1.13-20260917`, requested as `typesafe/jev-1.13`.
- 32 pairs: 20 real snapshot pairs and 12 authored controls. Snapshot labels are assistant-reviewed and provisional, NOT human-reviewed ground truth.
- Two calls per pair: original text and existing English text. English controls use explicitly authored translations; these are not production translation quality evidence.
- 64 paid requests, zero HTTP/parsing errors. No generative-model comparison was run: authorization in this turn specifically covered Jev.
- `probability >= 0.99` and `confidence >= 0.99` are unchanged pilot parameters, not a calibrated production policy.
- Initial labels used English translations as reading aids. Raw-source review revealed incorrect labels caused by translation differences. Four provisional labels were corrected in v2 and original results rescored without rerunning requests. Keep v1 unchanged for audit.
- Because labels were revised after inspecting results, the snapshot split named `held_out` is NOT an independent held-out benchmark. No tuning/adoption conclusion may be drawn from it. Build a new reviewed verification set before acceptance.

## Results against provisional v2 labels

| Metric | Original text | English text |
| --- | --- | --- |
| Successful requests | 32 | 32 |
| Label agreement | 29/32 (90.625%) | 29/32 (90.625%) |
| Automatic merge candidates | 7 | 8 |
| Incorrect merges observed | 0/7 | 0/8 |
| Material updates suppressed | 0/8 | 0/8 |
| P50 round-trip | 365.125 ms | 332.89 ms |
| Recorded request cost | US$0.000919590 | US$0.000913542 |

Total recorded cost: **US$0.001833132**. These small merge denominators do not establish 99% precision, and zero observed mistakes does not imply safety on unseen news.

## Findings

1. **Original facts must govern labels and canonical matching.** One source said 168 schoolchildren/teachers, while an existing English translation changed it to 198; another translated the Persian ICC sanctions headline into an Iran sanctions headline. A third translation changed a place name although both originals agreed. These are locally observed snapshot contents, not claims about the underlying news being true.
2. Jev protected the numeric difference in the original-text pilot. This is not a substitute for deterministic number/unit/period checks.
3. Jev sometimes treated background/detail differences as material updates. This is conservative for suppression, but reduces duplicate removal.
4. Different CPI reporting months were classified as `material_update` instead of `unrelated`. Neither outcome merged the reports; reporting period belongs in deterministic identity checks.
5. All three authored Chinese/Japanese/Thai duplicate controls chose `duplicate` on originals. Only Chinese passed the 0.99/0.99 gate. These are one case per language, not multilingual validation.
6. The authored instruction-in-report control did not override the relationship criteria. This single example does not prove prompt-injection resistance.

## Next implementation gate

- Retain Jev as the evaluation candidate; do not adopt it for production yet.
- Prepare 200–300 original-grounded reviewed pairs with provenance/rationales, hard negatives and real headline-only cases. Freeze labels before model calls; group related developments, not merely report IDs, across tuning and validation splits.
- Add deterministic preservation checks and make original-text judgments authoritative. Existing translations can help retrieve candidates, but must not silently replace source facts.
- Evaluate duplicate recall as well as precision; a model that merges almost nothing does not solve repeated notifications.
- Generative-model comparison, canonical linking, source aggregation, API/UI and dry-run end-to-end QA remain pending.

## Reproducible local artifacts

All content/results below are git-ignored under `var/news-dedup/`:

- `pairs-20260926.jsonl`: initial 300 unlabelled candidate pairs.
- `pilot-20260926.jsonl`: initial provisional labels; retain unchanged.
- `jev-pilot-original-20260926.jsonl`: original 32 responses using v1 expected labels; join with v2 labels to rescore.
- `pilot-20260926-v2.jsonl`: corrected provisional labels and explicit authored English controls.
- `jev-pilot-english-20260926-v2.jsonl`: 32 English-mode responses using v2 labels.

Builder: `db/tools/news_dedup_pilot.py`. Runner: `normalizer_classifier.deduplication_evaluation`. Credentials were injected from the existing local OpenRouter configuration for this authorized run; no keys or raw HTTP responses were stored in artifacts.

## Subsequent guard replay (offline, no new calls)

Conservative literal-figure/unit/period blockers retained 6 of the original model's 7 merge candidates. With 19 provisional duplicate labels, guarded recall was 6/19 (31.6%), compared with raw-model recall 7/19 (36.8%). Zero observed guarded mistakes across six merges is not a quality guarantee. This guard development used the provisional pilot, so it cannot be claimed as independent validation.

A separate 250-pair UNREVIEWED packet is available locally as `var/news-dedup/review-20260926-v1.md` / `.jsonl`; it includes 30 headline-only pairs and excludes report IDs from this pilot. Human labels, event grouping and freeze remain pending. No further paid requests were made for this replay or packet.
