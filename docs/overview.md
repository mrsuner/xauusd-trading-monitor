# XAUUSD Event Radar MVP Overview

> V1 實作範圍已收斂為新聞消息層：Telegram / RSS / 官方頁面採集、原始入庫、預處理、模型相關度判斷與通知。`mt5-collector`、`market_snapshots` 與行情異動反查屬於後續版本。最新範圍定義請見 [最終目標與 V1 實作範圍](./final-target-and-v1-scope.md)。首次 HomeLab 上線後的降噪、AI 成本統計與 source 管理規劃請見 [Production Feedback Roadmap](./production-feedback-roadmap.md)。

## 1. 專案定位

XAUUSD Event Radar MVP 是一個面向黃金交易情境的事件雷達系統。它的核心目標不是預測交易方向，也不是取代交易決策，而是在 XAUUSD 突然暴漲或暴跌時，快速回答以下問題：

- 是否存在消息面驅動？
- 消息來自哪一個權力系統或市場管道？
- 來源可信度與官方程度如何？
- 是否存在相反口徑或尚未確認的關鍵缺口？
- 當前市場波動是否可能是在交易單一來源的樂觀或恐慌敘事？

V1 應聚焦於「消息採集、來源分層、預處理、相關度判斷與通知」，而不是擴張成全球新聞終端。行情反查屬於後續版本。

目前系統首先服務個人工作台與個人通知。後續公共出口的方向不是 SaaS 多租戶化，而是把已處理、已去敏、可公開的高價值事件同步到 VPS 承載的公共網站，並由 HomeLab 端的 publisher 發布到 Telegram Channel 與 X。詳細部署邊界請見 [Public Website 架構規劃](./public-website-architecture.md) 與 [部署與使用方式](./deployment.md) 的「公共出口部署方向」。

## 2. 核心價值

黃金的短線劇烈波動常由宏觀、地緣政治、制裁、戰爭風險、能源價格、Fed 預期與美元流動性共同驅動。市場最危險的時刻通常不是「有新聞」，而是不同權力系統釋放出互相矛盾的訊號。

本系統的核心價值是把碎片化、速度不同、立場不同的消息源，整理成一個可回放、可驗證、可分級的事件系統。

典型場景：

```text
Trump tracker:
  Trump 表示 Iran deal 接近完成。

IRNA:
  暫無官方確認。

Tasnim:
  強硬派否認伊朗會放棄濃縮鈾。

SepahNews:
  尚未發聲。

Market:
  XAUUSD 先急跌，隨後快速回拉。

System conclusion:
  市場正在交易 Trump 樂觀預期，但伊朗政府與安全系統尚未確認，反轉風險上升。
```

只要 MVP 能穩定回答這類問題，就已具備實際交易輔助價值。

## 3. MVP 設計原則

### 3.1 分層事件中心

第一版不追求新聞覆蓋率，而是建立「分層事件中心」。每個來源都必須帶有來源群組、官方程度、立場、可靠度、延遲特徵與是否需要確認等資訊。

重點不是收集更多消息，而是知道每一條消息代表誰、能確認什麼、不能確認什麼。

### 3.2 官方確認與高頻提示分離

Telegram 適合突發捕捉，RSS 與官方頁面適合確認與歸檔。

- Telegram：用於第一時間發現 Trump、Iran、IDF、市場 squawk、OSINT 等突發訊號。
- RSS / 官方頁面：用於 Fed、CENTCOM、State Department、Treasury、Tasnim、SepahNews 等較穩定來源的確認與結構化保存。
- MT5 / Market API：後續版本用於 XAUUSD 與相關資產的行情快照，支援「行情先動時反查消息」。

### 3.3 規則先行，AI 輔助

AI 不應自由判斷交易方向，也不應直接輸出做多或做空建議。

MVP 應採用：

```text
規則分級
  + AI 摘要
  + AI 立場辨識
  + AI claim extraction
  + 人工可解釋分數
```

AI 的職責是整理事件，不是下交易指令。

### 3.4 衝突識別優先於單條新聞

系統最重要的能力不是推送單條新聞，而是識別不同權力層級之間的口徑衝突。

例如：

- Trump 宣稱 deal close。
- IRNA 沒有確認。
- Tasnim 或 SepahNews 發出強硬否認。
- Khamenei 系統重申紅線。
- 黃金先跌後反彈。

這種多來源衝突比單一新聞更有交易價值。

## 4. 第一版關注範圍

MVP 應圍繞以下閉環，而不是擴張成綜合新聞系統：

- Trump / Truth Social 相關突發訊號
- Iran government / IRNA 官方口徑
- IRGC-adjacent / Tasnim 強硬派風向
- IRGC official / SepahNews 正式聲明
- Supreme Leader / Khamenei 戰略紅線
- Fed 官方政策與官員發言
- CENTCOM / IDF 軍事升級訊號
- Treasury / OFAC 制裁與能源金融限制
- XAUUSD 異動與可能消息驅動反查，後續版本

## 5. 系統資料流

MVP 的主資料流如下：

```text
Telegram / RSS / Official Pages
  ↓
Collectors
  ↓
raw_items
  ↓
PostgreSQL LISTEN/NOTIFY
  ↓
normalizer-classifier
  ↓
events / event_claims
  ↓
event-router
  ├── alerts
  │     ↓
  │   alert-dispatcher
  │     ↓
  │   private Telegram / Pushover
  └── public_outbox
        ↓
      telegram-channel-publisher / x-publisher / public-syncer
```

關鍵原則：

- PostgreSQL 是 source of truth。
- `raw_items` 保存所有原始採集資料。
- `events` 保存規則與 AI 處理後的標準事件。
- `event_claims` 保存不同來源對同一事件的說法，用於衝突識別。
- `event-router` 負責出口路由判斷，寫入私人通知 queue 與公共發布 outbox。
- `alert-dispatcher` 與各 publisher 只負責 delivery，不再判斷事件應送往哪裡。
- `NOTIFY` 只傳 ID，不傳完整消息內容。
- Redis 與 RabbitMQ 暫不作為 MVP 的可靠事件總線。

## 6. 服務拆分

第一版新聞消息層建議拆成下列主要服務。

### 6.1 telegram-collector

職責：

- 使用 Telethon / MTProto 監聽指定 Telegram channels。
- 接收 `NewMessage`。
- 啟動時回補最近 3-12 小時消息。
- 寫入 `raw_items`。
- 維護 source health。

部署限制：

- 同一個 Telegram user session 只跑一個實例。
- session 檔案需要持久化 volume。
- channel 清單應由 source registry 控制，不應寫死在程式碼中。

### 6.2 rss-collector

職責：

- 定時輪詢 RSS 與官方頁面。
- 支援 `ETag` / `Last-Modified`。
- 解析 title、summary、published、link、guid。
- 寫入 `raw_items`。
- 對 OFAC 等無 RSS 來源使用 HTML polling。

### 6.3 normalizer-classifier

職責：

- 清洗文字。
- 語言辨識。
- 關鍵字匹配。
- 初步事件分類與分級。
- AI 摘要與 claim extraction。
- 寫入 `events` 與 `event_claims`。

第一版應使用可解釋的初篩公式：

```text
source_priority_score
+ keyword_score
+ actor_score
+ market_move_score
- duplicate_penalty
= preliminary_severity
```

### 6.4 event-router

職責：

- 讀取 `events`、`event_claims`、`sources` 與 primary `raw_items`。
- 計算 route score。
- 判斷事件應進入哪些 route。
- 寫入 `alerts`、`public_outbox` 與 `event_route_decisions`。
- 保持私人通知與公共出口的 route policy 可審計。

關鍵原則：

- 決定 `what / where / why`。
- 不呼叫 Telegram / Pushover / X API。
- 不再次呼叫 AI 針對 publisher 改寫內容。
- 不輸出交易指令。

### 6.5 alert-dispatcher

職責：

- claim `alerts` 中的 pending / retry 私人通知。
- 根據 `alerts.message` 與 `alerts.priority` 發送 Telegram / Pushover。
- 記錄推送狀態到 `alerts`。

事件是否應送往 Telegram / Pushover 由 `event-router` 決定；`alert-dispatcher` 只負責 API delivery、retry 與 provider response。

私人通知策略：

| Severity | Telegram | Pushover |
| --- | --- | --- |
| S | yes | high / emergency |
| A | yes | normal |
| B | yes | no |
| C | no | no |

### 6.6 telegram-channel-publisher / x-publisher / public-syncer

職責：

- claim `public_outbox` 或後續 public delivery queue。
- 依平台 API 進行 deterministic formatting。
- 發送到 Telegram Channel、X 或 VPS public API。
- 寫回 delivery state。

Publisher 不判斷事件價值、不讀 raw item 原文補內容、不呼叫 AI。

### 6.7 dashboard-api / dashboard-web

職責：

- 查詢事件時間線。
- 查詢高影響事件。
- 查詢 claim group。
- 查詢 source health。
- 顯示 XAUUSD 異動與消息疊加。

第一版 Dashboard 頁面：

| Page | 用途 |
| --- | --- |
| Live Timeline | 所有事件流 |
| High Impact Events | S / A 級事件 |
| Claim Groups | 同一事件的不同口徑 |
| Market Move Review | 金價異動與消息疊加 |

## 7. 來源分層

MVP 需要從一開始建立來源立場矩陣。這份矩陣應進入 `sources` 表，作為事件分級與衝突識別的基礎。

| Source Group | 代表來源 | 權力層級 | 交易用途 |
| --- | --- | --- | --- |
| `us_trump` | Trump Truth tracker | 美國總統個人口徑 | TACO / deal / sanctions |
| `us_fed` | Fed RSS | 美國央行 | 實際利率與降息預期 |
| `us_military` | CENTCOM / DoD | 美國軍事系統 | 中東軍事升級確認 |
| `us_diplomacy` | State Department | 美國外交系統 | 談判與官方聲明 |
| `us_sanctions` | Treasury / OFAC | 美國財政制裁系統 | 伊朗石油、美元、通膨 |
| `iran_government` | IRNA | 伊朗政府 | 是否承認或否認 Trump 說法 |
| `iran_external_media` | Press TV | 伊朗國家對外傳播 | 快速英文敘事 |
| `iran_irgc_adjacent` | Tasnim | 半官方 / IRGC-linked | 強硬派與安全系統風向 |
| `iran_irgc_official` | SepahNews | IRGC 官方 | 革命衛隊正式口徑 |
| `iran_supreme_leader` | Khamenei.ir | 最高領袖系統 | 核、戰爭、讓步底線 |
| `iran_conservative` | Mehr | 半官方 / 保守派 | 伊朗內部反對訊號 |
| `israel_military` | IDF | 以色列軍方 | 以伊衝突與軍事行動 |
| `israel_diplomacy` | Israel MFA | 以色列外交 | 協議與制裁反應 |
| `market_squawk` | Walter / FinancialJuice / FirstSquawk | 市場聚合 | 第一時間發現市場交易主題 |
| `osint_aggregator` | MES / OSINTdefender | OSINT / 立場聚合 | 早期提示，不作確認 |

## 8. 第一版資料源範圍

### 8.1 Telegram

第一版 Telegram 源不應超過 12 個，以免噪音失控。

建議優先採集：

- `@TrumpTruthSocial_Alert`
- `@Irna_en`
- `@presstv`
- `@Tasnimnews`
- `@enmehrnews`
- `@Khamenei_en`
- `@idfofficial`
- `@israelmfa`
- `@FinancialJuice` 或 `@firstsquaw`
- `@Middle_East_Spectator`
- `@OSINTdefender`

這些來源中，官方與半官方源可進入高權重分級；市場 squawk 與 OSINT 聚合源只作快速提示，通常需要交叉確認。

### 8.2 RSS / 官方頁面

第一版 RSS 與官方頁面來源：

- Fed RSS
- CENTCOM RSS / Press Releases
- State Department RSS
- Tasnim RSS
- SepahNews RSS
- Mehr RSS
- Press TV RSS / page
- Treasury Press Releases
- OFAC Recent Actions via HTML polling
- Jerusalem Post Iran / Middle East RSS

### 8.3 Market Data，後續版本

後續版本行情指標：

- XAUUSD
- DXY
- US10Y
- US02Y
- WTI / Brent
- VIX
- Fed rate probability，如果 API 可用

## 9. 事件分級

MVP 使用 S / A / B / C 四級事件。

| Severity | 含義 | 推送 |
| --- | --- | --- |
| S | 可能立即改變 XAUUSD 方向或風險定價 | Telegram + Pushover high / emergency |
| A | 未來數小時可能影響交易邏輯 | Telegram + Pushover normal |
| B | 背景資訊或待確認消息 | Telegram |
| C | 歸檔事件 | 不推送 |

S 級候選條件：

- Trump 直接宣布 deal、no deal、sanctions、military action，且包含原始連結。
- IRNA / Tasnim / SepahNews / Khamenei 與 Trump 說法直接矛盾。
- CENTCOM / IDF 宣布軍事行動。
- SepahNews / Tasnim 提到導彈、報復、霍爾木茲、封鎖。
- Fed 主席或重點官員發表明顯鷹派或鴿派轉向。
- Treasury / OFAC 發布重大伊朗或能源制裁。
- 油價或金價在短時間內異常波動，同時存在相關消息。

## 10. Claim Groups 與衝突識別

系統需要把不同來源對同一事件的說法掛到同一個 claim group 下。

示例：

```text
claim_group_id: iran_deal_2026_05_30_001

Trump tracker:
  claim_direction: confirm
  claim_text: Iran agreed to deal.

Tasnim:
  claim_direction: deny
  claim_text: Iran rejects giving up enrichment.

IRNA:
  claim_direction: neutral
  claim_text: No official confirmation.
```

Claim group 是系統回答「市場是否正在交易單邊敘事」的關鍵資料結構。

## 11. 金價異動反查，後續版本

後續版本中，系統不應只在新聞出現時推送，也應在行情先動時主動反查。

觸發條件示例：

```text
if XAUUSD moves > 0.6% in 5 minutes
or XAUUSD moves > 1.0 ATR(5m) in 3 candles
then:
  scan raw_items/events from last 45 minutes
  rank by source priority + keyword relevance
  send possible drivers alert
```

輸出應包含：

- XAUUSD 波動幅度與時間窗。
- 最近 45 分鐘可能相關的消息。
- 哪些來源已確認。
- 哪些來源尚未確認。
- 是否存在反向口徑。
- 初步解讀，但不輸出交易指令。

## 12. 資料庫核心實體

MVP 應至少包含以下表：

- `sources`：來源註冊、立場、官方程度、可靠度、延遲、是否啟用。
- `raw_items`：所有 Telegram / RSS / HTML polling 原始資料。
- `events`：標準化事件與分級結果。
- `event_claims`：同一事件下不同來源的 claim。
- `market_snapshots`：XAUUSD 與關聯市場行情快照，V1 暫緩。
- `alerts`：推送紀錄與 delivery status。

後續資料庫設計文件應詳細定義 schema、index、unique constraint、dedupe strategy 與 migration 策略。

## 13. 部署拓撲

長期部署拓撲：

```text
Windows Machine
  └── mt5-collector
        └── internal ingest API or restricted PostgreSQL user

Linux HomeLab Server
  ├── PostgreSQL
  ├── telegram-collector
  ├── rss-collector
  ├── normalizer-classifier
  ├── alert-dispatcher
  ├── dashboard-api
  └── dashboard-web

Optional
  ├── Redis
  └── AI inference / API worker
```

MT5 collector 在 V1 暫緩。後續實作時可以先直連 PostgreSQL，但應使用專用 DB user，只允許 insert `market_snapshots`，不給 `drop` / `alter` 權限。更建議改為：

```text
MT5 collector → internal ingest API → PostgreSQL
```

## 14. 非目標

MVP 不包含以下能力：

- 自動交易。
- 交易方向建議。
- 全球新聞全量監控。
- 多策略回測系統。
- 完整機器可讀 Reuters / AP 商業新聞流。
- 複雜分散式 queue 架構。
- 多 Telethon session 水平擴展。

這些能力可作為後續版本評估，但不應進入第一版。

## 15. 後續文件規劃

Overview 之後，建議依序補齊以下文件：

1. `docs/sources.md`：Telegram、RSS、官方頁面與 market data 的來源清單、立場矩陣與採集策略。
2. `docs/event-model.md`：事件類型、severity、confirmation state、impact channel、claim group 規則。
3. `docs/database-schema.md`：PostgreSQL schema、index、constraint、dedupe key、migration 策略。
4. `docs/services.md`：各服務職責、輸入輸出、重試策略、health check。
5. `docs/alerts.md`：Telegram / Pushover 訊息格式、優先級與降噪規則。
6. [docs/deployment.md](./deployment.md)：HomeLab、Docker Compose、GHCR image、volume、secret、network 與備份策略。
7. [docs/project-structure.md](./project-structure.md)：monorepo 目錄結構、service mapping 與 GHCR image mapping。
