# 領域路由與動態 prompt 重構計畫

> Status: Proposed; documentation only, no implementation authorized.
> The 2026-09-07 review in section 15 supersedes conflicting earlier proposals. Taxonomy ownership in Plan B was accepted on 2026-09-07; remaining parameters still require review.
> 範圍：`normalizer-classifier` 服務的 prefilter 與分類 prompt 從「寫死、單一領域（Iran/US 衝突）」演進為「DB 可配置、領域分流」。
> 相關服務規格：[normalizer-classifier](./services/normalizer-classifier.md)、[event-router](./services/event-router.md)。

## 1. 背景與動機

現況中兩個關鍵環節是寫死的，限制了可擴展性：

- **Prefilter 關鍵字評分**（`services/normalizer-classifier/src/normalizer_classifier/normalization.py` 的 `KEYWORD_GROUPS`）高度綁定 Iran / US / Israel / Fed。它是模型呼叫之前的閘門：未命中的 item 會被 `prefilter_passed=False` 擋下，模型根本看不到。
- **分類 prompt**（`model_client.py` 的 `system_prompt()`）把 relevance channel 清單（safe_haven、real_rate、inflation、dollar、liquidity、oil、sanctions、geopolitics、Fed expectations）硬編在字串裡，且 conflict-detection 的 lens 與一般總經解讀混在同一個 prompt。

目標：

1. 讓「追蹤哪些題材」成為**資料配置**而非程式碼變更（新增 ECB / 日本央行 / 中國 PMI / 美債上限等題材時免部署）。
2. 用**領域分流的 prompt 模板**取代單一萬用 prompt，避免「一個 prompt 同時做衝突偵測與總經解讀導致兩邊都變差」。
3. 正確處理**同一頻道 / 同一則新聞橫跨多個領域**的情境。
4. 補上**治理機制**，讓 AI 生成標籤與動態配置長期可維護。

> 對照產品定位（`docs/overview.md`）：擴展題材是有意識的範圍決策。conflict-detection 不被稀釋，而是成為 `geopolitics` 領域的一個 lens；其他領域以各自的 lens 平行加入。

## 2. 核心原則：source = 軟先驗，item = 硬判定

不可採用「一個頻道 = 一個領域 = 一個 prompt」的綁定。一旦這樣綁，多領域情境立刻崩潰（例如 IRGC 頻道突然發布石油市場新聞）。

- **Source / 頻道**只提供**領域先驗（prior）**：用於 router 階段加權，首版不提供無關鍵字命中的來源 fallback（見第 15 節）。它**不得硬閘門**。
- **Item 內容**才是**領域決策（decision）**，且**允許回傳多個領域**。

因此工作流**永遠 per-item 路由，不 per-source 路由**；頻道只是「推一把」。

## 3. 多領域處理策略（已拍板：A 組裝單呼叫）

| 策略 | 成本 | 品質 | 風險 | 採用 |
|---|---|---|---|---|
| **A. 組裝單呼叫**：取分數前 K 個領域模組拼成一個 prompt，單次模型呼叫 | ~1 call | 多數情況足夠 | prompt 偏長；需 reconciliation | **採用** |
| B. Fan-out：每命中領域各一次呼叫再合併 | N× call | 每領域最精準 | 撞預算上限、需合併器、可能矛盾 | 否 |
| C. 主領域 only：只跑最高分領域，其餘當 tag | 1 call | 次領域規則不套用 | 真正雙領域事件被低估 | 否 |

採用 **A** 的關鍵好處：因為只有一次呼叫，reconciliation 大部分由模型在單次推理內完成，**不需要外部合併器**；我們只需提供候選領域並要求模型標註輸出。

## 4. 兩階段工作流（router → 組裝式分類）

```
raw_item
 → [Stage 1: Router] 規則優先，零模型成本
     DB 關鍵字組(分領域) + source_domains 先驗
     → domain_scores = {geopolitics:55, energy:40, monetary:35, ...}
     → matched = 超過各自 threshold 的領域集合，依分數排序
     → prefilter_passed = matched 非空  或  (來源 P0/P1 且有任何命中)
     → 載入模組 = matched[:K]   (K = 2~3)
 → [Stage 2: Classify] 僅通過時才呼叫模型
     prompt = core_module + Σ domain_module[d]  for d in matched[:K]
     → 單次呼叫，統一輸出 schema
     → stamp: primary_domain, matched_domains, config_version
 → events
```

### 4.1 多領域案例（驗證）

新聞：「美國對伊朗石油出口加碼制裁，布蘭特原油跳漲，市場關注 Fed 是否因通膨升溫推遲降息」

1. Router 打分：`geopolitics 55`（sanctions/iran）、`energy 40`（brent/oil）、`monetary 35`（fed/inflation/rate）。
2. 三者皆過 threshold，但 **top-K=2** → 只載入 `[geopolitics, energy]` 模組；`monetary` 仍記入 `matched_domains` metadata，**並 log「因 K 上限未載入 monetary 模組」**（不靜默截斷）。
3. 組裝 prompt = core +（geopolitics lens）+（energy lens），**單次呼叫**。
4. 輸出：`primary_domain=geopolitics`、`relevant_domains` 由模型自評、`severity` 單一值、`xauusd_impact_channel` 為聯集——全部在單次推理內完成。

## 5. Prompt 模組設計

### 5.1 core / domain 切分

**Core module（永遠載入）**

- 安全護欄：不給交易指令、不預測方向、不暗示漲跌。
- 統一輸出 schema、`claim_direction` enum、語言與摘要長度規則。
- 通用指引：「依下方啟用的領域 lens 所列 channel 判定與黃金的相關性」。

**Domain module（依命中領域動態載入）**——把原本硬編在 core 裡的 channel 清單拆進各領域：

| 領域 key | relevance channels | lens 重點 | 關鍵 actor |
|---|---|---|---|
| `geopolitics` | safe_haven, sanctions, geopolitics | power-system 衝突偵測（confirm/deny/escalate） | 國家、軍事單位、機構 |
| `monetary` | real_rate, dollar, Fed, liquidity | 政策立場轉向（鷹/鴿，不給方向建議） | 央行、官員 |
| `energy` | oil | 供給中斷、OPEC、運輸咽喉 | 產油國、OPEC |
| `macro_data` | inflation | 數據相對預期的 surprise | 統計機構 |

> 現有 `system_prompt` 的 conflict-detection 即 `geopolitics` 模組的 lens；拆出後不再污染總經類 item 的判斷。

### 5.2 組裝後骨架

```
[core_module]
This item may touch multiple domains: geopolitics, energy.
Apply each lens below and report which were actually relevant.

[domain_module: geopolitics]
[domain_module: energy]

Output unified JSON (schema in core), plus:
  primary_domain, relevant_domains[]
```

### 5.3 schema 新增欄位

在現有分類 schema（`classification_json_schema_response_format()`）基礎上新增：

- `primary_domain`：模型選定的主領域（預設取 router 最高分）。
- `relevant_domains[]`：模型自評真正相關的領域。

`severity` remains a single value computed by the existing deterministic `severity_for()` rule from relevance score and source metadata. The model supplies impact channels, not severity.

## 6. Router 設計（取代寫死的 KEYWORD_GROUPS）

```
for each enabled domain d:
    score[d] = Σ(命中 domain_keywords 的 weight) + source_prior(source, d)
matched = [d for d in domains if score[d] >= d.threshold]，排序 by score desc
prefilter_passed = matched 非空  或  (source.priority in {P0,P1} 且有任何命中)
載入模組 = matched[:K]   (K = 2~3)
```

- 維持**規則優先**、可解釋、零模型成本，符合專案「rules-first, AI-assist」原則。
- 每領域獨立 threshold → 控管各領域靈敏度與通過量（直接影響模型呼叫預算）。
- 命中超過 K：超出者記入 `matched_domains` metadata 但不載入模組，並 **log 截斷原因**。
- token 預算守門：組裝後若超過上限，丟最低分模組並記錄（沿用 `estimate_messages_tokens`）。
- 關鍵字匹配：substring（現況）＋ 可選 regex／語言別（沿用現有 fa/he 多語關鍵字需求）。

## 7. 資料模型（提案）

沿用既有 taxonomy「DB 配置 + 執行期載入」模式（參考 `db/migrations/versions/0009_taxonomy_dictionaries.py`）。

- **`domains`**：`key, label_zh, label_en, enabled, sort_order, score_threshold, is_system`
  — 領域受控詞彙。
- **`domain_keywords`**：`domain_id, term, weight, lang?, match_type(substring|regex)`
  — **取代寫死的 `KEYWORD_GROUPS`**。
- **`source_domains`**（M:N）：`source_id, domain_id, prior_weight`
  — 軟先驗關聯。
- **`prompt_modules`**：`domain_id(core 時為 null), role(core|domain), version, body, is_active`
  — **版本化**的 prompt 片段。
- **`raw_items` / `events` 加欄**：`matched_domains jsonb, primary_domain, config_version`。

### 7.1 與既有 taxonomy 的關係（不同軸，不可混）

- `content_categories` / `tags` = 「這是什麼內容」（時間軸過濾用）。
- `domains` = 「該用哪個分析 lens」（驅動 router + prompt + severity）。
- 兩者正交；必要時可建立 domain → category 的對應，但不合併。

## 8. config_version（治理必備）

`config_version = hash(canonical routing snapshot)` (including domains, keywords, source priors, thresholds, matching rules, top-K, prompt modules, and taxonomy context; see section 15)，stamp 到 item / event。

用途：prompt 變動後可重現、可 A/B、可判斷哪些舊資料需重跑。現況僅 stamp `translation_model`，未含 prompt 版本。

## 9. 治理（三層）

1. **Tag 治理**（既有缺口）：
   - Audit correction: `db.py:update_translation_result` already recomputes `usage_count` from tag associations. A blanket “always zero” repair is not justified by current code.
   - 定期 curation job：合併同義 tag、promote 高頻 AI tag 為 system、停用一次性雜訊。
2. **領域 / 關鍵字 / prompt 治理**：
   - `prompt_modules` 版本化 → 支援 A/B 與 rollback；搭配 `config_version` stamp。
   - 關鍵字跨領域碰撞：同詞屬多領域時的權重聚合規則需定義。
   - **路由準確度回授**：比對模型回傳的 `relevant_domains` 與 router 的 `matched_domains`。模型說相關但 router 漏抓 → 關鍵字缺口信號，反饋調校 `domain_keywords`。
3. **配置歸屬**：
   - 領域 / 關鍵字結構**先以 migration seed 管理**（受 code review），穩定後再升級為 admin UI（需 audit）。
   - `prompt_modules` 尤其建議初期走 code review，勿一開始開放 runtime 任意編輯。

## 10. Worker 改動（概念）

- `normalize_item` → 改呼叫 DB-driven router，不再用硬編 `keyword_matches`。
- 新增 `get_routing_context()`（domains / domain_keywords / source_domains / 當前 active prompt_modules），**每批載入一次並快取**，比照 `get_taxonomy_context` 在 `worker.py` 的載入點。
- 分類呼叫 → `build_classification_prompt(matched_domains, modules)`。
- 寫回 events 時 stamp `primary_domain / matched_domains / config_version`。

## 11. Rollout（遵守 add → write → backfill → drop migration 紀律）

1. **Phase 1（純 schema + seed，不改行為）**：建立 4 張表，將**現有 Iran/US/Israel/Fed/market 關鍵字組原樣 seed 成第一批 domain**，重現今日行為。
2. **Phase 2（切換讀取，feature flag）**：worker 改讀 DB，與硬編版本跑 parity 比對。
3. **Phase 3（擴領域）**：以 seed/config 加入 `monetary` / `energy` / `macro_data`，純資料變更、免部署。
4. **Phase 4（清除）**：移除 `KEYWORD_GROUPS` 與 core 裡的硬編 channel 清單。

## 12. 成本影響

放寬 prefilter / 新增領域 ⇒ 更多 item 通過 ⇒ 更多模型呼叫。`MAX_MODEL_CALLS_PER_RUN` 等預算上限仍適用（見 `docs/development.md` §6）。每領域 threshold 是控管通過量的主要旋鈕；新增領域時須同步重估預算。

## 13. 下游 hook（V2，本計畫不展開）

`event-router` 之後可用 `primary_domain` 作為分流門檻（不同領域不同 route 策略），先在資料模型預留 `primary_domain`，實作留待 V2。

## 14. 待決事項

- K 值（2 或 3）的最終取捨，依實測 prompt 長度與品質決定。
- `domain_keywords` 是否一開始就支援 regex，或先 substring + weight。
- curation job 的觸發方式（排程 service vs 手動 CLI）。


## 15. 2026-09-07 review: proposed first-release contract

### Status and authority

On 2026-09-07 the user accepted moving category/tags from translation into
classification (Plan B). This is a design decision only; implementation remains
unauthorized in this discussion session. Other proposed numerical defaults and
operational details are not frozen by that acceptance.
The four content domains and controlled subscription taxonomy follow the accepted
[content plan](../../../docs/plans/2026-09-07-news-content-taxonomy.md).
Consumer notification behavior belongs to the
[delivery plan](../../../docs/plans/2026-09-07-news-preferences-and-delivery.md).
This service remains Python; Laravel Horizon belongs to consumer delivery only.
Existing operator notification routes remain outside this change.

### Current implementation findings

- `normalization.py` gives P0 a 30-point bonus against a 25-point threshold:
  nonempty P0 items can pass without keyword matches. P1 still needs a match.
  Removing that P0 bypass is a deliberate behavior change, not parity.
- `model_client.py` generates category/tags in the auxiliary translation call,
  after relevance classification. Translation can be disabled or fail.
- `worker.py` calls translation after classification even when no event is created.
  One classification call does not mean one total model request per item.
- `db.py` derives severity using `severity_for()` and already updates tag counts.
- Current budget counters live on the worker instance behind `asyncio.Lock`;
  restart or another process gets separate counters. They are not a daily global cap.

### Plan A: deterministic routing and bounded prompt assembly

Use four domains: `geopolitics`, `monetary`, `energy`, `macro_data`.
Default `top_k=2`; defer three modules until labeled samples show a material gain.
Do not add an LLM router, per-domain model fanout, or a new routing service.

Proposed initial scoring, subject to sample calibration:

- Each keyword has an explicit group; aliases in the same group contribute only
  the maximum matched weight, once per domain. Repetition cannot inflate scores.
- Strong entity/phrase groups contribute 30 points; weak groups contribute 10.
  Generic words such as `rate`, `deal`, or `market` are weak, not strong triggers.
- Source prior is 0 or 10 per domain, assigned explicitly. Priority alone is not
  an automatic pass. Threshold is initially 30 for each domain.
- A candidate requires a content match AND score >= threshold. Source prior
  cannot create candidates without a content match.
- Sort by score descending, then domain key ascending for deterministic ties.
  Preserve all candidates as `matched_domains`; load the first two modules.
- If no candidates exist, record `no_domain_match` and skip paid classification.
  Audit rejected samples manually to find vocabulary gaps; do not silently
  introduce a no-keyword official-source bypass.
- Normalize Unicode and case consistently. Support literal `word` matching for
  Latin abbreviations (so `fed` does not match `federalism`) and `substring`
  matching for phrases/non-Latin terms. No administrator-authored regex in V1.
  Existing multilingual keywords remain represented; no pre-routing AI translation.

The core includes a short description of all four domains, the unchanged output
rules, and the controlled taxonomy. Detailed modules supply only the selected
lenses. Domain is an analysis lens, not a synonym for category or impact channel.

`primary_domain` is null for irrelevant results; otherwise it must be one of
`relevant_domains`, which contains only enabled domain keys. A relevant domain
outside router candidates is permitted and recorded as a routing mismatch.
It must not trigger another classification call. Preserve the current impact-channel
wire vocabulary and deterministic severity rule; do not invent `Fed` as a new enum.

Validate prompt size before requests. Remove the lower-ranked domain module first;
never remove the core/output schema/taxonomy silently. If core plus the highest
module cannot fit, fail configuration validation. Input and output token limits
must be explicit for the chosen model; final numbers require model inventory.
News text is untrusted input and cannot override the system instructions.

### Plan B: one authoritative taxonomy result

Accepted design change (2026-09-07): move `content_category` and `topic_tags` into the existing
classification response, supplying the controlled taxonomy in the same request.
This makes taxonomy readiness independent of optional translation. Actual sending
still requires publishable public text under the delivery contract.

- Validate category, normalized tag keys, and the 12-tag limit before persisting.
  Respect the category underscore normalization fix in the content plan.
- Persist classification, category/tag associations, domain metadata, and any event
  in one transaction. A consumer-visible event must not appear before its taxonomy.
- Translation then owns translated text only; remove its taxonomy writes together
  with the new classifier writer. Do not run two competing taxonomy writers.
- Keep category/tag results for classified items that do not become events, so
  existing review/browsing behavior does not lose classification information.
- Preserve reviewed subscription vocabulary and internal suggested-tag behavior;
  AI output must never automatically make a new tag subscribable.
- A failed translation retains classification and taxonomy. The delivery contract's
  text fallback applies; no per-user model call is introduced.
- No automatic historical reclassification or notification replay.

The user accepted this scope adjustment. Translation failure must not remove or
overwrite taxonomy. This does not authorize publishing private text or bypassing
existing public-content approval rules. The user also accepted the severity-based language policy in delivery plan N8
on 2026-09-07: S allows immediate alternative-language summaries, A allows them
after two minutes from public receipt, and B/C wait for the requested language
until expiry. Approved classification summaries are eligible; their publication
and synchronization path already exists (event-router -> public outbox -> public-api).
The audit and proposed language-label/overwrite corrections are in delivery plan N8.

### Plan C: configuration ownership and reproducibility

Keep the proposed four configuration tables, adding keyword group and literal
match mode fields. Manage their initial contents through reviewed seeds/scripts.
Do not add an admin UI, scheduled AI curation, or live A/B infrastructure in V1.
Controlled database configuration updates remain operational changes; they are
not permission to edit production without the release/backup workflow.

Read a consistent configuration snapshot per claimed batch. Hash canonical sorted
content covering keywords/groups/weights, priors, domain settings, prompt bodies,
matching version, top-K, and the actual taxonomy context. Retain the immutable
snapshot by hash and stamp processing attempts/events with that hash. Record model
identity and request parameters alongside existing usage records. This supports
explanation and reconstruction, not a promise of deterministic model output.

Reject incomplete configurations before activation. During rollout, keep the prior
valid configuration/code artifact available; config rollback does not undo stored
events. No automatic reprocessing during rollback.

### Plan D: protect shared model capacity

Reuse private PostgreSQL for a small shared daily request counter; do not introduce
another queue/cache service for this purpose. Reserve atomically before each actual
provider request using a conditional update and `RETURNING`. Use the database's UTC
calendar day. Count classification, translation, retries, and fallback requests
against one total cap, with a translation sub-cap to protect classification capacity.

Reservations are conservative: after a crash or uncertain network outcome, do not
refund them. If the budget store is unavailable, do not call the model. A count cap
is not a dollar guarantee: explicit model/token limits and usage reporting are also
required. Hidden SDK retries must be disabled or included in reservations.

On classification exhaustion, defer the existing processing task without counting
it as irrelevant or burning failure retries. On translation exhaustion, retain the
classified event and record a translation budget skip. Resumption at UTC rollover
must not bypass the consumer delivery freshness window. Existing per-run limits may
remain supplementary guards, but cannot be presented as the shared cap.

Proposed sizing procedure: collect seven days of source volume and provider usage;
set a nonzero launch cap from that baseline and an owner-approved spend envelope.
Do not invent a dollar budget or automatically raise caps when channels are added.

References: [Python asyncio synchronization](https://docs.python.org/3/library/asyncio-sync.html)
and [PostgreSQL UPDATE / RETURNING](https://www.postgresql.org/docs/current/sql-update.html).

### Acceptance and rollout

1. Build a labeled offline set: at least 20 relevant samples per domain and 40
   irrelevant/ambiguous samples, covering existing languages and cross-domain news.
   Reserve a held-out portion; do not tune and score only on the same examples.
2. First check legacy routing parity without model calls. Seeding old keyword groups
   directly into four domains does not guarantee equivalent scoring. List deliberate
   differences, especially removal of the P0 bypass, separately from regressions.
3. Proposed quality gates: all explicitly labeled must-deliver samples pass routing;
   relevant-sample routing recall >=95%; category agreement >=90%. Report per-domain
   results and sample counts. These are sample gates, not production guarantees.
4. Verify one logical classification per item, deterministic ties/group deduplication,
   invalid output handling, taxonomy-before-event visibility, translation failure,
   and multiple-worker/restart budget enforcement. Count actual retry requests too.
5. Activate with existing channels first, inspect pass rate, model requests, taxonomy
   readiness, rejection samples, and backlog age. Expand channels in small batches
   only after this behavior is understood. No duplicate production LLM shadow calls.
6. Roll back code/config together if taxonomy ownership/schema changes require it;
   pause new consumer delivery until compatibility is verified. Retain raw data and
   existing deduplication state; never replay already delivered events automatically.

### TODOs before implementation-ready status

- [x] Accept moving taxonomy into classification (2026-09-07).
- [x] Accept severity-based public-text readiness policy (delivery plan N8).
- [ ] Freeze routing defaults and approved classification-summary publication details.
- Freeze source priors, keyword groups, labels/aliases, and the labeled sample set.
- Inventory actual models, token bounds, usage baseline, and daily budget values.
- Specify migration columns, event/translation write boundaries, snapshot retention,
  and task defer/resume behavior in implementation tickets after design acceptance.


### Prerequisite update: legacy summary retirement (2026-09-07)

The user requested retiring fixed-language event summary storage before larger News
implementation. Follow [standalone retirement plan](../../../docs/plans/2026-09-07-legacy-event-summary-retirement.md)
for proposed `event_translations`, classifier language-row output and consumer migration.
Do not extend `events.summary_zh/summary_en` as the target of the new classifier.
The existing evidence above remains a description of current code, not desired storage.
