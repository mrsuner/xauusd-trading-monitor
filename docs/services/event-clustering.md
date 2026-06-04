# event-clustering / semantic dedupe 設計草案

## 1. 定位

`event-clustering` 是 `normalizer-classifier` 與 `event-router` 之間的語義合併層。它的目標不是判斷消息是否重要，而是把多個來源對同一事件或同一 claim 的報導合併到同一個 canonical event，避免重複廣播，並利用多來源 claim 更新 `confirmation_state`。

V1 runtime 目前尚未實作此層。本文檔先作為 V1.5 / V2 的實作設計，短期先修復官方 RSS / HTML 採集，再評估落地。

目標資料流：

```text
raw_items
  ↓
normalizer-classifier
  ↓ proposed event + event_claim
event-clustering
  ├── create new canonical event
  └── merge into existing canonical event
        ├── append raw_item_ids
        ├── insert event_claims
        ├── update confirmation_state
        └── update relevance/severity if materially upgraded
  ↓
event-router
  ↓
alerts / public_outbox
```

## 2. 要解決的問題

### 2.1 來源偏見不等於低價值

部分來源有明確官方態度或派系立場，例如 Iranian state / semi-official / IRGC-adjacent Telegram channels。這些來源可能誇大、選擇性呈現或使用政治敘事，但它們仍然有高價值：

- 代表官方或派系對談判、軍事升級、核議題、制裁的 stance signal。
- 在市場關注特定敘事時，立場本身就是價格敏感資訊。
- 當同一來源過去在特定主題上有 predictive value，不應用單純 `official_level` 或 `requires_confirmation` 將其完全壓低。

因此系統應分離兩種分數：

| 概念 | 說明 | 主要用途 |
| --- | --- | --- |
| `event_relevance_score` | 消息對 XAUUSD / 地緣 / Fed / 制裁 / 能源是否重要 | 是否進事件流、是否 private alert |
| `fact_confidence` / `confirmation_state` | claim 是否被可靠且獨立來源確認 | public route、Pushover emergency、公開語氣 |

高 relevance 可以來自 biased source；高 fact confidence 應來自 source diversity、official confirmation 或後續驗證。

### 2.2 現有去重邊界不足

現有 runtime 的去重主要是單一 raw item / 單一 event 層級：

- `raw_items.dedupe_key` 避免同一 collector item 重複入庫。
- `events.dedupe_key` 目前可由單一 raw item 派生。
- `alerts.dedupe_key = alert:{event_id}:{channel}` 避免同一 event 在同一 channel 重複通知。
- `public_outbox` 以 `event_id` unique，避免同一 event 重複進公共出口。
- `event_route_decisions` 以 `(event_id, route_key)` unique。

這無法處理「不同來源報導同一事件」：

```text
Tasnim reports claim A
Press TV reports claim A
IRNA reports claim A
FinancialJuice repeats claim A
```

若每筆 raw item 都建立獨立 `events` row，下游會把它們視為不同事件，導致 Telegram Channel / X / private alerts 多次廣播相同主題。

## 3. 設計原則

### 3.1 先合併 claim，再做廣播

`event-router` 應只處理 canonical event。若新 raw item 命中既有 event cluster，預設只更新既有 event，不重新建立 public outbox。

例外情況：

- severity 從 `A` 升級為 `S`。
- `confirmation_state` 從 `unconfirmed` 升級為 `confirmed`，且策略允許發出「確認更新」。
- 新來源提供了相反 claim，導致 `contradicted`，且事件本身足夠重要。

上述情況也應走明確的 route policy，而不是讓每筆補充報導自然重複發布。

### 3.2 保留來源立場，不把 biased source 當成錯誤

`event_claims` 應保存每個來源自己的 claim、stance、claim_direction 與 confidence。系統可以標記「Tasnim 稱」「Press TV 表示」，但不應在未確認時把 claim 改寫成系統事實。

Public copy 原則：

| confirmation_state | 建議語氣 |
| --- | --- |
| `unconfirmed` | 「某來源稱」「尚待確認」 |
| `partially_confirmed` | 「多個來源稱」「仍待官方/獨立確認」 |
| `confirmed` | 「官方確認」「多方確認」 |
| `contradicted` | 「說法互相矛盾」「需留意後續確認」 |

### 3.3 source diversity 比 source count 更重要

同一派系或同一媒體生態的多個來源不應直接等同獨立確認。

確認強度應看：

- `source_group` diversity。
- `official_level`。
- 是否同屬 aggregator / mirror。
- 是否引用同一上游來源。
- claim direction 是否一致。
- 時間間隔是否合理。

例如：

```text
Tasnim + Press TV
```

可以提升 attention，但不一定是 confirmed，因為兩者都可能屬於 Iranian official / semi-official narrative ecosystem。

```text
Tasnim + IRNA + CENTCOM / State / IAEA / Israeli official
```

則可以顯著提升 confirmation 或標記 contradiction。

## 4. Semantic Cluster Key

### 4.1 初始 deterministic key

V1.5 可以先不引入 embedding，使用 normalized fields 生成候選 key：

```text
semantic_cluster_key =
  event_type
  + normalized_region
  + normalized_primary_actor
  + normalized_secondary_actor
  + normalized_claim_direction
  + normalized_topic_key
  + time_bucket
```

建議 time bucket：

| event_type | time_bucket |
| --- | --- |
| `US_FED` | 24h |
| `US_SANCTIONS` | 24h |
| `US_MILITARY` | 6h |
| `IRAN_GOVERNMENT` / `IRAN_IRGC` | 6h |
| `IRAN_NUCLEAR` | 12h |
| `MARKET_SQUAWK` | 1h |
| `OTHER_RELEVANT_NEWS` | 3h |

### 4.2 候選查詢

新 raw item 產生 proposed event 後，先查最近候選：

```sql
select e.*
from events e
where e.event_type = :event_type
  and coalesce(e.region, '') = coalesce(:region, '')
  and e.detected_at >= :window_start
order by e.detected_at desc
limit 20;
```

再用 deterministic similarity 計算：

- actor overlap。
- topic tag overlap。
- title / claim trigram similarity。
- claim_direction 是否一致。
- source_group 是否不同。

命中門檻建議：

```text
same event if:
  event_type same
  actor overlap strong
  topic overlap moderate
  claim similarity >= 0.72
  published/detected time within event_type window
```

### 4.3 後續 embedding

如果 deterministic key 誤判太多，再引入 embedding 或 LLM reranker。embedding 只用於「候選是否同一事件」判斷，不應用來覆蓋 structured source / claim metadata。

## 5. 合併行為

### 5.1 命中新 cluster 時

若新 raw item 不屬於既有 cluster：

- 建立 `events`。
- 設定 `dedupe_key = semantic:{semantic_cluster_key}`。
- `raw_item_ids = [raw_item.id]`。
- 插入第一筆 `event_claims`。
- `confirmation_state` 依 source policy 預設為 `unconfirmed` 或 `partially_confirmed`。

### 5.2 命中既有 cluster 時

若新 raw item 屬於既有 event：

- append `raw_item.id` 到 `events.raw_item_ids`，避免重複。
- 插入新的 `event_claims`。
- 更新 `events.relevance_score = greatest(existing, new)`。
- 若新 severity 更高，更新 `events.severity`。
- 更新 `events.confirmation_state`。
- 優先保留 canonical summary，不因 aggregator 重述覆蓋官方來源摘要。

建議更新 SQL 形態：

```sql
update events
set raw_item_ids = (
      select array_agg(distinct id)
      from unnest(events.raw_item_ids || :raw_item_id::uuid) as id
    ),
    relevance_score = greatest(events.relevance_score, :new_relevance_score),
    severity = :upgraded_severity,
    confirmation_state = :new_confirmation_state,
    updated_at = now()
where id = :event_id;
```

## 6. Confirmation State Policy

### 6.1 source group classification

建議將來源分成可配置類別，可先放在 `sources.source_config`：

```json
{
  "stance_signal": true,
  "confirmation_role": "primary_claim|supporting|aggregator|mirror|official_confirmation",
  "narrative_cluster": "iran_state|iran_irgc|us_government|israel_government|market_aggregator"
}
```

### 6.2 狀態轉移

初始規則：

| 條件 | confirmation_state |
| --- | --- |
| 單一 `requires_confirmation=true` source | `unconfirmed` |
| 多個同 narrative cluster 來源一致 | `partially_confirmed` |
| 至少兩個獨立 narrative cluster 一致，且其中一個為 official/semi_official | `confirmed` |
| aggregator / mirror 重述，不含原始官方連結 | 不提升或最多 `partially_confirmed` |
| 不同 narrative cluster 出現相反 claim | `contradicted` |
| official source 發布直接確認，且 source configured as `official_confirmation` | `confirmed` |

### 6.3 contradiction handling

若新 claim 與既有 cluster claim direction 相反：

- 不建立新 cluster，除非它描述不同事件。
- 插入 `event_claims`，`claim_direction` 保留相反方向。
- `events.confirmation_state = 'contradicted'`。
- public copy 必須保留矛盾狀態，例如「伊朗媒體否認，美方來源尚未確認」。

## 7. 重複廣播控制

### 7.1 下游 idempotency 保持 event-level

下游不需要直接理解 semantic dedupe。只要 `event-clustering` 保證同一語義事件共用同一 `events.id`，現有邊界即可繼續工作：

- `alerts.dedupe_key = alert:{event_id}:{channel}`。
- `public_outbox` unique by `event_id`。
- `event_route_decisions` unique by `(event_id, route_key)`。

### 7.2 Update route

後續可新增更新型 route：

```text
private.telegram_update
public.telegram_channel_update
public.x_update
```

但 V1.5 建議先不做更新型公共廣播，只在 Dashboard / public website 顯示同一 event 的 source count、latest confirmation 與 claim history。

## 8. Schema 建議

### 8.1 最小改動

短期可沿用：

- `events.raw_item_ids uuid[]`
- `events.dedupe_key`
- `events.confirmation_state`
- `event_claims`

新增欄位：

```sql
alter table events add column semantic_cluster_key text;
alter table events add column source_group_count integer not null default 1;
alter table events add column claim_count integer not null default 1;
alter table events add column latest_claim_at timestamptz;
```

索引：

```sql
create index events_semantic_cluster_key_idx
  on events (semantic_cluster_key)
  where semantic_cluster_key is not null;
```

### 8.2 較完整版本

若 `raw_item_ids uuid[]` 開始變複雜，新增 bridge table：

```sql
create table event_raw_items (
  event_id uuid not null references events(id) on delete cascade,
  raw_item_id uuid not null references raw_items(id) on delete cascade,
  relation_type text not null default 'supporting',
  created_at timestamptz not null default now(),
  primary key (event_id, raw_item_id)
);
```

後續也可新增：

```sql
create table event_clusters (
  id uuid primary key default gen_random_uuid(),
  semantic_cluster_key text not null,
  canonical_event_id uuid references events(id),
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## 9. 實作順序

建議不要立刻實作。先做官方 RSS / HTML 修復，讓 confirmation source 可用。

推薦順序：

1. 修復官方 RSS / HTML source health，例如 Treasury、OFAC、State Department、CENTCOM、Tasnim RSS、Sepah News。
2. 在 Dashboard / SQL 中觀察 3-7 天：同一事件是否多 source 重複建 event。
3. 加入 `semantic_cluster_key` deterministic helper 與單元測試。
4. 在 `normalizer-classifier` 的 `_insert_event` 前加入 candidate lookup。
5. 命中 cluster 時改為 merge event + insert claim。
6. 更新 `event-router` route policy，只對 canonical event 進行公共發送。
7. 補 Dashboard 顯示：source count、claim count、confirmation state、supporting sources。

## 10. 驗收標準

- 同一 claim 被 Tasnim、Press TV、IRNA 先後發出時，只建立一個 canonical event。
- `events.raw_item_ids` 或 `event_raw_items` 能看到所有 supporting raw items。
- `event_claims` 保留每個來源的原始 claim direction / stance。
- `public_outbox` 同一事件只建立一筆。
- `confirmation_state` 能從 `unconfirmed` 升級為 `partially_confirmed` / `confirmed`，也能在相反 claim 出現時變為 `contradicted`。
- Aggregator / mirror source 不會單獨把事件升級為 confirmed。
- Biased but useful source 可以保持高 relevance，但公開文案不把其 claim 當成已確認事實。
