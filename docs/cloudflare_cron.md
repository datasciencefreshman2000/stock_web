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

新增兩個 trigger：
新增一個 trigger：

```text
0 * * * *
```

意思是：

- 每小時整點刷新價格與 summary cache，並寫入一筆 hourly asset snapshot。
