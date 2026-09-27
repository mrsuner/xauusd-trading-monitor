# Cross-source news evaluation

Status: Normalizer tools remain evaluation-only. A default-disabled lightweight notification deduplicator is now implemented for local testing. Production behavior, ingestion, feed and digests remain unchanged.

First actual Jev run: [2026-09-26 pilot evidence](news-deduplication-pilot-2026-09-26.md). This pilot is provisional, not an adoption benchmark. Subsequent [authored diagnostic round](news-deduplication-round2-2026-09-27.md) is also not production acceptance.

Plan authority: [umbrella implementation plan](../../../docs/plans/2026-09-26-news-cross-source-deduplication.md).

## Lightweight notification implementation

`services/notification/app/Services/Delivery/NotificationDeduplicator.php` runs before Telegram delivery, not during ingestion or feed selection. Enable explicitly with `NOTIFICATION_DEDUP_ENABLED`; the endpoint, API key and model have no URL/model fallback and are declared in the service `.env.example`. Production remains disabled/unmodified.

The service compares at most two recent sent deliveries for the same subscriber/channel AND channel revision, using one visible, untruncated original report associated through `public_raw_items.upstream_event_ids`. An older channel target's delivery cannot suppress the new target's first message. It requires different source names and publication timestamps within 30 minutes. Missing/ambiguous originals, source-record updates after the reference's send, figure/unit/status conflicts, uncertainty, invalid responses and operational failures all preserve normal sending. A conservative source-update veto may also skip matches after translation enrichment; missed matches are acceptable. Numeric and English status checks are lexical, not comprehensive multilingual fact extraction.

The total comparison deadline is one second, with remaining time passed to each HTTP request, no paid retry/cascade and cached pair results shared across recipients. References still require recipient-specific successful delivery, even on cache hits. Concurrent notifications may both send; no blocking global semantic lock or canonical identity schema is introduced. Confirmed duplicate deliveries use existing canceled status with `cross_source_duplicate:<reference-delivery-id>`; raw reports stay intact. Model call diagnostics record actual model/cost/latency/choice without source text, targets or credentials.

Local verification: full notification regression 79 tests / 328 assertions, all external calls faked; Pint/PHP syntax checks passed. Read-only local Postgres coverage query found 7,797 uniquely associated originals among 10,864 visible events, with 3,067 missing and zero ambiguous. This is association coverage, not deduplication quality or a replay of real notifications. No paid calls or Telegram sends occurred for this implementation step. Scanner dry-run does not invoke the delivery processor; the delivery-path tests use faked provider responses instead.

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

## Original facts and frozen acceptance inputs

`news_fact_guards` records conservative merge blockers for literal figures, known units, currencies, English thousand/million/billion/trillion scales and known months/quarters/years. Unicode decimal digits and full-width punctuation are normalized. English zero through twenty are normalized too (eight/8, two thousand/2000); this is not a general compound-number or multilingual number-word parser. Only a narrowly recognized MNA dateline wrapper is excluded; dates inside claims remain protected. Different additional background figures can block a valid match. Equal footprints do not establish identical facts; other spelled-out numbers, unknown units/periods and entity drift remain limitations. No production consumer uses these rules yet.

Metrics separate raw model merges from guarded merges and report both recall and precision. A translated-only judgment is never eligible for guarded suppression. Thresholds and guards require new frozen validation; replaying the pilot is not independent evidence.

An additional conservative English status-cue veto keeps both reports when departure/arrival/meeting or denial/confirmation/uncertainty cue sets differ. This is not semantic status extraction: quotes, background and future-tense text may over-block valid duplicates. Multilingual cues remain unsupported. It was tuned after the paired comparison exposed visit-stage conflation; offline replay is not independent validation.

Prepare a stratified packet, optionally excluding report IDs already sent to Jev:

```sh
uv run python -m normalizer_classifier.deduplication_evaluation sample \
  --strategy review --limit 250 \
  --exclude-input ../../var/news-dedup/pilot-20260926-v2.jsonl \
  --output ../../var/news-dedup/review.jsonl
uv run python -m normalizer_classifier.deduplication_dataset review \
  --input ../../var/news-dedup/review.jsonl --output ../../var/news-dedup/review.md
```

Sampling now supplements recent reports with original title-only reports and up to eight cross-source neighbours in a six-hour window. It samples across similarity ranks, not only top matches. Report-ID exclusion does not exclude previously exposed developments: reviewers must also keep those out of independent validation.

Review JSONL rows using the escaped source-text packet. Fill `expected`, `split`, `development_groups`, `reviewed_by` and `rationale`. Assign both development identities on unrelated pairs, and use the same group across paraphrases, languages and later related updates. Review metadata is a declaration, not automatic proof of human review; do not disguise assistant labels as human labels.

```sh
uv run python -m normalizer_classifier.deduplication_dataset freeze \
  --input ../../var/news-dedup/reviewed.jsonl --manifest ../../var/news-dedup/reviewed.manifest.json
uv run python -m normalizer_classifier.deduplication_dataset verify \
  --input ../../var/news-dedup/reviewed.jsonl --manifest ../../var/news-dedup/reviewed.manifest.json
```

The manifest covers exact input bytes including labels, text and metadata. Freeze requires 200–300 reviewed pairs, both splits, rationale and development groups; outputs cannot overwrite an earlier manifest. Acceptance-sized paid runs require `--manifest`; any changed file is rejected before calls. All runs, including small pilots, record the input SHA-256. Persist the original frozen artifact and use a new held-out set after prompt/guard tuning, rather than rewriting labels after results.

The `news-relationship-v2` criteria distinguish a corrected figure for the same release (`material_update`) from different reporting periods (`unrelated`). The diagnostic builder `db/tools/news_dedup_round2.py` creates 32 explicitly assistant-authored English controls; these must never be represented as human-reviewed snapshot news.

## Paid evaluation configuration

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

## Bounded diagnostic generative comparison

The comparison runner uses the same original input and relationship criteria for Jev and an explicitly configured OpenRouter chat model, with no exchange of answers or labels. It is restricted to 1–64 pairs, cannot replace the frozen acceptance workflow, and checkpoints every billable response without retries. It reserves unknown failed-call costs as well as successful calls. Supply prior campaign spend; the runner rejects batches whose reservations exceed the remaining US$5 limit. Reservations are not a provider-side billing hard cap.

```sh
uv run python -m normalizer_classifier.deduplication_comparison \
  --input ../../var/news-dedup/pilot-20260926-v2.jsonl \
  --output ../../var/news-dedup/comparison-original-new.jsonl \
  --comparator-model openai/gpt-6-luna --allow-paid \
  --spent-usd 0.033951314 --budget-usd 5
```

This uses `NEWS_DEDUP_MODEL_API_KEY`, `NEWS_DEDUP_MODEL_ENDPOINT` and `NEWS_DEDUP_MODEL_NAME` explicitly. The comparator can be injected through `NEWS_DEDUP_COMPARATOR_MODEL`, now `openai/gpt-6-luna` in the example environment; there is no hard-coded model fallback. The catalog and provider price caps restrict chat input/output prices, original source state is limited to 20,000 UTF-8 bytes without truncation, completion is capped at 1,024 tokens, and reasoning is disabled. Equal self-reported thresholds do not imply equal calibration or precision across engines. See the paired-comparison section of the [round 2 evidence](news-deduplication-round2-2026-09-27.md) for actual costs and limitations.

## Translation model diagnostics

Provider policy: explicitly use `provider.sort = "price"`, not a hard-coded provider order. Among endpoints supporting the requested structured output/reasoning parameters, try the cheaper providers first. Keep `require_parameters = true`. Release caps are US$0.03 input / US$0.17 output per million tokens, corrected from the earlier experiment's 0.15/0.60 after checking current endpoint prices. If none qualify, record a failure instead of removing price caps or changing models. Future results retain the actual provider when the response exposes it; a missing field remains unknown. Actual usage cost, not catalog floor pricing, is the spend authority. See [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

`translation_evaluation` reads three observed problematic source reports from the existing local snapshot without DB writes, freezes originals plus stored translations, and compares paid `openai/gpt-oss-20b` with `openai/gpt-oss-120b`. Four output locales are required: `zh-Hant,en,th,ja`. The stored snapshot lacks model attribution and must not be described as known 20B output. Both fresh models use identical inputs, prompts, temperature 0, low reasoning and 4,096-token output caps. Provider prices are sorted and capped; failed-call reservations count toward the same US$5 campaign budget.

```sh
uv run python -m normalizer_classifier.translation_evaluation \
  --input ../../var/news-dedup/translation-sources-new.jsonl \
  --output ../../var/news-dedup/translation-comparison-new.jsonl \
  --spent-usd 0.033951314 --allow-paid --prompt-variant explicit-locales
```

Use `--prompt-variant current` to reuse the existing worker system prompt; `explicit-locales` adds evaluation-only language/attribution/uncertainty fidelity clarification. Production prompts and model settings are unchanged. The evaluator checks unique locales, nonempty full translations, summary lengths and complete responses; lexical flags surface numbers, missing target script and the observed unsupported Iran entity. Passing these checks is not semantic translation certification. Future runs retain source-derived output text and validation locations/types for failed examples, without hidden reasoning or HTTP headers. No automated retry or backfill occurs.
