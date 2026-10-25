# News 雲端模型 provider 拆分與 Ollama Cloud 整合

## Status

- 狀態：P0–P6 已完成；R2 target-script 修正本地完成、未部署。HomeLab 仍為 P6 的 `abc6107`／GLM／low；VPS／公開網站未部署本次變更。
- 建立日期：2026-10-21；時區：Asia/Bangkok。
- 授權：使用者已要求依本文件推進本地實作，各階段獨立提交並回寫進度。
- 所屬 repo：`xauusd-trading-monitor`，直接使用 `develop`；不納入 checkout 中既有、與本工作無關的修改。
- 範圍：News normalizer-classifier 的 Layer 1／Layer 2；保留 OpenRouter，新增直接呼叫 Ollama Cloud 的獨立 client，退役早期 local LLM route。
- 完成定義：P0–P4／R1 的本地程式、設定、文件與 mock 驗收全部通過。使用者後續明確授權 T1／T2／T3 的有界真實 Cloud 測試，結果另列於本文；P6 後續已明確授權並完成 HomeLab normalizer-only 發布與部署；完整語言品質與長期容量認證仍不在本輪範圍。

## 決策與目前實作

- Worker 先完成 Layer 2 classification／event，再執行 best-effort Layer 1 translation-summary；保持此順序及資料契約。
- 重構前的 `OpenAIStyleModelClient` 混合任務 prompt、provider 參數、HTTP、解析、驗證與 usage。
- `local_8b`／`LOCAL_MODEL_*` 是早期探索，可移除；不保留本機推論實作、fallback 或相容 client。
- OpenRouter 與 Ollama Cloud 各有獨立實作類別，以小型 `ModelClient` Protocol 對接 worker；不使用共同 provider 父類別，也不建立 registry／plugin framework。
- 共用新聞 prompt、輸入組裝、schema、業務驗證、結果／錯誤／usage 契約，以及無 provider 判斷的 HTTP／log 工具。各 client 自行客製化 payload、headers、response 解析與能力限制。
- 所有 API attempt 由 worker 的現有預算與 fallback 流程掌握；client 單次操作只呼叫一次 HTTP，不隱藏重試、切換 provider 或 JSON 修復。
- R2：Ollama Cloud Layer 1 僅在 target-script 驗證失敗時，由 worker 最多新增一次帶欄位回饋的修正呼叫；所有 configured routes 共用此一次上限，逐次預算與 usage 留存。OpenRouter 不新增同 client 重試；timeout 與其他無效輸出不觸發此修正。

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
| P3 | 移除 local route、Compose／env examples、服務文件與整合回歸；`refactor: retire local model routes and document cloud providers` | active runtime／設定樣板無 local route；舊 local 選擇明確報錯；Compose 使用假資料驗證；完整服務測試通過 | 完成：`c8e0dfb`；241 tests 通過 |
| P4 | 最終差異審查、驗收證據、進度結案；`docs: close cloud model provider implementation` | P0–P3 提交可追溯、工作產物已提交、無關修改未納入；清楚列出未執行的真實 Cloud 驗證與部署 | 完成：審查與驗收證據隨本階段文件提交 |

| R1 | Code review 修復與回歸驗證；`fix: harden cloud model failure handling after review` | 下列五項問題修復；針對性回歸與完整服務測試通過，無關修改不納入 | 完成：20 個針對性回歸／完整服務 261 tests 通過；隨 R1 獨立提交 |
| R2 | Layer 1 target-script 修正；`fix: retry Ollama translations once after script validation failure` | 保留驗證、定位所有錯誤欄位、補強全文提示；修正呼叫最多一次且遵守預算，不重播分類；完整 mock suite 通過 | 本地完成：19 個新增案例／完整服務 284 tests 通過；不改配置、不部署，長文／timeout 另議 |

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
- [x] P4 審查與結案；本記錄於結案階段獨立提交。
- T1／T2 已依後續授權分別完成 GLM 與 MiniMax 各 6 次真實 Cloud 冒煙／對比測試；待辦為擴大真實新聞、語言品質、穩定性與容量評估，不自動啟用 worker。

## 驗證與提交紀錄

- 基準：先前針對 model client／settings／translation runtime／Luna runtime 的 50 個 mock tests 通過；未呼叫真實 API。

- P1：`services/normalizer-classifier/.venv/bin/python -m pytest services/normalizer-classifier/tests -q --disable-warnings --tb=short`：126 passed；compileall 與 `git diff --check` 通過。既有 warning 為 Python 3.14／pytest-asyncio deprecation。日誌模組改為 `model_transport`，事件名稱與遮罩行為保持。

- P2：完整 normalizer-classifier suite：228 passed；compileall 與 `git diff --check` 通過。新增 Cloud request／response／業務驗證、各層 provider／timeout 設定與跨 provider fallback 測試；worker 測試覆蓋逐次預算／usage、認證錯誤停止、quota 阻擋與分類先儲存後翻譯。
- P2 實作細節：OpenRouter identity 明確固定，不再由 URL 猜測；Ollama Cloud 限直接 `https://ollama.com/v1`，不支援本機 daemon／任意 proxy。拒絕未設定語言的輸出；原有額外日語測試改為明確要求日語。 malformed envelope／usage 可記錄失敗，不遺漏 attempt。

- P3：完整 normalizer-classifier suite：241 passed；compileall、`make compose-config`、`git diff --check` 通過。新增公用 env 樣板與 Compose 實際 render → Settings → factory 的離線驗收，覆蓋預設 OpenRouter 及雙層 Ollama／OpenRouter 備援。
- P3：移除 local 設定欄位／factory 分支／部署 wiring／樣板與測試專用 local route；`MODEL_ROUTE` 僅接受 `cloud_small`，退役值會在建立 client 前被拒絕。歷史 usage／migration 不修改。修正空字串 optional timeout／fallback provider 的 env 正規化，現有私有 env 未更動。
- P3：同步目前服務契約、開發與部署設定說明及 V1 範圍；舊模型預設與 legacy summary 範例在涉及段落一併對齊。未改動 checkout 中其他既有文件或功能修改。

## 最終驗收（P4）

| 驗收項 | 證據與結果 |
| --- | --- |
| OpenRouter 行為 | `test_model_client.py`、`test_luna_runtime.py`、`test_translation_runtime.py` 通過；保留既有預設與參數政策 |
| Cloud 能力與參數隔離 | `test_ollama_cloud.py` 通過；兩層成功路徑、錯誤輸出、未知 taxonomy、四語驗證、HTTP 錯誤分類、各方向 factory 設定均覆蓋 |
| Worker 協調 | `test_worker_model_providers.py` 通過；逐次 budget／usage、停止條件、實際 route 歸因與分類／翻譯執行順序均覆蓋 |
| 設定與退役 | `test_provider_configuration.py` 通過；三個公用 env 樣板、空設定正規化、retired route 拒絕與兩種 Compose render 情境均覆蓋 |
| 完整服務 suite | 241 passed，無 skipped；既有 pytest-asyncio／Python 3.14 deprecation warnings 不影響結果 |
| 靜態驗證 | compileall、`make compose-config`、`git diff 594f322^..HEAD --check` 通過；沒有新增 runtime dependency 或 DB migration |
| 提交邊界 | P0 `594f322`、P1 `d4f0673`、P2 `e945296`、P3 `c8e0dfb`；P4 為本文件的獨立結案 commit，以 `docs: close cloud model provider implementation` 識別 |
| Checkout 保護 | 維持 `develop`；工作範圍的檔案已提交，原先 public-web／public-api／notification／shared82 等無關修改保留，未包含於本批提交 |

P4 當時未執行（後續 T1 另列）：真實 Ollama Cloud／OpenRouter inference、雲端帳戶／額度確認、模型品質／延遲評估、DB 寫入／migration、container 啟停、私有 env 修改、production 切換、push／release／部署。上述為後續啟用驗證，不是本次本地實作的通過證據。

回退方式：維持兩個 provider selector 為 `openrouter` 且 translation fallback 停用即可保持原先預設呼叫路徑。若需要程式回退，依 P3 → P2 → P1 順序 revert 對應提交；未變更 schema／資料，不需要資料回滾。

## Code review 與修復（R1，2026-10-21）

範圍：`594f322^..94bff23` 的 provider 拆分、factory／settings、worker、usage、Compose／樣板與既有測試，並追蹤 `db.py` 的 commit／translation upsert 行為。這是本次變更的功能回歸 review，不是整個 repo 的完整安全稽核。

| 編號／優先級 | 觸發條件與影響 | 修復與回歸案例 |
| --- | --- | --- |
| R1.1／P1 | Layer 2 已 commit，後續 usage／翻譯 DB 操作失敗仍走 `mark_failed`；可能重新分類、重複呼叫模型。翻譯 storage 與 API 共用 except，也會將正常模型輸出當作失敗，`update_translation_failed` 會清空已有翻譯 rows | 分類 commit 後不再將 task 改回 retry／failed；翻譯 API 與 storage 的錯誤邊界分開，storage 失敗不 fallback、不改寫 failed 翻譯。以 classification usage、translation usage、translation result、failed-attempt usage 四種 DB 失敗回歸 |
| R1.2／P2 | OpenRouter 分類只驗證可解析 JSON；`finish_reason=length/content_filter` 或 refusal 仍可能被接受為有效分類 | Provider 解析先拒絕已知非正常完成／refusal，保留缺 finish_reason 的既有相容行為；三種有效 JSON 但不完整／拒絕的回應回歸 |
| R1.3／P2 | `TRANSLATION_REQUIRE_ALL_LANGUAGES=false` 提早 return，連已提供語言缺摘要／全文也通過，可能標記空內容為 completed | 此旗標只控制是否允許缺語言；每個已提供語言仍需滿足 summary／full-translation policy。兩種 provider 分別驗證缺欄位拒絕及完整 subset 接受 |
| R1.4／P2 | enabled categories 為空時跳過 category 驗證；空 domains／categories 的 schema 也放寬為任意值，與 worker 可接受範圍不一致 | 空 categories 僅允許 `other`（既有 nullable result 仍由 DB 正規化）；空 domains 要求 primary 為 null、relevant_domains 為空；兩種 provider 的未知 category 拒絕與 schema 回歸 |
| R1.5／P2 | 缺 provider usage 時 tokenizer／cache 失敗會遮蔽原始模型錯誤，失去該次 usage；未知 output 被視為零，成本與 total 看似完整 | 估算失敗保留原始錯誤與 attempt，未知 tokens／total／cost 為 null，僅在 input／output 都已知時推導 total／cost。記錄安全的 estimation error 類別，不將拒絕的答案假估為空字串 |

回歸測試集中於 `tests/test_provider_review_regressions.py`。修復不新增 dependency／schema／provider、fallback route 或 production 行為切換。儲存層不可用時，可能仍有缺 usage 或待處理翻譯，需要依 error log 人工檢查；本次不引入新的持久化重試 queue，也不重播已 commit 的分類。

R1 驗證結果：

- 針對性回歸：在 `services/normalizer-classifier` 執行 `.venv/bin/python -m pytest tests/test_provider_review_regressions.py -q --disable-warnings --tb=short --maxfail=5`，20 passed。
- 修復前重現：在可丟棄的暫存 source copy 中，使用 `git show 94bff23:<path>` 還原四個被修復的 runtime 檔案，保留相同的 20 個新增測試與既有 fixtures；結果為 18 failed、2 passed。兩個通過案例是完整的部分語言 subset 正向控制。未切換／覆寫工作 checkout，驗證後刪除暫存副本。
- 完整回歸：同 service 執行 `.venv/bin/python -m pytest tests -q --disable-warnings --tb=short --maxfail=5`，261 passed，無 skipped。874 個既有 pytest-asyncio／Python 3.14 deprecation warnings 不影響結果。
- AST parse、compileall 與 `git diff --check` 通過；完整 suite 內含既有兩種離線 Compose config render 驗證，不執行 container workload 或連線 DB。
- 最初採用的 security-audit skill 對 target tests 要求完整 OS sandbox；現有隔離 runtime 沒有所需 Python dependency。使用者已在本次 review 明確允許沿用原有本機 virtualenv 執行 mock pytest，之後才執行上述 baseline／修復後測試。未安裝依賴；mock 不呼叫真實模型 API、不連 DB、不啟停專案 runtime。
- R1 修復、回歸測試與本記錄以 `fix: harden cloud model failure handling after review` 獨立提交至 `develop`。原 P4 的 241 passed 保留為當時版本證據，本節的 261 passed 是 review 後的最新驗收。

## 真實模型冒煙測試（T1，2026-10-21）

使用者提供本機私有 env 的 key，明確授權測試 `glm-5.3-flash:cloud`。官方[模型頁面](https://ollama.com/library/glm-5.3-flash:cloud)與 [Cloud catalog](https://ollama.com/api/tags) 指定直接 API model 為 `glm-5.3-flash`，`:cloud` 用於 App／CLI。此測試透過既有 factory／OllamaCloudClient 呼叫 `https://ollama.com/v1/chat/completions`；不經本機 Ollama，也未更改私有 env。

範圍：固定的英文未證實爆炸消息、中文央行利率維持消息、無關的網站配色消息，均為人工撰寫的 fixture；3 次分類、3 次翻譯嘗試，總上限 6 次，無隱藏重試／OpenRouter fallback。每次由測試 harness 限制 `max_tokens=4096`，這不是 production client 的新預設。輸出直接通過目前的 Pydantic／業務驗證，不修復 JSON。未啟動 worker、連 DB、寫入新聞或部署。

| Case／Layer | Reasoning effort | Latency | Input／output tokens | 結果 |
| --- | --- | --- | --- | --- |
| 英文未證實爆炸／Layer 2 | 未指定，模型預設 | 28.321 s | 1164／2811 | 成功；relevant=true、score=35、requires_confirmation=true |
| 英文未證實爆炸／Layer 1 四語 | 未指定，模型預設 | 32.712 s | 962／4096 | `finish_reason=length`；測試上限截斷，client 正確拒絕 |
| 同則英文／Layer 1 四語 | `low` | 5.635 s | 962／722 | 成功；zh-Hant／en／th／ja 摘要與全文齊全 |
| 中文央行維持利率／Layer 2 | `low` | 2.297 s | 1175／344 | 成功；relevant=true、score=70、primary_domain=monetary |
| 同則中文／Layer 1 四語 | `low` | 4.358 s | 974／715 | 成功；4.50% 與未承諾降息的核心語意保留 |
| 無關網站配色／Layer 2 | `low` | 4.431 s | 1151／286 | 成功；relevant=false、score=0、primary_domain=null |

第一次翻譯碰到測試 token ceiling 後，查核模型文件的 thinking 設計：reasoning 始終開啟，可使用 low／high／max。其餘 4 次以明確 `low` 完成，仍計入同一個 6-request campaign 上限。不能從這個非同時、非完整 A/B 的小樣本推定全部延遲差異都來自 reasoning effort。

總計 6388 input tokens、8974 output tokens，5 次通過、1 次有界截斷；其中 low variant 4／4 通過。API 未回實際 USD cost，本系統亦未設定該 provider／model 的計費單價，成本保留未知，不把 catalog 標價當實際帳單。完整非敏感輸入、輸出、usage 與 request hashes 見 [T1 evidence](evidence/2026-10-21-ollama-cloud-glm-5.3-flash.json)；來源程式 commit 為 `d3ec333`。

人工初審的待修品質問題：

- 日文爆炸消息摘要以 `と報じられた、地方通信社の報道によると` 起頭，保留不確定性但句型生硬。
- 中文消息未指明央行國家，分類輸出的 impact channel 卻加入 `Fed expectations`，有無來源依據的美國特定推論。
- 這些 fixture 僅驗證可呼叫、結構與少量關鍵語意；不是 native-language 認證、真實新聞 benchmark、正式分類 admission 或 production 吞吐量驗收。暫不自動切換常駐 worker。

建議測試設定（仍須由操作者決定正式啟用）：`OLLAMA_CLOUD_*_MODEL=glm-5.3-flash`、兩個 `OLLAMA_CLOUD_*_REASONING_EFFORT=low`。模型名稱與 effort 只在本次程序內覆寫，使用者既有 `.env.dev` 原值保持。T1 evidence 與進度以獨立文件提交保存。


## 模型對比測試（T2，2026-10-21）

使用者明確授權以 `minimax-m3.1-flash` 進行對比。依官方[模型頁面](https://ollama.com/library/minimax-m3.1-flash:cloud)與 [Cloud catalog](https://ollama.com/api/tags)，直接 Cloud API 使用 `minimax-m3.1-flash`。沿用 T1 的本機私有 key、既有 factory／client、人工 fixture、taxonomy、domain modules 與六次呼叫順序；未更改私有 env、未啟動 worker、未連 DB 或部署。仍限制每次 `max_tokens=4096`，無隱藏重試／fallback。

每次都將 request payload 的 model 正規化為 GLM 基準名稱，再比對既有 request hash；6／6 相符，表示來源內容、messages 與 schema prompt 相符。該 hash 不涵蓋 reasoning effort／token ceiling，這兩項另按原始六列逐項配對。另一次 `/api/show` metadata probe 回傳 HTTP 200，capabilities 包含 thinking，但 `thinking` 欄位未提供等級資訊；因此相同的 requested `low` 不代表已證明兩個模型的實際 reasoning 強度相同。metadata probe 不計入六次 inference。

| Case／Layer | Reasoning effort | GLM latency | MiniMax latency | MiniMax input／output tokens | MiniMax 結果 |
| --- | --- | --- | --- | --- | --- |
| 英文未證實爆炸／Layer 2 | 未指定 | 28.321 s | 31.028 s | 1365／2335 | 通過；relevant=true、score=46、requires_confirmation=true |
| 英文未證實爆炸／Layer 1 四語 | 未指定 | 32.712 s（截斷） | 28.101 s | 1160／3110 | 通過；四語齊全 |
| 同則英文／Layer 1 四語 | `low` | 5.635 s | 23.149 s | 1160／2986 | 通過；人工初審有日文語意問題 |
| 中文央行維持利率／Layer 2 | `low` | 2.297 s | 28.435 s | 1363／2284 | 通過；relevant=true、score=82、primary_domain=monetary |
| 同則中文／Layer 1 四語 | `low` | 4.358 s | 21.116 s | 1159／2113 | 通過；保留 4.50% 與未承諾降息 |
| 無關網站配色／Layer 2 | `low` | 4.431 s | 7.531 s | 1353／637 | 通過；relevant=false、score=0、primary_domain=null |

MiniMax 共 7560 input tokens、13465 output tokens，程式結構／業務驗證 6／6 通過；GLM T1 為 5／6 通過，其中一次觸及測試 token ceiling。相同 requested `low` 的四次配對兩者均為 4／4 通過；MiniMax 平均 20.058 s，GLM 平均 4.180 s，這組觀測約為 4.8 倍。對應 output tokens 為 8020／2067。兩組測試時間不同、樣本很少，tokenizer、reasoning 計量、cache、輸出涵蓋範圍與當時 provider 負載亦可能不同，不能視為穩定效能排名或把差異全歸因於模型。

人工初審：

- MiniMax 的央行分類沒有 GLM 樣本中無來源的 `Fed expectations`，region 為 null，primary actor 明確保留「未指明央行」。這是單一 fixture 的改善證據。
- MiniMax `low` 日文爆炸翻譯把 `casualty figures` 縮窄為 `負傷者数`，遺漏死亡人數範圍；把單一 `The report` 擴大為 `どの報道でも`，超出來源。`報道機関は…と報じられた` 的主詞／被動用法亦生硬。結構通過不代表語意品質通過。
- MiniMax 全文包含提供的標題，GLM T1 全文省略標題；輸出內容涵蓋範圍不同，影響 token 數。MiniMax 預設 effort 的日文措辭較自然，但不能用它與 GLM low 的措辭差異宣稱同條件優勢。

結論：兩者均可透過目前 Cloud adapter 完成任務；此樣本中 GLM requested low 延遲較低，MiniMax 預設 effort 在測試 ceiling 內完成翻譯，但兩者均有需改善的內容品質。尚未通過正式模型品質 admission，不據此切換常駐 provider／model。API 未回實際 USD cost，成本維持 null；catalog 標價或限時優惠不作實際帳單證據。

完整非敏感輸入、輸出、逐筆 usage、配對 hashes 與統計見 [T2 evidence](evidence/2026-10-21-ollama-cloud-minimax-m3.1-flash.json)。執行程式來源為 `d3ec333`，GLM evidence 基準為 `89f7cf6`。T2 以獨立文件提交保存；本次僅新增對比證據與更新進度，不變更 runtime code。


## 本地真實新聞處理（T3，2026-10-21）

使用者明確要求在本地處理一輪真實新聞，核對 Layer 1／Layer 2 的 `glm-5.3-flash` 與 `reasoning_effort=low`、結果及耗時，暫不部署。先前已依使用者決定更新私有 `infra/.env.dev`，兩層均選 `ollama_cloud`；本輪不再次修改 env。

本地 `127.0.0.1:55432` 當時沒有開發 PostgreSQL container 或資料卷，故透過既有 development Compose 建立本地 DB，執行現有 Alembic migrations 至 `0026_ai_daily_budgets`；沒有接觸遠端／production。透過既有 rss-collector HTTP／parser 取得 Federal Reserve、CENTCOM、Mehr News 的 live RSS，各選一則通過既有 routing 的消息，再由原有 `upsert_raw_item` 寫入本地 queue。輸入為 RSS 標題與摘要，沒有額外下載文章內文；CENTCOM 該則只有標題。

執行方式：一次性 harness 直接執行既有 worker `_loop`，concurrency=1，程序內分類／翻譯預算各 3 次，不啟動其他服務。factory、prompt、schema、HTTP payload 與 DB 寫入沿用 runtime；未覆寫 token ceiling。六次實際 transport payload 均送往 `https://ollama.com/v1/chat/completions`、model=`glm-5.3-flash`、reasoning_effort=`low`，API 回傳 model 亦全部相符、`finish_reason=stop`。這能確認送出的參數與回應模型，不能由此量測服務端實際 reasoning 強度。

| 真實 RSS 消息 | Layer 2 latency | Layer 1 latency | 分類結果 | 本地處理／翻譯 |
| --- | --- | --- | --- | --- |
| CENTCOM：反無人機攔截器量產框架協議（2026-10-19） | 3.839 s | 3.604 s | relevant=true、45、geopolitics | completed／completed |
| Fed：終止 Gardner Bancshares／Small Business Bank 執法措施（2026-10-16） | 4.733 s | 3.420 s | relevant=false、5、primary_domain=null | completed／completed |
| Mehr：加薩衛生部警告醫院燃油耗盡（2026-10-21） | 3.366 s | 3.204 s | relevant=true、35、geopolitics | completed／completed |

三則分類與三次翻譯全部通過現有程式／業務驗證；DB 留下 6 筆成功 `ai_model_calls`、6 筆 completed translation rows（繁中／英文各 3 筆）。Layer 2 平均 3.979 s、Layer 1 平均 3.409 s。從首次 API request 到最後回應的實際處理區間約 22.293 s；這不包含 DB 初始化，也不包含處理完成後等待停止的 idle 時間。harness 全生命週期為 72.574 s；既有 worker 在達到 call budget 後會 idle，而非自動退出，因此先確認所有 DB commits 完成後才中止處理程序，沒有中斷中的 API request。總計 9817 input tokens、1688 output tokens；實際 USD cost 未回傳，保留未知。

分數均低於既有事件門檻 70，因此 event count=0、public_outbox rows=0，符合規則。無 retry、fallback、截斷或模型錯誤。未啟動 collector 常駐 loop、alert delivery、public syncer 或部署。完成後已停止本地 worker 程序與 development PostgreSQL；保留新建的資料卷與結果。

結果人工初審與限制：

- Layer 1 繁中／英文摘要與全文齊全；反無人機的 25,000 枚年產量、Fed 的執法終止主體、加薩醫院發電機燃油耗盡等核心資訊保留。當前本地 env 僅要求兩語，本輪沒有驗證泰文／日文。
- Layer 2 將 Fed 例行監管消息判為不相關，未擴寫成利率決策；兩則地緣消息評分較低且未生成事件。
- 加薩分類的 `topic_tags` 包含原始標題／RSS 摘要未出現的 `iran`，存在無依據的 tag；將人道基礎設施消息歸為 `military` 亦值得校準。格式驗證成功不等於正式內容品質通過。
- Fed 標題與 RSS 摘要本身相同，現有 normalization 將兩段連接後，全文翻譯亦重複。這是上游輸入去重的既有問題，本輪不擴大成 normalization／prompt 重構。
- 本輪只驗證三個短 RSS 輸入與本地真實 DB 回寫，未涵蓋長文、事件插入分支、production 容量或正式模型品質 admission。

完整實際參數、逐筆 API／DB usage、輸出、狀態與耗時見 [T3 evidence](evidence/2026-10-21-ollama-cloud-glm-real-news.json)。本輪驗收結果：兩層實際使用指定模型與 requested low、三則分類／翻譯成功回寫、六筆 usage 與時間可核對、處理程序已停止、未部署；上述內容品質事項留待後續校準。本地 evidence 另存於 ignored `var/evaluations/glm-real-news-20261021/`。


## 接受決策與部署預檢（P5，2026-10-21）

使用者接受目前已記錄的內容品質缺陷，包括加薩消息無來源的 `iran` tag、RSS 標題與摘要重複，以及前述小樣本語言／分類限制，要求提交變更並進行部署 preflight。這是接受已知缺陷，不是宣稱缺陷已修復或完成全面品質認證。

部署候選：HomeLab 的 `normalizer-classifier`，Layer 1／Layer 2 均使用 Ollama Cloud `glm-5.3-flash`、requested `reasoning_effort=low`，沿用目前私有 `infra/.env.dev` 中的同一把 `OLLAMA_API_KEY`。key 只在私有輸入或程序記憶體傳遞，禁止納入 Git、報告、image layer 或命令列參數；不以 development env 覆蓋 production env。

本輪只授權提交與 preflight；檢查本地程式／Compose、候選 image、HomeLab 現況與 schema 相容性。既有 runtime／測試證據已分階段提交至 `b03abdd`。VPS、Cloudflare Pages、production env 寫入、image push、服務重建、migration 執行與正式部署不在本輪範圍。所有既有無關 dirty changes 均排除。

P5 結果：**技術 preflight 通過；正式 deployment gates 尚待執行**。接受決策 commit 為 `24da7ba`，前述實作與測試證據均已提交；本輪沒有 push、merge main 或發布。

| 檢查 | 結果 |
| --- | --- |
| normalizer 完整 mock pytest | 261 passed；874 筆既有 Python 3.14／pytest-asyncio deprecation warnings，1.18 s |
| whitespace／production Compose template | `git diff --check`、`docker compose --env-file infra/.env.example -f infra/docker-compose.prod.yml config --quiet` 通過 |
| HomeLab 現況 | 兩個 normalizer replicas 均 running、restart_count=0；舊 image 為 `normalizer-classifier:3de3c10`，目前尚無 Ollama key／新 provider env |
| DB 相容性 | production schema 已為 `0026_ai_daily_budgets`；required routing／translation／budget tables 齊全，usage layer／nullable token-cost constraints 相容，`events.summary_zh` 可為 null；本次候選沒有新增 migration，無須為此執行 schema migration 或其 restore rehearsal |
| 候選 Compose | 將 committed Compose 經 stdin 唯讀送至 HomeLab，用既有 production env 加程序內 override 渲染；兩層 GLM／low、Cloud URL、同 key 全部相符；保留四語 `zh-Hant,en,th,ja`、OpenRouter key、原有兩個 replicas／每個 worker_concurrency=2 的規模，fallback 維持關閉；其他既有 service 的 image 宣告不變 |
| 健康／空間 | HomeLab dashboard 與 public API 均回 `status=ok`、`database=ok`；HomeLab project filesystem 約 349 GiB 可用；原 normalizer registry manifest 可讀 |
| 候選 image | 以 `git archive 24da7ba` 的 service Dockerfile／pyproject／src 建置，排除所有未提交變更與 env；`linux/amd64` 建置成功，local tag=`xauusd-normalizer-preflight:24da7ba`，未 push |
| image 內載入 | Python 3.12.15／x86_64；兩層 client 與 payload 參數檢查、四語設定、CLI help 全部通過；檢查容器 `--network none`，沒有 API 呼叫或 DB 連線 |
| secret custody | 已建立 ignored、mode 0600 的私有 `infra/.env.ollama-cloud.preflight`，只包含本次選定 override 與同一把 key；同 key 比對僅輸出 boolean；未寫入 production env、Git 或 image |

候選 application source 固定為 `24da7ba`。本地 image ID 為 `sha256:f2a9c5d2d026831ede667894fd870b23a83e37b6fd6294c4ffed64fc15918dba`；這是本地 image ID，並非已發布的 registry manifest digest。後續可將該已驗證 image 發布為 `ghcr.io/mrsuner/xauusd-trading-monitor/normalizer-classifier:24da7ba`，並只用 `NORMALIZER_IMAGE_TAG` 指向它；不要全域變更 `IMAGE_TAG` 或重建無關服務。此 P5 報告後續 commit 只更新文件，不改變上述候選 application source。

部署前尚待完成：

1. 按當前受影響 HomeLab 狀態建立新備份、off-host 校驗與要求的 restore gate；本輪僅唯讀 preflight，沒有建立 production 備份，也沒有宣稱歷史備份足以部署。
2. 確認 scoped Git 發布來源：當前 `develop` 與 `origin/develop` 分歧，origin head 為 `1ee96ae`；本機也有其他工作的 dirty changes／既有未發布 commits。沒有 force-push、rebase、merge main、暫存無關修改或全樹 rsync。候選 image 已從指定 commit 的必要 service paths 建置；後續應只整合／發布授權範圍，不能直接整批推送。
3. 發布已驗證的 immutable candidate image，記錄 registry digest。這輪沒有 registry push。
4. 取得正式部署授權並通過備份 gate 後，先備份 production env，再只合併私有 override 的選定 keys，套用本次 Compose delta，只重建現有兩個 normalizer replicas；保留其餘 env、服務、DB 與 sessions。不要用 `.env.dev` 或該 partial override 整份覆蓋 production env。
5. 部署後檢查實際 Cloud payload／usage、四語新聞產出與管線狀態。T3 的真實 RSS 回寫只驗證繁中／英文；四語 GLM 的 bounded 冒煙證據在 T1，並不替代 production 驗收。

完整非敏感 preflight 證據見 [P5 evidence](evidence/2026-10-21-ollama-cloud-deployment-preflight.json)。本輪未變更任何 production 檔案、DB、runtime 或 image，未建立 VPS／Pages release。已接受的內容缺陷不再作為本次候選的阻擋項；上述尚待部署的實際 gates 仍須完成。


## HomeLab scoped 部署（P6，2026-10-21，完成）

使用者明確授權完成備份／還原、處理 Git 發布分歧、推送 image 並部署 HomeLab，只更新 normalizer，沿用同 key，兩層固定 `glm-5.3-flash`／`low`，部署後檢查真實新聞。VPS 與公開網站不在部署範圍。

已通過新備份 `glm-cloud-20261021T111037Z` 的 gate：來源與本機 age 密文 SHA256 相符，network-none PostgreSQL16.14 原生完整還原完成，25 張表行數、15 張核心表內容 fingerprint 與來源 roles／ownership 全部相符；驗證資源與明文已清理。首次 verifier 在初始化階段載入 roles 失敗；獨立 roles probe 通過，改為等待正式 PID1 PostgreSQL 就緒後重跑，全驗證通過。此過程沒有變更 production。

本次 11 個提交已 scoped 重放為 `b23b710` 至 `293a5f0`，遠端 develop 從 `1ee96ae` fast-forward 至 `293a5f0`；main 保持 `3de3c102`。本機 develop 整合遠端，原有 32 檔未提交內容逐一 SHA256 保留，其他本機未發布工作沒有推送。

18:39:02 Asia/Bangkok 首次只重建兩個 normalizer，image=`normalizer-classifier:293a5f0`、registry manifest=`sha256:d9c705e836a3059220cf6bb4f5cc5bad2c2897911c70a3b153192a60459f6ce5`。它重用 preflight 原 image 的 config digest `sha256:f2a9c5d2d026831ede667894fd870b23a83e37b6fd6294c4ffed64fc15918dba`，來源程式內容相同，避免重新解析依賴。HomeLab containerd 以 manifest digest 顯示 image ID，本機 classic store 以 config digest 顯示；已核對 manifest 的 config digest 與全部 RootFS layers，一致後才切換。其他服務 IDs／images／started_at 全部不變。四語設定與 OpenRouter key 保留，沒有 migration、VPS 或 Pages 變更。

### Production 摘要長度修正

第一則自然進入的真實新聞為 `https://t.me/Tasnimnews/453031`。Layer 2 成功（score=10、不相關，6.248 s），Layer 1 首次（20.502 s）及一次明確的 translation-only 手動重試均因英文摘要超過 400 字元被拒；失敗 usage 留存，分類沒有被重跑。這是 production 新發現的輸出可靠性問題，不能混同先前已接受的 tag／重複輸入限制。

只在 Ollama client 的 `translation_summary` prompt 加上保守的單句摘要目標：繁中 120 字元、其他語言 220 字元，保留歸因／不確定性；細節放在全文翻譯。既有繁中 280／其他 400 的 hard validation、分類 prompt、OpenRouter、key、model、effort 與 retry/fallback 契約均保持。沒有截字、JSON 修復或新增隱藏重試。

同一真實輸入的有界 live 檢查通過（1 request、20.346 s；摘要長度 zh-Hant=46、en=162、th=141、ja=78，四語全文齊全，未寫 DB）。新增四個摘要邊界回歸案例，完整 mock suite 265 passed。這是 prompt headroom 的實測改善，仍不是 Cloud 原生 structured-output 或永不超長的保證。見 [summary headroom evidence](evidence/2026-10-21-ollama-cloud-summary-headroom.json)。修正 image 發布、第二次 scoped 切換與真實新聞驗收已完成，結果如下。


### P6 最終部署與驗收

19:01:54 Asia/Bangkok 已只更新兩個 normalizer 至 application commit／image tag `abc6107`。Registry manifest digest 為 `sha256:0946a6d89079800e5cf76a74f1faa99dbe038cd3025e63a5acd8d7aeaab226a5`，config digest 為 `sha256:40e358b3752f77a6063d4a51037abf84499b726b61bb5423a91579de3e456566`。修正 image 從已驗證的前版 manifest 固定基底，僅以 `pip install --no-deps --force-reinstall .` 重裝本次 application source；比對確認 runtime dependency names／versions 全部不變，容器內實際載入的 Ollama client SHA256 與提交內容一致。

第二次切換前另建立 `glm-cloud-config-20261021T115700Z` 加密設定 checkpoint，HomeLab／Mac 密文 SHA256 相符，解密後 `.env`／Compose 檔案 hash 全部驗證，明文已清理。完整 DB 還原 gate 沿用同一 migration-free 發布流程已通過的 `glm-cloud-20261021T111037Z`；這個 checkpoint 只新增當前設定保護，沒有宣稱產生第二份完整 DB 備份。正式 env 只合併本次選定 keys，並保留原檔的 timestamp backup；沒有用 development env 覆蓋 production。

最終兩個 replicas 均 running、restart_count=0；有效 client factory 與實際 request 都核對到 Ollama Cloud `glm-5.3-flash`、requested `reasoning_effort=low`，key 與本地私有 key 比對為相同。四語保持 `zh-Hant,en,th,ja`，OpenRouter 設定保留。自首次部署前至最終驗收，所有非 normalizer 容器的 IDs／images／started_at／restart count 一致，HomeLab dashboard／DB health 正常。沒有 migration、VPS 部署、main 更新或公開網站發布。

真實新聞皆由既有 collectors 自然進入 production，未插入 fixture、重新排程已完成分類或改動 source 設定。5 則樣本的分類與四語翻譯最終全部 completed，共 20 筆語言結果：

| Source／樣本 | Score | Layer 2 | Layer 1 成功耗時 | 結果 |
| --- | --- | --- | --- | --- |
| Tasnim／教授網絡成立 `453031` | 10 | 6.248 s | 20.460 s | 初始英文摘要超長；修正後只補跑翻譯成功 |
| Press TV／地拉那抗議現場 `211677` | 5 | 4.297 s | 6.818 s | 自然 worker 處理完成 |
| Tasnim／演習圖文報導 `453033` | 10 | 4.504 s | 7.523 s | 自然 worker 處理完成 |
| Tasnim／海底電纜依賴分析 `453044` | 25 | 5.909 s | 21.091 s | 初始英文摘要超長；修正後只補跑翻譯成功 |
| Mehr／UKMTO 海事事件 `248798` | 55 | 5.778 s | 5.785 s | 修正 image 上新的自然 worker 完整流程成功 |

Layer 2 平均 5.347 s（4.297–6.248 s），成功的 Layer 1 四語呼叫平均 12.335 s（5.785–21.091 s）；這是不同長度／語言的真實輸入，不與 T1 人工短 fixture 直接作速度排名。觀察期間 production 共 13 次呼叫，10 成功、3 次英文摘要超長失敗（2 則新聞，其中一則有一次明確重試），失敗 usage 全部保留。修正後 4 次 production 呼叫全成功：2 次明確 translation-only 補跑，加上 1 則新新聞的 Layer 2／Layer 1；沒有新增失敗，沒有重跑分類或新增隱藏重試。另有 1 次本地新 prompt 的真實輸入檢查，不寫 DB，不混入 production 計數。

繁中／英文人工抽查看到來源歸因、95–99%／30% 數值與海事事件未確認性保留；泰文／日文驗證欄位、目標 script、長度與非空全文，沒有宣稱母語品質認證。UKMTO 例保留 requires_confirmation=true。樣本分數均低於既有事件門檻 70，因此未建立 event，這輪沒有驗證 production event 插入／發布分支。成本 API 未回，維持未知。先前已接受的 tag／重複輸入缺陷未擴大修復。

備份產物（加密，禁止提交內容）：

- HomeLab：`/home/luke/backups/xauusd-event-radar/glm-cloud-20261021T111037Z.tar.gz.age`。
- Mac off-host：`/Users/lukesun/Projects/trading-sys/infra/backups/glm-cloud-20261021T111037Z.tar.gz.age`。
- 設定 checkpoint：上述兩個目錄內的 `glm-cloud-config-20261021T115700Z.tar.gz.age`。
- 正式設定的 timestamp backups 與各階段 image／container identities 記錄於下方 evidence；只回滾 normalizer 時，優先恢復該階段 env／Compose 與原 image，僅以 `--no-deps --scale normalizer-classifier=2` 重建 normalizer，不自動還原 DB 或回退整個 stack。

Git：首次 scope 從 `1ee96ae` fast-forward 至 `293a5f0`，摘要修正再 fast-forward 至 `abc6107`；原本 11 個階段 commit 保留為重放後的獨立提交，修正另有獨立 commit。原本 32 檔未提交內容經逐檔 SHA256 保留，其他本機既有未發布 commits 未推送，本機 develop 已整合遠端而無 behind 分歧。main 維持 `3de3c102`。本節與證據另以文件 commit 同步到 develop，不更動已部署 application image。

完整非敏感的備份／還原 receipts、兩次 rollout、image config／manifest 身分、runtime clients、實際 request 參數、逐筆 usage、樣本翻譯長度／hash 與 Git 邊界見 [P6 deployment evidence](evidence/2026-10-21-ollama-cloud-homelab-deployment.json)。完整新聞文字與輸出只留在 ignored 本地 evidence，沒有提交 production env、API key 或 DB dump。

## Layer 1 target-script 修正（R2，2026-10-25，本地完成）

2026-10-22 的唯讀觀察發現：P6 摘要長度修正後約 17 小時，Layer 2 為 179／179 成功；Layer 1 為 179／181 成功（含兩則部署時的明確補跑）。兩次失敗分別為長文 `ReadTimeout` 及短文 `missing target script: zh-Hant`。後者的實際 HTTP 回應為 200／stop，繁中、泰文、日文摘要已翻譯，但三語 `full_translation` 全部沿用英文；原驗證器只回報第一個繁中欄位。這是全文輸出錯誤，不能透過放寬字元驗證解決，也不是繁簡字判斷問題。

使用者要求先修正字元檢查相關問題，長文方案另議。本階段不調整 timeout／model／reasoning／key／fallback 設定，不修改 DB schema，不部署、不補跑 production 新聞。HomeLab 仍使用 P6 `abc6107`，本地測試不呼叫真實 API 或連線 DB。

實作：

- 保留原有摘要字數、完整語言、非空全文與目標 script 驗證。新增 `TranslationScriptError`，一次收集所有錯誤語言與欄位，例如 `zh-Hant.full_translation`、`th.full_translation`、`ja.full_translation`；`ModelClientError` 帶出結構化欄位清單供 worker 判斷，usage 同時保留可讀錯誤。若同時有缺語言、缺全文或摘要超長，優先維持原錯誤，不進入此次 script 修正。
- 僅補強 Ollama Layer 1 prompt：逐語獨立檢查摘要與全文，只有與原文同語言的全文欄位可以沿用原文；英文來源的繁中／泰文／日文全文必須實際翻譯。人名、帳號可保留於已翻譯的句子內。
- Worker 僅對 Ollama Cloud 的 target-script 錯誤新增一次明確修正呼叫，帶入錯誤欄位，從原文重新產生整組翻譯。每個 client 單次操作仍只有一次 HTTP；修正次數跨 primary／fallback 共用上限，不新增持久化重試 queue，也不局部填補或拼接錯誤全文。
- 每次修正前重新通過既有 translation／daily／paid-fallback 預算，成功與失敗 usage 分別入帳；整組通過原有驗證後才寫入結果。未開 fallback 時最多兩次呼叫；已開 fallback 時最多為原有 routes 數加一次修正，不自行啟用其他 provider。OpenRouter 維持原有同 client 不重試行為；timeout、認證、JSON、摘要過長及缺全文等錯誤不觸發新的 script 修正。
- 分類先提交的順序維持；修正失敗、預算不足或結果寫入失敗均不重播 Layer 2。儲存錯誤不觸發模型重送，也不把已成功的模型結果覆寫為 failed rows。

驗收結果：

| 驗收項目 | 結果 |
| --- | --- |
| 重現三語全文複製英文 | 19 個新增 mock 案例之一；一次回報三個全文欄位，client 本身不重試 |
| 首次錯誤、修正成功／再次失敗 | 最多一次修正，保持原文與整組四語要求；分別保存兩次 usage，只有整組成功才寫入結果 |
| 預算與 fallback | Daily／per-run／budget store 不可用都會阻擋額外請求；各 route 共用一次修正上限，OpenRouter 不新增同 client 重試 |
| 非 script 錯誤與儲存錯誤 | timeout／auth／JSON／摘要超長／缺全文不進入 script 修正；修正成功後儲存失敗不呼叫 fallback |
| 分類獨立性 | 完整 worker loop 覆蓋一次分類、兩次翻譯失敗；分類只提交一次，未呼叫分類失敗重排程 |
| 完整回歸 | 在 `services/normalizer-classifier` 執行 `.venv/bin/python -m pytest tests -q --disable-warnings --tb=short --maxfail=3`：284 passed、1054 warnings、1.59 s；7 個修改／新增 Python 檔 AST parse 與 `git diff --check` 通過 |

本次為本地程式與 mock 回歸完成，不宣稱模型真實輸出已驗收或 production 失敗新聞已恢復。長文處理策略與真實 Cloud／HomeLab 驗收待後續授權；timeout 仍維持原值，不沿用討論中的 120 秒建議。本階段以表列 commit message 獨立提交，不推送、不部署。
