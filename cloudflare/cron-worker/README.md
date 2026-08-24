# Cloudflare Cron Worker

This Worker keeps the existing Vercel FastAPI backend as the source of truth.

## 目前排程（UTC）

```
0 * * * *              每小時整點 → 整點寫 snapshot，其餘 refresh
10,20,30,40,50 1 * * * 台北 09:10–09:50
30,40,50 13 * * *      台北 21:30–21:50
10,20,30 14 * * *      台北 22:10–22:30
```

Worker 會把排定時間換算成台北時間，並跳過台北 04:00–08:00 與 14:30–20:30。

### 換算成台北時間，實際觸發點長這樣

```
00:00  01:00  02:00  03:00                    每 60 分
09:00  09:10  09:20  09:30  09:40  09:50      每 10 分  ← 開盤
10:00  11:00  12:00  13:00                    每 60 分  ← ⚠ 盤中空窗
14:00  15:00
21:00  21:30  21:40  21:50                              ← 美股開盤
22:00  22:10  22:20  22:30
23:00
```

**已知缺口**：台股交易時間是 09:00–13:30，但 09:50 之後就只剩整點更新。
所以在 12:30 看盤，資料會是 12:00 的。

要驗證排程有沒有照你想的跑，可以直接模擬：

```bash
node -e "
const {readFileSync}=require('fs');
// 見 docs/cache_and_refresh.md 的模擬腳本
"
```

## 要改哪一條

**只改 `10,20,30,40,50 1 * * *` 這一條，其他三條都別動。**

```
10,20,30,40,50 1 * * *      ← 改成 ↓
5-55/5 1-5 * * *            台北 09:05–13:55，每 5 分鐘
```

`1` 改成 `1-5`（UTC 01–05 = 台北 09–13）就把整個台股盤中補滿了。
分鐘從 `5` 起跳、不含 `0`，是為了**避開 `0 * * * *` 的整點**——
兩條 cron 撞在同一分鐘會讓 Worker 被叫兩次，白花一次全站重算。

| | 盤中觸發次數 | 最大空窗 |
|---|---:|---:|
| 現在 | 10 次 | 60 分鐘 |
| 改後 | 55 次 | 5 分鐘 |

另外三條維持原樣的理由：

- `0 * * * *` —— 整點 snapshot，寫 `account_snapshots` 歷史，不能拿掉
- `30,40,50 13 * * *` / `10,20,30 14 * * *` —— 美股開盤，跟台股無關

⚠ **改 cron 之前必讀**：後端有 `PRICE_REFRESH_TTL_SECONDS`（預設 600 秒）。
價格快取只要還在有效期內，就算排程觸發也**不會**去打外部 API。

所以 cron 每 5 分鐘 + TTL 600 秒 = 實際仍是 10 分鐘才更新一次。
兩者要一起調：

```env
PRICE_REFRESH_TTL_SECONDS=240    # 4 分鐘，配合 5 分鐘的 cron
```

### 額度確認

| | |
|---|---|
| Fugle 免費方案 | 60 次/分鐘 |
| 每次刷新用掉 | 約 21 次（台股標的數） |
| 台股盤中每 5 分鐘 | 一天 55 次刷新 |

完全在額度內。

Supabase 這邊：一次 `/jobs/refresh` 現在是 **14 次往返**（先前 35 次，
因為 summary 與三個 portfolio 各自把同一份 FIFO 重算了一遍）。
55 次 × 14 ≈ 一天 770 次，免費方案綽綽有餘。

## 在哪裡改

Cron 觸發器設定在 **Cloudflare Dashboard → Workers → 你的 Worker → Settings → Triggers → Cron Triggers**，
不在這個 repo 裡（沒有 `wrangler.toml`）。

`PRICE_REFRESH_TTL_SECONDS` 設在 **Vercel → Settings → Environment Variables**。

## Worker 變數

```text
API_BASE=https://stock-web-gamma.vercel.app/api
CRON_SECRET=<same value as Vercel CRON_SECRET>
```

## 後端端點

```text
POST /api/jobs/refresh    抓價 + 重算 + 寫快取
POST /api/jobs/snapshot   同上 + 寫入 account_snapshots
POST /api/jobs/settle     FIFO checkpoint 結算（台北 03:00 / 15:00）
GET  /api/jobs/status     各排程最後執行狀況 ← 想確認排程有沒有在跑就打這個
```

全部需要：

```text
X-Cron-Secret: <CRON_SECRET>
```

## 手動測試

```text
https://<worker-name>.<your-subdomain>.workers.dev/refresh
https://<worker-name>.<your-subdomain>.workers.dev/snapshot
https://<worker-name>.<your-subdomain>.workers.dev/settle
```
