# News deduplication diagnostic round 2

Date: 2026-09-27. Local evaluation only; production ingestion, feed, delivery and digests are unchanged.

## Method

- Generated 32 assistant-authored English controls using `db/tools/news_dedup_round2.py`, not real snapshot reports or human-reviewed acceptance data.
- Eight scenarios each cover four fictional actors: paraphrase, literal/word count equivalence, revised figures, official denial, different reporting periods, shared-actor unrelated stories and two insufficient-evidence cases.
- Actor-disjoint tuning/held-out groups contain 16 pairs each, but repeat templates. This split does not provide independent real-news validation.
- Input SHA-256 was recorded before calls: `6a3f9fec36c5edf0630f54a220250db66ac46c295237a13e45de6d1a8b875747`.
- Used original mode, `news-relationship-v2`, probability/confidence thresholds 0.95 selected before this run from prior pilot diagnostics. No post-result tuning or relabelling.
- Requested `typesafe/jev-1.13`; actual returned model `typesafe/jev-1.13-20260917`. All 32 paid calls used OpenRouter; no local model or alternative translation model was invoked.

## Results

- 32/32 expected relationship labels; zero request errors.
- Raw and guarded decisions merged all eight authored duplicates and no other pairs. Observed precision/recall 100% on these controls only.
- Zero of eight material updates suppressed. Both 16-pair splits passed all labels.
- Recorded cost US$0.000837648; median latency 342.195 ms.
- Automated service regression: `uv run --group dev pytest -q --disable-warnings`, 80 tests passed.

Artifacts remain local and git-ignored under `var/news-dedup/`: `round2-authored-20260927.jsonl` and `jev-round2-authored-20260927.jsonl`. The builder is versioned for reproducibility. Prior pilot outputs remain untouched.

## Changes and limits

Small English number words now normalize to literals in factual guards. Criteria now distinguish corrected figures within a release from separate reporting periods. Every evaluation result records the input hash; acceptance-sized calls still require a verified frozen manifest. Metrics explicitly count guarded material updates suppressed.

These simple English controls do not establish real-world precision, multilingual performance, candidate retrieval recall or readiness for automatic suppression. The 250-pair real-data packet still requires human review, development-level separation and freezing before acceptance evaluation. The configured generative-model comparison remains pending.

Translation fidelity follow-up was captured in Kanboard TickBase project 44, task 4098, Ready: compare the observed original/translation factual discrepancies against alternative cloud models under identical fidelity prompts. Its note preserves examples involving 168/198, ICC/Iran and a place-name alias requiring verification. No replacement translation, backfill or deployment has been authorized by this capture.

## Subsequent paired comparison (same day)

User authorized continued model evaluation without repeated cost approval while the campaign stays below US$5. The runner reserved US$0.05 for each call, including failures, with a preflight ceiling of US$3.202670780 including prior recorded spend. Reservations are conservative planning controls, not an account-level provider billing hard cap. It checkpoints responses, does not retry, bounds source bytes and output tokens, verifies comparator catalog pricing, and caps provider prices. Production authorization is unchanged.

Compared Jev against `openai/gpt-5.4-mini`, corresponding to the configured normalizer cloud model `gpt-5.4-mini`, through OpenRouter with reasoning disabled. Both received identical original text and relationship criteria; neither received expected labels or the other's answer. Input was the previous provisional 32-pair pilot (20 snapshot pairs plus 12 authored controls), SHA-256 `f4d3f78d1110f10687c322d0911930b65023b9dfdfc807035b7d8a8856293d83`. This is reused diagnostic data, NOT held-out acceptance despite legacy split names. The 250-pair review packet was not sent to models or relabelled.

64 calls completed without request errors. At probability/confidence thresholds 0.95, before new status-cue tuning:

| Model | Guarded merges | Provisional duplicate recall | Material updates suppressed | Recorded cost | Median latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jev | 10 (all provisionally correct) | 10/19, 52.6% | 0 | US$0.000931686 | 341.105 ms |
| GPT-5.4 mini | 14 (one provisionally wrong) | 13/19, 68.4% | 1 | US$0.025422000 | 1501.585 ms |

Relationship choices agreed on 29/32 pairs. On the 20 snapshot-only cases, Jev guarded recall was 7/15; GPT guarded recall was 10/15, with the additional wrong merge. Self-reported confidence is not calibrated across models, so applying identical thresholds does not equate their risk. Recorded campaign total: 160 calls, US$0.029024466. Artifact: `var/news-dedup/comparison-original-20260927-v1.jsonl`; original results remain unchanged.

The wrong high-confidence merge paired report `27352342-d4ab-4170-8c2a-7bbac69fc779` (ministers have met) with `0b0e0f32-1337-488e-ac69-004248a67491` (arrival for talks). A second pair contrasts arrival with departure. These are event-progress ambiguities, NOT a failed official-denial control: both models passed the authored denial case. Human judgment of milestone granularity is still needed; do not rewrite pilot labels to improve scores.

Added an evaluation-only original English status-cue veto for differing departure/arrival/meeting, denial/confirmation/uncertainty cues. This is lexical, not semantic fact extraction. Quotes, background facts and future-tense wording may over-block; multilingual status cues remain unsupported. Matching cues never prove the same event.

Offline replay after this tuning keeps Jev's 10 merges and reduces GPT's guarded merges to 13, blocking the observed stage-change error; guarded material updates suppressed become zero for both. This is tuning on the observed failure, NOT fresh validation. No extra paid calls or result-file rewriting occurred. Service regression now passes 93 tests. Independent reviewed data and candidate-retrieval evaluation remain prerequisites; neither model has been adopted for production suppression.

Sources checked for implementation: [OpenAI GPT-5.4 mini parameters](https://developers.openai.com/api/docs/models/gpt-5.4-mini) and [OpenRouter model catalog](https://openrouter.ai/api/v1/models). Actual usage costs above come from API responses, not list-price estimates.

## Requested Luna and OSS-120B trials

User requested GPT-6 Luna instead of GPT-5.4 mini for further deduplication comparisons, and an OSS-120B translation trial against OSS-20B. Exact OpenRouter IDs were verified: `openai/gpt-6-luna`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`. The example evaluation environment now injects `NEWS_DEDUP_COMPARATOR_MODEL=openai/gpt-6-luna`; there is no comparator model fallback. Historical GPT-5.4 results remain unchanged. Normalizer production classification/translation settings were NOT migrated.

### Deduplication

Completed another 64 calls, reusing the same 32 original pilot pairs and criteria with reasoning disabled and thresholds 0.95. Current status-cue guards were in place before this run. Zero request errors.

| Engine | Relationship accuracy against provisional labels | Guarded duplicate merges / expected duplicates | Guarded material updates suppressed | Recorded cost | Median latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jev | 31/32 | 10/19 | 0 | US$0.000931686 | 335.01 ms |
| GPT-6 Luna | 27/32 | 12/19 | 0 | US$0.002898500 | 1373.29 ms |

Luna's unguarded high-confidence answer still merges departure with arrival; the original status-cue veto prevents suppression. Lower cost does not establish equal or better model quality. This is reused diagnostic data with assistant-provisional labels, NOT independent acceptance. Artifact: `var/news-dedup/comparison-luna-original-20260927-v1.jsonl`. The real 250-pair review set remains untouched.

### Translation

Frozen the three observed source reports and their stored four-locale outputs. Source packet SHA-256: `49a23934adb6217d9fc432a79540d85929e39cba5239aa580ba6ac2811769d36`. The public snapshot has no model provenance column; its existing bad translations cannot be conclusively attributed to OSS-20B.

Ran fresh paid OSS-20B and OSS-120B on identical source/prompt/parameters for each case, temperature 0, low reasoning, output capped at 4,096 tokens. Four locales: Traditional Chinese, English, Thai, Japanese. First reused the current worker system prompt; second added evaluation-only instructions for each full translation's language, source-only numbers, complete source text, attribution, uncertainty and near/in distinctions. Worker code/prompts were not changed.

| Prompt | Model | Structurally valid cases | Full-translation fields missing target script | Recorded cost | Median latency |
| --- | --- | ---: | ---: | ---: | ---: |
| Current | OSS-20B | 3/3 | 4/12 | US$0.000157068 | 5815.17 ms |
| Current | OSS-120B | 3/3 | 6/12 | US$0.000394070 | 14373.22 ms |
| Explicit locales | OSS-20B | 1/3 | 0/4 evaluable fields | US$0.000164484 | 7501.79 ms |
| Explicit locales | OSS-120B | 3/3 | 0/12 | US$0.000381040 | 16353.97 ms |

Script checks only flag entirely missing target script; they do not distinguish Traditional/Simplified Chinese or certify naturalness. The two failed 20B responses were `ValidationError`, not HTTP failures; their returned usage was retained. These early rows did not preserve failed response content, so the exact invalid field/JSON cause is unknown. Future runs now retain source-derived output text and validation locations/types, without hidden reasoning or credentials. No failed calls were automatically retried.

Assistant source-grounded review, NOT native-speaker certification:

- Both models' fresh outputs preserved 168, unlike the stored 198; the existing numerical error was not reproduced.
- Both models removed the unsupported Iran entity from the Persian ICC story. OSS-20B collapsed full translation into a shortened summary and dropped U.S.-official attribution and Hague; OSS-120B preserved more source structure/attribution but STILL dropped Hague even with explicit locale instructions.
- Current-prompt English-source cases produced English full text under Thai/Japanese for both models; OSS-120B also did so for Chinese. Bigger-model replacement alone did not solve language leakage.
- With explicit locale instructions, OSS-120B supplied four actual target-language full translations, and preserved reportedly/near-Halamish across the shooting story's summaries and full text. It did not silently substitute Neve Tzuf. An alias might be legitimate but near/in and certainty changes are separate concerns.
- Remaining review glossary: Minab (keep a consistent transliteration or source Latin spelling); International Criminal Court / 國際刑事法院 / ศาลอาญาระหว่างประเทศ / 国際刑事裁判所. The 120B Chinese Minab rendering varies, and Thai uses a less standard ICC term (`ศาลอาชญากรรมระหว่างประเทศ`). These issues and the omitted Hague prevent unconditional adoption.

Artifacts: `var/news-dedup/translation-sources-20260927-v{1,2}.jsonl` and `translation-oss-ab-20260927-v{1,2}.jsonl`. Twelve translation calls cost US$0.001096662. Across the campaign: 236 completed calls, recorded US$0.033951314, below the authorized US$5 limit. No DB write, translation backfill, production deployment or notification delivery. Service regression: 101 tests passed.

Conclusion: use Luna for subsequent bounded comparator trials as requested. OSS-120B plus explicit locale prompting is a promising translation candidate, but switching models alone is insufficient. Next translation work should address complete-source coverage, proper-name/ICC terminology and invalid/wrong-language output rejection before rollout; neither lexical flags nor this three-case trial replaces wider multilingual/native review.

Official parameter references: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [gpt-oss-120b](https://developers.openai.com/api/docs/models/gpt-oss-120b); provider availability/pricing checked against the [OpenRouter catalog](https://openrouter.ai/api/v1/models).

## Local worker integration and QA continuation

Continuation result: notification replay completed with 20 actual snapshot-original pairs plus recorded Jev responses in `services/notification/tests/Fixtures/news-dedup-snapshot-replay.json`. The full delivery processor canceled 2 duplicates and fake-sent 18 messages; deterministic eligibility/fact checks meant only 4 recorded model answers were used. No provisional update/unrelated example was suppressed. All transport is faked and ledger state is synthetic SQLite; this is not a live PostgreSQL/Telegram/model test or held-out quality evidence. Full notification suite: 80 tests / 467 assertions, replay test 139 assertions. No new model charge. Existing original/source references stay unchanged and are not appended to translations. Rollout preparation is recorded in the umbrella plan; HomeLab Tailscale SSH timed out, so runtime/backup preflight remains blocked. VPS public services are healthy; no deployment occurred.

Implemented translation-only OpenRouter price routing (`sort: price`, compatible parameters, max input US$0.15 / output US$0.60 per million tokens), explicit per-locale fidelity instructions and ICC glossary. Existing production model defaults are unchanged. The ignored local trial profile is `infra/.env.news-optimization.local`; it contains no key, selects OSS-120B / four locales / low reasoning / no model fallback, and must not be deployed. Translation API base URL is explicit. Output validation rejects duplicate locales, overlong summaries, missing required text, obvious English copies in Chinese/Thai/Japanese, explicit truncation/refusal and reasoning-only responses. Script presence does NOT certify target-language dominance, Traditional Chinese, numeric fidelity or semantic completeness.

The evaluator's new `--worker-client` mode calls the actual `build_translation_model_clients` / `summarize_and_translate` path, not a separately constructed API request. It caps diagnostic output at 4,096 tokens and original serialized input at 20,000 bytes; it does not impose that output ceiling on production long-document translation. Source metadata absent from the public snapshot is explicitly neutral diagnostic metadata, not reconstructed production configuration. No worker loop or DB writer runs. Invalid runtime responses retain public output/usage for review, without keys or hidden reasoning.

Two batches, three source records each:

| Batch | Valid structures | Provider | Cost |
| --- | ---: | --- | ---: |
| Worker prompt v1 | 3/3 | AkashML | US$0.000360620 |
| Worker prompt v2 | 3/3 | AkashML | US$0.000413090 |

All twelve full-translation fields in each batch include the target script. Both preserve 168 and remove the unsupported Iran entity in the ICC story; Thai/Japanese ICC terminology follows the supplied glossary. V1 still drops shooting-story uncertainty in Chinese and Thai. V2 restores uncertainty in full translations and keeps near-Halamish; however its English summary says “A reported Israeli settler”, an awkward scope of reportedly, and Japanese summaries mechanically prefix `と報じられたところによると`. Both batches STILL omit Hague and Chinese Minab transliteration varies. These are targeted diagnostics on reused problematic cases, not held-out/native-speaker acceptance. No additional model tuning or semantic acceptance is claimed.

Artifacts: `var/news-dedup/translation-sources-worker-20260927-v{1,2}.jsonl` and `translation-worker-20260927-v{1,2}.jsonl`; source SHA256 remains `49a23934adb6217d9fc432a79540d85929e39cba5239aa580ba6ac2811769d36`. New spend US$0.000773710; campaign 242 calls / US$0.034725024, below the authorized US$5 ceiling.

Local automated checks: normalizer 113 tests passed; notification 79 tests / 328 assertions passed; web 7 tests and TypeScript typecheck passed; `make qa-news` passed endpoint readiness. Browser QA initially found stale Vite dependency URLs serving the SPA HTML rather than JavaScript. Restarting only the web pane with `npm run dev -- --force` restored rendering; no code workaround or database restart was needed. Chrome feed in all four locales and Chinese event-detail/source UI use unchanged stored snapshot translations, not these new outputs. iOS GUI initially appeared unavailable under Simulator.app; `Device Hub` (`com.apple.dt.Devices`) provides the simulator here. On iPhone 17 Pro / iOS 26.5, guest UI-language switching English/Thai/Japanese/Chinese passed, as did latest-feed and event-detail/source rendering. Original English UI / Chinese content / high-impact preferences were restored. Minimized native tabs expand after dragging back toward the top. These are baseline smoke checks, not authenticated digest/sync or new-output persistence/display E2E. Notification real-data delivery replay remains pending. Pause at semantic translation acceptance discussion rather than tuning indefinitely on the same three exposed examples. No production mutation, stored translation backfill, Telegram sends or commit.
