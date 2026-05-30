# alert-dispatcher 功能需求

## 1. 服務定位

`alert-dispatcher` 是 V1 的通知出口服務，負責根據 `events`、relevance score、severity、source priority 與通知規則，將高價值消息發送到 Telegram Bot 與 Pushover。

此服務只負責通知決策與發送，不負責採集、AI 分析或交易判斷。

## 2. V1 目標

- 監聽 `event_created` notification 或輪詢 pending alert tasks。
- 讀取 `events`、`sources`、`event_claims`，以及必要的 `raw_items`。
- 根據規則判斷通知 channel。
- 格式化 Telegram / Pushover message。
- 發送通知。
- 寫入 `alerts` delivery status。
- 支援 alert dedupe，避免同一事件重複打擾。
- 發送失敗可 retry。

## 3. 非目標

V1 不包含：

- 使用者偏好 UI。
- 多使用者權限模型。
- 複雜 escalation policy。
- 排班。
- 通知中心前端。
- 交易指令。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | V1 主語言 |
| HTTP client | httpx | Telegram Bot API / Pushover REST |
| Database | PostgreSQL 16+ | 讀 events、寫 alerts |
| DB driver | psycopg 3 / asyncpg | 支援 task locking |
| Config | pydantic-settings | env 管理 |
| Logging | structlog / standard logging | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab 部署 |

Go 可作為後續備選，適合單 binary 通知 worker。

## 5. 輸入與輸出

輸入：

- `events`
- `sources`
- `event_claims`，如果 V1 有建立
- `raw_items`
- `event_created` notification 或 `alert_tasks`

輸出：

- Telegram Bot message
- Pushover message
- `alerts` rows

## 6. 通知決策

初始規則：

| 條件 | Telegram | Pushover |
| --- | --- | --- |
| `relevance_score >= 85` 且來源 P0 / P1 | yes | yes |
| `relevance_score >= 70` | yes | no |
| `severity = S` | yes | high / emergency |
| `severity = A` | yes | normal |
| `severity = B` | yes | no |
| `severity = C` | no | no |
| OSINT / aggregator 單源消息 | yes | no |
| duplicate / near-duplicate | merge / skip | no |

`Pushover emergency` 需要保守使用。V1 建議只在明確 P0 官方或半官方高風險事件時使用。

## 7. Alert Dedupe

需要避免同一事件重複推送。

建議 dedupe key：

```text
alert:{event_id}:{channel}
```

可選近似去重：

```text
alert:{event_type}:{source_group}:{normalized_title_hash}:{time_bucket}
```

規則：

- 同一 `event_id` 同一 channel 只發送一次。
- retry 不產生新 alert row，應更新原 row status 或 attempt count。
- near-duplicate event 可由 normalizer 先合併，dispatcher 只做最後防線。

## 8. Telegram Message 格式

Telegram message 需要短、可掃描、可人工驗證。

範例：

```text
[A] IRAN_NUCLEAR | relevance 86

Tasnim 否認伊朗將放棄濃縮鈾的說法。

Source: Tasnim (@Tasnimnews)
Group: iran_irgc_adjacent
Official: semi_official
Confirmation: requires confirmation

Impact: safe_haven, oil_inflation
URL: https://...
```

要求：

- 顯示 severity。
- 顯示 event type。
- 顯示 relevance score。
- 顯示 summary_zh。
- 顯示 source name / group / official level。
- 顯示是否需要 confirmation。
- 有 URL 時提供 URL。
- 不輸出交易指令。

## 9. Pushover Message 格式

Pushover 更短，用於快速提醒。

Title：

```text
[A] IRAN_NUCLEAR relevance 86
```

Message：

```text
Tasnim 否認伊朗將放棄濃縮鈾的說法。
Source: Tasnim
Requires confirmation.
```

Priority mapping：

| Severity | Pushover priority |
| --- | --- |
| S | 1 or 2 |
| A | 0 |
| B | no pushover |
| C | no pushover |

V1 若使用 priority 2 emergency，必須設定 retry / expire，並限制觸發條件。

## 10. Alerts Table

建議欄位：

```text
id
event_id
channel                  telegram / pushover
priority                 normal / high / emergency
dedupe_key
message
sent_at
delivery_status          pending / sent / failed / skipped
attempt_count
next_retry_at
provider_response_json
error_message
created_at
updated_at
```

Unique：

```text
unique(dedupe_key)
```

## 11. 錯誤處理

| 類型 | 處理方式 |
| --- | --- |
| Telegram rate limit | respect retry-after，retry |
| Telegram chat not found | mark failed，需人工修設定 |
| Pushover API error | retry if transient |
| DB connection failed | retry |
| message formatting failed | mark failed，保存 error |
| duplicate alert | mark skipped |

Retry：

```text
max_attempts = 3
initial_backoff = 10s
max_backoff = 300s
```

## 12. 設定項

```text
APP_ENV=development
SERVICE_NAME=alert-dispatcher
DATABASE_URL=postgresql://...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
PUSHOVER_EMERGENCY_RETRY_SECONDS=60
PUSHOVER_EMERGENCY_EXPIRE_SECONDS=600
POLL_INTERVAL_SECONDS=2
LOG_LEVEL=INFO
```

Secrets 不得提交到 repo。

## 13. Observability

Metrics：

- pending alert count
- sent count by channel
- failed count by channel
- skipped duplicate count
- provider latency
- retry count

Logs：

- `event_id`
- `alert_id`
- `channel`
- `priority`
- `delivery_status`
- `provider_status_code`
- `error_type`

## 14. 測試需求

單元測試：

- notification decision rules。
- Telegram formatter。
- Pushover formatter。
- dedupe key generation。
- priority mapping。

整合測試：

- mock Telegram Bot API。
- mock Pushover API。
- failed retry。
- duplicate skip。
- alerts table status update。

## 15. 驗收標準

- 高相關事件能按規則發送 Telegram / Pushover。
- 中等相關事件只發 Telegram。
- 低相關事件不發送。
- OSINT 單源不發 Pushover。
- 同一事件同一 channel 不重複發送。
- 發送結果完整寫入 `alerts`。
- provider 失敗可 retry。
- 通知內容不包含交易指令。

