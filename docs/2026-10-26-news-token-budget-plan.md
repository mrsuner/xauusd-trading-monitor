# News 長文分流與 token 預算

## 狀態與授權

- 2026-10-26，Asia/Bangkok；使用者授權先訂計畫／驗收，再推進本地實作，暫不部署。
- 本地 P0–P3 已完成；未推送、未部署，沒有真實 Cloud 呼叫。HomeLab 仍為 `abc6107`。
- 沿用 `develop`，各階段獨立提交並回寫進度；不推送、不呼叫真實模型、不變更私有 env 或 HomeLab／VPS／公開網站 runtime。
- 前置：provider 拆分／HomeLab `abc6107` 已部署；R2 script 修正 `fc4a423` 僅本地。本文為後續長文工作權威；前案見 [provider 實作計畫](2026-10-21-news-model-providers-implementation-plan.md)。

## 已確認的資料與契約

近 30 天 16,751 則資料：Telegram 14,770，RSS 1,935，HTML polling 46。國務院 RSS 101 則的 P95 為 24,457 字元；已完成分類的 32 則中，12 則超過估算 2,500 source tokens。HTML polling 是列表標題，其餘多數 RSS 是短摘要，不能宣稱網站全文分布已完整校準。

source tokens 固定用既有 `o200k_base` 相容估算；不是 GLM 原生 tokenizer，不是精確帳單。分流使用完整 normalized source，先於既有字元截短與 Layer 2；來源類型、優先級、`always_full_translate` 都不得繞過上限。

| 完整 source tokens | 行為 |
| --- | --- |
| ≤ 2,500 | 若來源要求 full，允許四語摘要＋全文；來源 summary_only 保持摘要模式 |
| 2,501–8,000 | Layer 2 正常分類；Layer 1 僅四語摘要，所有 full_translation 必須為 null |
| > 8,000 | 兩層都不呼叫模型，保留原文，分類與翻譯 skipped，記錄 source_token_limit_exceeded |

來源 disabled 繼續不翻譯。已有字元上限仍是額外限制；若不能容納完整輸入，不再靜默截短後當成整篇完成，而以明確原因略過翻譯。估算失敗採 fail closed，不降級成無限制呼叫。

## 預算與狀態的具體方案

1. 每次 HTTP 前估算完整最終 payload（含 system prompt、JSON schema、來源資訊、修正回饋），預留 `ceil(estimate × 1.25) + 256` 輸入 tokens；單次最大 16,000，不能只估正文。此餘量是保守估算，不能保證等同 provider 原生 token 數。
2. 每次 request 明確帶 output 上限：分類 2,048；全文翻譯 10,000；摘要 1,500。沿用 provider 自有 client 傳遞其支援參數；官方參考：[Ollama compatibility](https://docs.ollama.com/api/openai-compatibility)、[OpenRouter parameters](https://openrouter.ai/docs/api_reference/parameters)。`finish_reason=length`／refusal／無效 JSON 不視為成功。摘要模式若模型仍回全文，驗證拒絕，不刪掉後假裝成功。
3. 跨兩層、fallback、R2 修正及分類重排程，同一 raw item 的終身預留上限為 30,000；跨 replicas 每日 UTC 共用預留上限初值 5,000,000。均為正值配置，不以 0 表示無限。這是 token 預留上限，不是美元封頂；每日值可在未來依量測與使用者預算調整。
4. 使用既有 PostgreSQL，新增每則預算表並延伸 daily budget 表。以固定 daily→item 鎖順序在同一 transaction 檢查與遞增；跨 worker 不可超額。預留量為保守輸入＋本次 output 上限；不因短輸出、timeout、解析失敗或程序 crash 退額，避免不確定用量重複花費。保留既有 request-count／per-run 預算，額外失敗不得繞過它們。
5. 每次修正／fallback 都重新預留；額度不足不送出，R2 仍至多一次額外 script 修正。DB 預算不可用時不呼叫模型。分類前的 daily 額度不足延後；輸入／單則額度不足明確略過。分類已提交後的翻譯阻擋不重播分類。
6. 新增 `summary_only` 狀態至 private raw item／translation 與 public translation 契約。此狀態表示摘要已完成、全文未翻譯；full_translation 永遠 null，不能寫 completed／completed_truncated。DB 聚合、public-syncer 選取／payload、public-api 驗證／儲存與 dashboard 篩選同步接受，避免摘要消失或被誤認為全文。既有 completed 歷史不回填，原文保持。
7. 本輪只修改公用 env 樣板與 Compose wiring，不覆蓋私有 env。新增 private／public migration 僅本地驗證；未來 rollout 需先讓 public-api 接受狀態，再讓 HomeLab 發送，另走備份／還原 gate。本輪不執行 rollout。

## 分階段實作與驗收

| 階段 | 產物與獨立提交 | 驗收標準 | 進度 |
| --- | --- | --- | --- |
| P0 | 本計畫；`docs: plan source token routing and bounded model budgets` | 明列門檻、預算、狀態、失敗處置、邊界案例及部署範圍 | 完成，`0ad897d` |
| P1 | Token 設定、request output/input guard、持久化原子預留與 migration；`feat: bound news model requests with shared token reservations` | 完整 payload／schema／repair 計入；超限或估算／DB 失敗零 HTTP；兩 provider 有 output cap；多連線競爭與同 item 跨日仍不超限。Source 分流邊界隨 P2 驗收 | 完成：針對性 132／完整服務 306 tests；PG16.14 競爭與 migration 驗證通過 |
| P2 | Worker 分流、R2 budget 整合、summary_only 狀態與同步相容；`feat: preserve summary-only news without claiming full translation` | 超 8,000 兩層零呼叫；來源 full／summary_only／disabled 與 always_full 組合；摘要 null 全文；分類先提交，修正／fallback 額度不足不多送；狀態聚合、公開 payload／驗證一致 | 完成：normalizer 338／syncer 37／public-api 48 tests；dashboard typecheck、private／public 新 migration 驗證通過 |
| P3 | 設定 wiring、服務說明、完整回歸與本地 DB 驗證紀錄；`test: verify news token budget and summary-only contracts` | normalizer／syncer／public-api 相關測試、dashboard typecheck、公用 env→Compose→factory、全新及既有 DB migration upgrade/downgrade、真實 PostgreSQL 競爭預留；git diff 檢查；測試資源清除 | 完成：normalizer 339／syncer 37／public-api 48 passed；4 項既有 opt-in 測試 skipped；PG roundtrip／跨服務狀態保存與 typecheck 通過 |

必要失敗案例包含：tokenizer 不可用、payload metadata 過大、output 到頂、摘要模式意外全文、第一次 script 失敗與第二次額度不足、連續修正失敗、401／timeout 不新增 script 重試、預算預留後 crash 不退額、儲存失敗不 fallback、不重播已提交分類。全部 API 呼叫 mock；migration／鎖競爭使用無 production 資料的可丟棄 PostgreSQL 16.14，不連 HomeLab DB。

## 實作紀錄

- P0：計畫已整理並獨立提交 `0ad897d`。
- P1：新增 `token_budget.py`、正值 Settings、兩 provider 的最終 payload input guard／output cap，以及 `0027_ai_token_budgets` 與原子預留。完整 normalizer suite 306 passed（1.68 s），其中 token／provider 針對性 132 passed。預算 guard 尚未接入 worker，該整合屬 P2，不宣稱現階段 production 已受保護。
- P1：以 `services/normalizer-classifier/.venv/bin/python db/tools/verify_news_token_budgets.py` 啟動僅綁 localhost 隨機 port、tmpfs、無 production 資料的 PostgreSQL16.14；10 個並行預留在 daily=30／每次10 時僅3個成功，在 item=25／每次10 時僅2個成功，拒絕不扣另一預算。新 client 與 daily reset 不會重設 item 額度，既有 request-count 預算仍有效。Private fresh upgrade／downgrade至0026／upgrade、public fresh upgrade 通過；驗證 container 已移除。未連線 HomeLab 或呼叫模型。
- P2：接入兩層完整 payload 預留，source 2,500／8,000 分流與舊 char cap 明確略過；新增 private `0028_summary_only_status`、public `0010_summary_only_status`，聚合／syncer／API／dashboard 不把摘要當全文。正常來源 summary_only 不會因 always_full_translate 升級為 full。完整 normalizer 338 passed、syncer 37 passed、public-api 48 passed／4 個既有 opt-in content DB tests skipped；dashboard `npm run typecheck` 通過。PG verifier 隨新增 migration 再跑通過；P3 補上有摘要資料的 DB roundtrip／契約驗證。P1 commit=`02003c1`。
- P3：P2 commit=`974f743`。三份公用 env 樣板與 normalizer Compose wiring 完成，離線 Compose render→Settings→兩 provider factory 驗證新門檻及 input／output／item／daily 配置。固定 `o200k_base`，避免 provider tokenizer 名稱識別變動悄悄改變分流基準；tokenizer 故障在完整 worker loop 下亦為零 HTTP。
- P3：最終 normalizer suite 339 passed（含原 provider／R2 回歸），syncer 37 passed，public-api 48 passed／4 skipped；skipped 為既有 content lifecycle 的 opt-in DB 測試，不是本次驗收。Dashboard `npm run typecheck`、AST parse、`git diff --check` 通過。公用範本均以測試用 key 與 DB URL render，未讀取或覆蓋私有 env。
- P3：PG16.14 verifier 另走實際 `update_translation_result`／SQL 聚合、syncer SQL選取／payload、public-api request 驗證與 repository ingest，四語均保存為 summary_only、全文 null、原文保持。Private 與 public DB 都拒絕 summary_only 寫入全文；帶摘要資料 downgrade 後改為 skipped 並保留摘要，再 upgrade 不會假造 completed。完整 DB 路徑不使用 production 資料；container／tmpfs 已刪除，沒有留下測試服務。
- P3：原工作目錄既有 public-syncer DB／測試修改逐 patch 比對保留，提交只包含本階段 status 篩選變更；其他 public-web／public-api／infra 的既有修改未納入。本地分支原有 ahead／behind 分歧不在本次發布範圍，未推送或合併 main。

## 限制與後續

- 本地驗收不保證 provider 實際 token 計數等於估算，也未證明指定 Cloud 模型在所有情況遵守 output cap；部署前需另授權有界 live 驗證／usage 校準。沒有宣稱美元硬封頂或長文摘要品質認證。
- 5,000,000／日是保守「預留量」初值，未用實際低用量退額；高流量下可能提早停用當日模型處理。該行為是成本保護，不自動加額或繞過。單則額度耗盡不自動跨日重置；原文仍留存，可在後續明確決策後人工處理。
- 網站列表／RSS 摘要沒有因此變成網站全文，本輪不新增正文擷取、分段翻譯、全文按需執行器或新 provider。現有 60 秒 timeout 保持，未自動重試 timeout。
- 未來部署需有 fresh backup／restore gate、private migration、public-api 契約相容順序，以及 scoped image／runtime 驗收；本輪只完成本地實作。
