# Services

本目錄保存 XAUUSD Event Radar MVP 各服務的功能需求、技術棧、資料流、設定、測試與驗收標準。

所有服務文件使用繁體中文。程式碼、設定鍵、資料表、API、套件名稱與技術名詞保留英文。

V1 目前專注新聞消息層，完整範圍請見 [最終目標與 V1 實作範圍](../final-target-and-v1-scope.md)。

## 服務文件

| Service | 文件 | 狀態 |
| --- | --- | --- |
| `telegram-collector` | [telegram-collector.md](./telegram-collector.md) | 已建立 |
| `rss-collector` | [rss-collector.md](./rss-collector.md) | 已建立 |
| `normalizer-classifier` | [normalizer-classifier.md](./normalizer-classifier.md) | 已建立 |
| `alert-dispatcher` | [alert-dispatcher.md](./alert-dispatcher.md) | 已建立 / runtime 已實作 |
| `telegram-channel-publisher` | [telegram-channel-publisher.md](./telegram-channel-publisher.md) | 後續公共出口 / runtime skeleton 已實作 |
| `x-publisher` | [x-publisher.md](./x-publisher.md) | 後續公共出口 / 已建立 |
| `dashboard-api` | [dashboard-api.md](./dashboard-api.md) | V1 可選 / 已建立 |
| `dashboard-web` | [dashboard-web.md](./dashboard-web.md) | V1 可選 / 已建立 |
| `mt5-collector` | `mt5-collector.md` | V1 暫緩 |

## 技術棧基準

後端服務優先使用：

- Python 3.12+
- PostgreSQL 16+
- Docker
- structured logging
- environment-based configuration

Go 可作為後續備選，適用於需要單 binary 部署、高併發或更低 runtime footprint 的服務。

前端服務統一使用：

- React Router V7
- TanStack Query
- TailwindCSS V4
- DaisyUI V5
