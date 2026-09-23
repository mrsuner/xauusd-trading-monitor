# 領域路由與動態 prompt 重構計畫

> Status: Implemented locally on `codex/news-content-routing`; production activation pending calibration and release gates.
> 第 15 節的 2026-09-07 review 取代先前衝突的提案。2026-09-10/11 implementation adopts Plan B, deterministic `top_k=2`, migration-seeded configuration and optional shared UTC daily budgets.
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

`severity` 維持單一數值，由既有的 deterministic `severity_for()` 規則依 relevance score 與 source metadata 計算。模型提供 impact channels，不提供 severity。

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

2026-09-07，使用者同意將 category/tags 從 translation 移入
classification（Plan B）。這僅是設計決策；本次討論 session 仍未授權實作。
其他提議的數值預設與運維細節不因該同意而凍結。
四個 content domains 與受控的 subscription taxonomy 遵循已同意的
[content plan](../../../docs/plans/2026-09-07-news-content-taxonomy.md)。
Consumer notification 行為屬於
[delivery plan](../../../docs/plans/2026-09-07-news-preferences-and-delivery.md)。
本服務維持 Python；Laravel Horizon 僅屬於 consumer delivery。
既有 operator notification routes 不在此變更範圍內。

### Current implementation findings

- `normalization.py` 給予 P0 30 分加權，threshold 為 25 分：
  非空 P0 items 無需關鍵字命中即可通過。P1 仍需要命中。
  移除該 P0 bypass 是刻意的行為變更，不是 parity。
- `model_client.py` 在輔助 translation call 中、relevance classification 之後產生 category/tags。Translation 可被停用或失敗。
- `worker.py` 在 classification 之後呼叫 translation，即使沒有 event 產生。
  一次 classification call 不代表每個 item 只有一次模型請求。
- `db.py` 以 `severity_for()` 推導 severity，且已更新 tag counts。
- 目前的 budget counters 存放在 worker instance 上，由 `asyncio.Lock` 保護；
  restart 或另一個 process 會取得獨立的 counters。它們不是每日全域上限。

### Plan A: deterministic routing and bounded prompt assembly

使用四個 domains：`geopolitics`、`monetary`、`energy`、`macro_data`。
預設 `top_k=2`；第三個模組延後到 labeled samples 顯示實質收益再導入。
不加入 LLM router、per-domain model fanout 或新的 routing service。

建議的初始計分，仍需樣本校準：

- 每個關鍵字有明確的 group；同 group 內的 aliases 只貢獻最大命中權重，
  每個 domain 一次。重複不會灌水分數。
- 強 entity/phrase groups 貢獻 30 分；弱 groups 貢獻 10 分。
  `rate`、`deal`、`market` 這類通用詞屬於弱觸發，不是強觸發。
- Source prior 每個 domain 為 0 或 10，明確指定。Priority 本身不是自動通過。
  每個 domain 的 threshold 初始為 30。
- 候選需要內容命中 AND score >= threshold。沒有內容命中時，source prior
  不得製造候選。
- 依分數降序排序，平手時以 domain key 升序，確保 deterministic。
  所有候選保留在 `matched_domains`；載入前兩個模組。
- 若無候選，記錄 `no_domain_match` 並跳過付費 classification。
  人工審核被拒樣本以找出詞彙缺口；不得默默引入
  no-keyword official-source bypass。
- 一致地 normalize Unicode 與大小寫。對拉丁縮寫支援 literal `word` 匹配
  （因此 `fed` 不會命中 `federalism`），對片語/非拉丁詞支援 `substring`
  匹配。V1 不提供管理員撰寫的 regex。
  既有多語關鍵字仍被保留；不做 pre-routing AI translation。

Core 包含四個 domains 的簡短描述、不變的 output rules，以及受控 taxonomy。
Detailed modules 只提供被選中的 lenses。Domain 是分析 lens，不是 category 或
impact channel 的同義詞。

`primary_domain` 對 irrelevant 結果為 null；否則必須是 `relevant_domains` 之一，
後者只包含已啟用的 domain keys。允許 router 候選之外的 relevant domain，
並記錄為 routing mismatch。
它不得觸發另一次 classification call。保留目前的 impact-channel
wire vocabulary 與 deterministic severity 規則；不得發明 `Fed` 作為新 enum。

請求前驗證 prompt 大小。先移除較低分的 domain module；
絕不默默移除 core / output schema / taxonomy。若 core 加上最高模組仍放不下，
視為 configuration validation 失敗。所選模型的 input / output token limits
必須明確；最終數字需要 model inventory。新聞文字是不可信輸入，
不得覆蓋 system instructions。

### Plan B: one authoritative taxonomy result

已接受的設計變更（2026-09-07）：將 `content_category` 與 `topic_tags` 移入既有的
classification response，並在同一請求中提供受控 taxonomy。
這使 taxonomy readiness 與可選的 translation 脫鉤。實際發送仍依 delivery contract
需要可發佈的 public 文字。

- 持久化前驗證 category、normalized tag keys 與 12-tag 上限。
  遵守 content plan 中的 category underscore normalization 修正。
- classification、category/tag 關聯、domain metadata 與任何 event
  在同一 transaction 中持久化。Consumer 可見的 event 不得出現在其 taxonomy 之前。
- Translation 之後只負責翻譯文字；連同新的 classifier writer 一起移除其 taxonomy 寫入。
  不得同時運行兩個競爭的 taxonomy writers。
- 為已分類但未成為 event 的 items 保留 category/tag 結果，
  使既有 review/browsing 行為不會失去 classification 資訊。
- 保留已審核的 subscription vocabulary 與 internal suggested-tag 行為；
  AI 輸出不得自動使新 tag 變成 subscribable。
- 翻譯失敗仍保留 classification 與 taxonomy。適用 delivery contract 的
  text fallback；不引入 per-user model call。
- 不做自動歷史重新分類或通知重放。

使用者已接受此範圍調整。翻譯失敗不得移除或覆蓋 taxonomy。這不授權發佈 private 文字
或繞過既有 public-content 審核規則。使用者也在 2026-09-07 同意了 delivery plan N8 的
severity-based language policy：S 允許立即提供替代語言摘要，A 自公共接收兩分鐘後允許，
B/C 在到期前等待請求的語言。Approved classification summaries 符合資格；其發佈
與同步路徑已存在（event-router -> public outbox -> public-api）。
審核與提議的 language-label/overwrite 修正見 delivery plan N8。

### Plan C: configuration ownership and reproducibility

保留提議的四張 configuration tables，加入 keyword group 與 literal
match mode 欄位。初始內容透過受審核的 seeds / scripts 管理。
V1 不加入 admin UI、排程 AI curation 或 live A/B 基礎設施。
受控的 database configuration 更新仍屬於運維變更；
它們不是未經 release/backup workflow 就編輯 production 的許可。

每個 claimed batch 讀取一致的 configuration snapshot。對涵蓋 keywords/groups/weights、
priors、domain settings、prompt bodies、matching version、top-K 與實際 taxonomy context
的 canonical sorted content 做 hash。以 hash 保留 immutable snapshot，
並以該 hash stamp processing attempts / events。在既有 usage records 旁記錄 model
identity 與 request parameters。這是為了解釋與重建，不是 deterministic model output 的承諾。

啟用前拒絕不完整配置。Rollout 期間保留前一個有效 configuration / code artifact；
config rollback 不會復原已儲存的 events。Rollback 期間不做自動重處理。

### Plan D: protect shared model capacity

為小型的共享每日 request counter 重用 private PostgreSQL；不為此引入
另一個 queue/cache 服務。每次實際 provider 請求前，以 conditional update 與
`RETURNING` 原子性預留。使用資料庫的 UTC calendar day。
將 classification、translation、retries 與 fallback 請求計入同一總上限，
並為 translation 設子上限以保護 classification 容量。

Reservation 採保守策略：crash 或網路結果不確定後，不退款。
若 budget store 不可用，不呼叫模型。數量上限不是金額保證：
明確的 model/token limits 與 usage reporting 同樣必需。
隱藏的 SDK retries 必須停用或計入 reservation。

Classification 額度用盡時，延後既有 processing task，不將其計為 irrelevant，
也不消耗 failure retries。Translation 額度用盡時，保留已分類的 event 並記錄
translation budget skip。UTC 日切時的恢復不得繞過 consumer delivery 的
freshness window。既有的 per-run limits 可作為輔助防護，
但不得呈現為共享上限。

建議的 sizing 程序：收集七天的 source volume 與 provider usage；
依該基線與 owner 核准的支出 envelope 設定非零的啟動上限。
不虛構 dollar budget，也不在加入 channels 時自動調高上限。

References（參考）：[Python asyncio synchronization](https://docs.python.org/3/library/asyncio-sync.html)
與 [PostgreSQL UPDATE / RETURNING](https://www.postgresql.org/docs/current/sql-update.html)。

### Acceptance and rollout

1. 建立 labeled offline set：每個 domain 至少 20 筆 relevant samples 與 40 筆
   irrelevant / ambiguous samples，涵蓋既有語言與跨領域新聞。
   保留 held-out 部分；不得只用同一批樣本調校又計分。
2. 先在不呼叫模型的情況下檢查 legacy routing parity。直接把舊關鍵字組
   seed 進四個 domains 不保證等價計分。將刻意差異（特別是移除 P0 bypass）
   與 regression 分開列出。
3. 建議的 quality gates：所有明確標記必須送達的樣本通過 routing；
   relevant-sample routing recall >=95%；category agreement >=90%。
   報告 per-domain 結果與樣本數。這些是樣本 gate，不是 production 保證。
4. 驗證每個 item 一次邏輯 classification、deterministic 平手 / group 去重、
   無效輸出處理、taxonomy 先於 event 可見、translation 失敗，
   以及多 worker / restart 的 budget enforcement。實際 retry 請求也要計入。
5. 先以既有 channels 啟用，觀察 pass rate、model requests、taxonomy
   readiness、被拒樣本與 backlog age。只有在理解此行為後才小批量擴充 channels。
   不做重複的 production LLM shadow calls。
6. 若 taxonomy ownership / schema 變更需要，code 與 config 一起回滾；
   相容性驗證前暫停新的 consumer delivery。保留原始資料與既有去重狀態；
   絕不自動重放已送達的 events。

### TODOs before implementation-ready status

- [x] 接受將 taxonomy 移入 classification（2026-09-07）。
- [x] 接受 severity-based public-text readiness policy（delivery plan N8）。
- [ ] 凍結 routing 預設值與 approved classification-summary 的發佈細節。
- 凍結 source priors、keyword groups、labels / aliases 與 labeled sample set。
- 盤點實際 models、token bounds、usage baseline 與每日 budget 值。
- 設計驗收後，在實作 tickets 中指明 migration 欄位、event / translation 寫入邊界、
  snapshot retention 與 task defer / resume 行為。


### Prerequisite update: legacy summary retirement (2026-09-07)

使用者要求在較大的 News 實作之前，先退役固定語言的 event summary 儲存。
針對提議的 `event_translations`、classifier language-row 輸出與 consumer migration，
遵循 [standalone retirement plan](../../../docs/plans/2026-09-07-legacy-event-summary-retirement.md)。
不得將 `events.summary_zh/summary_en` 擴充為新 classifier 的目標。
上述既有證據仍是對目前程式碼的描述，不是目標儲存方式。


## Direction checkpoint: routing and exhausted AI capacity (2026-09-07)

The user accepted the following behavior principles on 2026-09-07. Accepted taxonomy ownership,
summary-retirement priority and delivery policies are unchanged. This checkpoint
separates remaining decisions from numerical calibration before implementation.

| Question | Recommended behavior |
| --- | --- |
| Source priority versus content | A trusted source raises confidence/prior but does not automatically make every item relevant. Require content evidence in the configured domain rules. Removing today's P0 no-keyword bypass is an explicit behavior change that requires a labeled-sample comparison before activation. |
| Multi-domain events | Assemble at most two detailed domain lenses in one logical classification request, retaining all matched domains as metadata. No per-domain LLM fanout; input/output schema and taxonomy remain mandatory. |
| Missed topics | Keep rejected raw items under existing retention and audit representative rejected samples. Adjust centrally reviewed keywords/prompts; do not add automatic per-item LLM fallback that defeats the prefilter budget. |
| Shared budget | Enforce a shared limit across workers/restarts and count every provider request including retries/translations/fallbacks. Reserve translation sub-capacity so optional text work cannot exhaust classification capacity. Request limits and token/model constraints jointly control cost. |
| Budget exhaustion or budget-store outage | Preserve raw data and a deferred reason; do not classify budget-denied input as irrelevant. Do not silently increase spend, switch to a paid fallback outside budget, or start another worker to bypass limits. Notify the operator through an existing operational path. |
| Resumption | Resume within configured capacity and preserve new live intake capacity. Deferred historical classification is distinct from notification catch-up; expired news is never sent by bypassing accepted delivery freshness. Define bounded backlog scheduling/lookback before implementation. |
| Configuration changes | Keep rules/prompts versioned and reviewable. Adding a channel/domain does not automatically raise budget. Do not build an admin UI, automatic prompt rewriting or online A/B platform for V1. |

No exact keyword weights, monetary cap, backlog horizon or SLA is frozen by this
proposal. Recheck source cadence, languages, rejection samples, current model settings
and measured usage before implementation. The historical best-effort raw retention
window is not expanded automatically by this plan.


Routing review checkpoint: content evidence remains required even for P0; top-K=2
single logical classification, reviewed keyword changes, shared AI accounting and
budget-denied deferral are accepted. Numeric scoring, model limits and backlog
scheduling still require preimplementation calibration. No runtime changes had been made at that review checkpoint.

## 16. Local implementation record (2026-09-11)

- `0024_subscription_taxonomy` adds the accepted eight subscribable categories,
  27 subscribable tags and en/zh-Hant labels. Classification is the sole taxonomy
  writer; translation only writes language rows and status.
- `0025_domain_routing` adds the four routing tables, four seeded domains, grouped
  word/substring keywords, optional source priors and versioned prompt modules.
  Runtime routing requires content evidence, sums one maximum weight per group,
  sorts score-desc/key-asc, selects two lenses and stamps a SHA-256 configuration hash.
- `0026_ai_daily_budgets` provides atomic PostgreSQL reservations across workers and
  restarts. Total/classification/translation limits remain `0` until a measured budget
  is approved; configured store failure prevents the provider call.
- Local migration round-trips, seeded DB-context routing, atomic budget reservations
  and normalizer tests pass. Production activation still requires the labeled sample
  calibration, model/token inventory, release backup gate and the legacy-summary R5 gate.
