# Cross-source news evaluation

Status: Evaluation tooling only. Ingestion, feed, notification delivery and digests are unchanged.

First actual Jev run: [2026-09-26 pilot evidence](news-deduplication-pilot-2026-09-26.md). This pilot is provisional, not an adoption benchmark.

Plan authority: [umbrella implementation plan](../../../docs/plans/2026-09-26-news-cross-source-deduplication.md).

## Local sample

From `services/normalizer-classifier`:

```sh
uv run --group dev pytest
uv run python -m normalizer_classifier.deduplication_evaluation sample --output ../../var/news-dedup/pairs.jsonl
```

Sampling reads only the existing local `lukes-postgres` / `xauusd_public` snapshot, relative to its latest visible publication time. No DB/server is started, no production connection is used and no DB mutation is made. Generated reports remain in git-ignored `var/`; output files are exclusive-create to protect manual labels.

The initial 300 pairs are similarity-selected cross-source candidates from up to 1,200 reports in the snapshot's latest 72 hours, within a six-hour pair window. This is not a balanced benchmark. Review labels manually, add hard negatives, multilingual, headline-only, material-update and insufficient-evidence cases. Similarity is never ground truth. Candidate retrieval recall needs separate verification.

Each JSONL row has `id`, `current`, `candidate`, `expected`, `split`, and `slice`. Set `expected` to `duplicate`, `material_update`, `unrelated`, or `insufficient_evidence`; `split` to `tuning` or `held_out`. Keep both reports in the same split across pairs to prevent leakage. Do not put test labels in prompts or tune on held-out results.

The paid runner rejects unlabelled rows, missing splits, repeated/reversed report pairs and reports shared across tuning/held-out splits. Metrics are reported overall and separately by split and slice. Cost is flagged partial when any request fails because a failed/parsing-invalid call may still incur provider charges.

## Paid evaluation (explicit opt-in)

Create an ignored `.env.news-dedup.local` in the repository root with these explicit values:

```dotenv
NEWS_DEDUP_MODEL_ENDPOINT=https://openrouter.ai/api/alpha/decisions
NEWS_DEDUP_MODEL_NAME=typesafe/jev-1.13
NEWS_DEDUP_MODEL_API_KEY=
```

Fill the key privately. Never commit it or copy its value to a report. The client does not fall back to digest/translation configuration.

```sh
set -a
source ../../.env.news-dedup.local
set +a
uv run python -m normalizer_classifier.deduplication_evaluation run \
  --input ../../var/news-dedup/held-out.jsonl \
  --output ../../var/news-dedup/jev-original.jsonl \
  --allow-paid --max-pairs 300 --text-mode original \
  --probability 0.99 --confidence 0.99
```

Thresholds above are conservative evaluation inputs, not adopted production settings. Repeat with a separate output and `--text-mode english` to compare existing English translations; missing translations are recorded as errors, never silently invented. Requests are sequential, bounded and have a 15-second timeout; no automatic paid retry/cascade. Results contain actual model version, probabilities, confidence, usage/cost, latency and error class, but no credentials or raw HTTP responses.

Null precision/no merges is not acceptance. Inspect errors, label confusion and subgroup results, not just aggregate accuracy. `confidence` is not probability of correctness. Compare the configured generative model on the same pairs before adopting Jev. This comparator and reviewed labels are still pending.

Reference: [OpenRouter Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request).
