# News 雲端模型 provider 拆分與 Ollama Cloud 整合

## Status

- 狀態：In progress
- 建立日期：2026-10-21；時區：Asia/Bangkok。
- 授權：使用者已要求依本文件推進本地實作，各階段獨立提交並回寫進度。
- 所屬 repo：`xauusd-trading-monitor`，直接使用 `develop`；不納入 checkout 中既有、與本工作無關的修改。
- 範圍：News normalizer-classifier 的 Layer 1／Layer 2；保留 OpenRouter，新增直接呼叫 Ollama Cloud 的獨立 client，退役早期 local LLM route。
- 完成定義：下列本地程式、設定、文件與 mock 驗收全部通過。真實雲端模型品質／延遲驗證、production 啟用、發布與部署不在本次範圍；不得將 mock 驗收寫成真實服務驗證。

## 決策與目前實作

- Worker 先完成 Layer 2 classification／event，再執行 best-effort Layer 1 translation-summary；保持此順序及資料契約。
- 現有 `OpenAIStyleModelClient` 混合任務 prompt、provider 參數、HTTP、解析、驗證與 usage。
- `local_8b`／`LOCAL_MODEL_*` 是早期探索，可移除；不保留本機推論實作、fallback 或相容 client。
- OpenRouter 與 Ollama Cloud 各有獨立實作類別，以小型 `ModelClient` Protocol 對接 worker；不使用共同 provider 父類別，也不建立 registry／plugin framework。
- 共用新聞 prompt、輸入組裝、schema、業務驗證、結果／錯誤／usage 契約，以及無 provider 判斷的 HTTP／log 工具。各 client 自行客製化 payload、headers、response 解析與能力限制。
- 所有 API attempt 由 worker 的現有預算與 fallback 流程掌握；client 單次操作只呼叫一次 HTTP，不隱藏重試、切換 provider 或 JSON 修復。

## 外部契約與限制（2026-10-21 查核）

- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)：直接使用 `https://ollama.com/v1` 與 Bearer API key，不經本機 Ollama。
- [Ollama Cloud](https://docs.ollama.com/cloud)：model 名稱使用 Cloud API catalog 的名稱，使用者需明確設定，程式不猜測預設模型。
- [Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)：頁首標明 Ollama Cloud 尚不支援 structured outputs。首版不發送 `response_format`／native `format`，將 JSON schema 放入 system prompt；收到結果後仍執行共同驗證。不得宣稱模型端保證 schema。
- Ollama Cloud 僅接受最終 `message.content` 作業務結果；reasoning 不作替代答案。拒絕空答案、refusal、非正常完成、無效 JSON、未知 domain／category，以及不完整／不合規的翻譯。
- OpenRouter 保持現有 model、price caps、structured output 與 reasoning 行為；預設不切換 provider。

## 設定與失敗契約

- `CLASSIFICATION_MODEL_PROVIDER`、`TRANSLATION_MODEL_PROVIDER`：`openrouter`（預設）或 `ollama_cloud`。
- 保留既有 `CLOUD_MODEL_*`、`TRANSLATION_MODEL_*` 作 OpenRouter 設定，避免改動既有部署輸入；新增各 Layer 的可選 OpenRouter timeout，未設定時沿用 `MODEL_TIMEOUT_SECONDS`。
- Ollama 使用獨立 `OLLAMA_CLOUD_BASE_URL`、`OLLAMA_API_KEY`、各 Layer 的 model／timeout／reasoning 設定。只在 route 啟用時要求對應 key／model；不借用 OpenRouter 憑證。
- Layer 1 新增 `TRANSLATION_FALLBACK_PROVIDER`，預設沿用 primary provider。現有 `TRANSLATION_PAID_FALLBACK_ENABLED`、`TRANSLATION_FALLBACK_MODEL_NAME` 與 fallback budget 保留名稱，語意為明確啟用的雲端備援；沒有預設備援或額外請求。
- `MODEL_ROUTE=cloud_small` 保留為既有 route 標記；`local_8b` 與未知值啟動即失敗，provider 由新 selector 決定，不默默將舊 local 設定改成付費呼叫。
- Timeout／連線失敗、408／429／5xx、無效或不完整輸出可嘗試已配置的翻譯備援；400／401／403／404 等設定或認證錯誤直接停止，不以 fallback 掩蓋。所有 attempt 分別記錄 usage。
- Layer 2 維持單一 provider 與既有 processing retry，不新增跨 provider fallback。
- daily budget 仍以實際請求預留次數跨 provider 計算，不增加 DB schema；未知 Ollama 費用保持 `null`，不當作零成本。
- 翻譯耗盡後記錄實際嘗試的 route；未呼叫的 fallback 不可被誤標為失敗 provider。

## Plan

| 階段 | 產物與獨立 commit | 驗收標準 | 進度 |
| --- | --- | --- | --- |
| P0 | 本文件與服務索引；`docs: plan cloud model provider implementation` | 範圍、契約、分期、驗收與外部限制可追溯 | 完成：`594f322` |
| P1 | Protocol、OpenRouterClient、共用任務／HTTP／usage 拆分；`refactor: isolate OpenRouter model client` | OpenRouter request、結果、price routing、usage、日誌遮罩及既有測試保持；worker 不依賴具體 client | 完成：`d4f0673`；126 tests 通過 |
| P2 | OllamaCloudClient、provider factory／設定、跨 provider translation fallback；`feat: add Ollama Cloud model provider` | 兩層可獨立選 provider；Cloud key／model 缺失 fail fast；參數隔離；strict JSON 與業務驗證；每次呼叫預算／usage；無隱藏重試 | 完成：`e945296`；228 tests 通過 |
| P3 | 移除 local route、Compose／env examples、服務文件與整合回歸；`refactor: retire local model routes and document cloud providers` | active runtime／設定樣板無 local route；舊 local 選擇明確報錯；Compose 使用假資料驗證；完整服務測試通過 | 完成：241 tests 通過，隨本階段提交 |
| P4 | 最終差異審查、驗收證據、進度結案；`docs: close cloud model provider implementation` | P0–P3 提交可追溯、工作產物已提交、無關修改未納入；清楚列出未執行的真實 Cloud 驗證與部署 | 待開始 |

每階段先完成對應驗證，再在同一 commit 更新本文件；下一階段補記前一階段 SHA，避免自指 commit hash。單純本地實作不改 production env 或 runtime。

## 驗收矩陣

| 類別 | 必要案例 |
| --- | --- |
| OpenRouter 回歸 | 既有分類與四語翻譯、schema、reasoning、price caps、header 遮罩、usage／失敗記錄 |
| Ollama Cloud request | Cloud URL／Bearer key；不帶 OpenRouter provider／headers／response_format；schema 進 prompt；model／timeout／reasoning 為該 route 的值 |
| Ollama Cloud response | 成功兩層輸出；空 content／reasoning-only／refusal／length／malformed response／無效 JSON 失敗且有 usage；不修復 JSON |
| 業務驗證 | 未知 domain／category、重複或缺少語言、錯誤文字 script、過長摘要與缺 full translation 拒絕 |
| Factory／設定 | 預設全 OpenRouter；任一層單獨切 Ollama；各方向 translation fallback；缺 key／model、不支援 provider、無效 timeout 與 retired route 拒絕 |
| Worker | primary 成功不呼叫 fallback；transient／invalid output 才 fallback；認證錯誤停止；quota／fallback quota 阻擋呼叫；成功與失敗逐 attempt 入帳；分類結果不因翻譯失敗撤銷 |
| 整體 | normalizer-classifier 完整測試、compile、Compose 靜態與離線 config 驗證、git diff 檢查 |

## TODOs

- [x] P1 完成；程式與本記錄於同一階段提交。
- [x] P2 完成；程式與本記錄於同一階段提交。
- [x] P3 完成；程式與本記錄於同一階段提交。
- [ ] P4 審查與結案提交。
- 後續獨立工作：使用者選定 Cloud model／帳戶額度後，再安排有明確請求與成本上限的真實 API、品質與延遲評估；本次不自動執行。

## 驗證與提交紀錄

- 基準：先前針對 model client／settings／translation runtime／Luna runtime 的 50 個 mock tests 通過；未呼叫真實 API。

- P1：`services/normalizer-classifier/.venv/bin/python -m pytest services/normalizer-classifier/tests -q --disable-warnings --tb=short`：126 passed；compileall 與 `git diff --check` 通過。既有 warning 為 Python 3.14／pytest-asyncio deprecation。日誌模組改為 `model_transport`，事件名稱與遮罩行為保持。

- P2：完整 normalizer-classifier suite：228 passed；compileall 與 `git diff --check` 通過。新增 Cloud request／response／業務驗證、各層 provider／timeout 設定與跨 provider fallback 測試；worker 測試覆蓋逐次預算／usage、認證錯誤停止、quota 阻擋與分類先儲存後翻譯。
- P2 實作細節：OpenRouter identity 明確固定，不再由 URL 猜測；Ollama Cloud 限直接 `https://ollama.com/v1`，不支援本機 daemon／任意 proxy。拒絕未設定語言的輸出；原有額外日語測試改為明確要求日語。 malformed envelope／usage 可記錄失敗，不遺漏 attempt。

- P3：完整 normalizer-classifier suite：241 passed；compileall、`make compose-config`、`git diff --check` 通過。新增公用 env 樣板與 Compose 實際 render → Settings → factory 的離線驗收，覆蓋預設 OpenRouter 及雙層 Ollama／OpenRouter 備援。
- P3：移除 local 設定欄位／factory 分支／部署 wiring／樣板與測試專用 local route；`MODEL_ROUTE` 僅接受 `cloud_small`，退役值會在建立 client 前被拒絕。歷史 usage／migration 不修改。修正空字串 optional timeout／fallback provider 的 env 正規化，現有私有 env 未更動。
- P3：同步目前服務契約、開發與部署設定說明及 V1 範圍；舊模型預設與 legacy summary 範例在涉及段落一併對齊。未改動 checkout 中其他既有文件或功能修改。
