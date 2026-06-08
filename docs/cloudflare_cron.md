# Cloudflare Cron 設定

## 先在 Supabase 建資料表

到 Supabase SQL Editor 執行：

```text
backend/sql/migrations/20260609_account_snapshots.sql
```

這會建立 `account_snapshots`，每小時會存：

- 每個帳戶的總額
- 快照時間 `snapshot_at`
- 快照日期 `snapshot_date`
- 快照小時 `snapshot_hour`
- TWD 換算總額
- 股票市值
- 現金
- 投入金額
- 已實現/未實現損益
- 配置 JSON
- 原始 summary payload

## Vercel 環境變數

在 Vercel 專案加：

```env
CRON_SECRET=一組很長的隨機密碼
```

部署後可以用這兩個 API：

```text
POST https://stock-web-gamma.vercel.app/api/jobs/refresh
POST https://stock-web-gamma.vercel.app/api/jobs/snapshot
```

Header 都要帶：

```text
X-Cron-Secret: 同一組 CRON_SECRET
```

## Cloudflare Worker

建立 Worker，貼上：

```text
cloudflare/cron-worker/worker.js
```

手動測試 Worker URL 時也要帶 header：

```text
X-Cron-Secret: 同一組 CRON_SECRET
```

設定 Worker Variables/Secrets：

```text
API_BASE=https://stock-web-gamma.vercel.app/api
CRON_SECRET=同一組 CRON_SECRET
```

## Cron Triggers

Cloudflare cron 是 UTC。

新增四個 trigger：

```text
0 * * * *
10,20,30,40,50 1 * * *
30,40,50 13 * * *
10,20,30 14 * * *
```

意思是：

- `0 * * * *`：每小時整點觸發。Worker 會在允許的整點刷新價格與 summary cache，並寫入一筆 hourly asset snapshot。
- `10,20,30,40,50 1 * * *`：台北時間 09:10、09:20、09:30、09:40、09:50 只刷新，不寫 snapshot。
- `30,40,50 13 * * *`：台北時間 21:30、21:40、21:50 只刷新，不寫 snapshot。
- `10,20,30 14 * * *`：台北時間 22:10、22:20、22:30 只刷新，不寫 snapshot。

台北時間 09:00、10:00、22:00 會由每小時整點 trigger 處理，所以不需要另外加，避免同一分鐘重複觸發。

Worker 會自動略過這兩段台北時間：

- 04:00 到 08:00
- 14:30 到 20:30

非整點觸發會呼叫：

```text
POST /api/jobs/refresh
```

整點觸發會呼叫：

```text
POST /api/jobs/snapshot
```

所以資料表只會保留整點 snapshot；其他 10 分鐘觸發只會更新即時價格與 summary cache。
