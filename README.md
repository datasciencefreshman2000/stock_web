# stock_web

個人投資組合追蹤系統。前端使用 React + Vite，後端使用 FastAPI，資料存在 Supabase，股價與匯率由 Finnhub 取得。

## 專案結構

```text
backend/    FastAPI 後端、Supabase repository、股價服務
frontend/   React + Vite 前端
org_data/   原始 Google Sheets 匯出 CSV，用來比對資料
docs/       專案規格與設計紀錄
```

## 本地開發

後端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

> 新增了 `@tanstack/react-query` 相依，第一次拉到這版請務必先跑一次 `npm install`。

請先複製 `.env.example` 成根目錄的 `.env`，並填入 Supabase 與 Finnhub 設定。

## 網站登入

所有 `/api/*` 端點（除了 `/api/health`）都需要登入。**未設定認證時 API 會一律回 503**，
不會在沒有保護的狀態下對外提供資料。

產生密碼雜湊與 JWT secret：

```bash
cd backend
python scripts/hash_password.py
```

把輸出的 `APP_PASSWORD_HASH` 與 `JWT_SECRET` 填進 `.env` 與 Vercel 環境變數。
本機開發若不想每次登入，可設 `AUTH_DISABLED=true`（**絕對不要**設在正式環境）。

## 資料刷新流程

刷新責任集中在排程與手動刷新端點，所有 GET 端點一律只讀快取：

| 端點 | 誰呼叫 | 做什麼 |
|------|--------|--------|
| `POST /api/jobs/refresh` | Cloudflare cron / 前端刷新按鈕 | 抓最新報價、重算、寫快取 |
| `POST /api/jobs/snapshot` | Cloudflare cron（整點） | 同上 + 寫入 `account_snapshots` |
| `POST /api/jobs/settle` | Cloudflare cron（03:00 / 15:00） | FIFO checkpoint 結算（12 小時內有異動才做） |
| `GET /api/jobs/status` | 除錯用 | 各排程最後執行狀況 |

排程端點接受 `X-Cron-Secret` 或使用者 JWT。

## 需要提供的設定

你不需要把 key 貼在聊天裡。請在本機 `.env` 或部署平台環境變數填入：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `FINNHUB_KEY`
- `FUGLE_API_KEY`
- `APP_PASSWORD_HASH`、`JWT_SECRET`（見上方「網站登入」）
- `CRON_SECRET`

Supabase 需要先建立 `trades`、`manual_values`、`price_cache`、`cash_accounts`、`manual_investments`，欄位可參考 `backend/sql/schema.sql`。

## 測試

```bash
cd backend
python -m pytest tests/ -q
```

`tests/test_settlement.py` 有一條關鍵不變式：**從 checkpoint 續算的結果必須等於全量重算**。
只要這條測試通過，FIFO checkpoint 就只是效能優化，不會影響金額正確性。

## Supabase 連線方式

1. 到 Supabase 專案的 SQL Editor。
2. 執行 `backend/sql/schema.sql` 建立資料表；舊資料庫則依序補跑 `backend/sql/migrations/` 內的 SQL。
3. 到 Settings → API 複製 Project URL 與 service_role key。
4. 寫入根目錄 `.env`：

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
FINNHUB_KEY=your_finnhub_api_key
FUGLE_API_KEY=your_fugle_api_key
```

後端健康檢查：

```bash
cd backend
..\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from main import app; print(TestClient(app).get('/api/health').json())"
```

實際執行後端：

```bash
cd backend
..\.venv\Scripts\uvicorn.exe main:app --reload --port 8000
```

## Finnhub 測試

填好 `FINNHUB_KEY` 後，美股會用 Finnhub 報價。若要先測單一代號，可用瀏覽器打：

```text
https://finnhub.io/api/v1/quote?symbol=NVDA&token=你的_FINNHUB_KEY
```

如果回傳 JSON 裡 `c` 有數字，代表目前價格可用。

## Fugle 台股報價

台股與 `x` 帳戶使用 Fugle，請在 `.env` 填入：

```env
FUGLE_API_KEY=your_fugle_api_key
```

後端會用 `fugle-marketdata` 的 `client.stock.intraday.quote(symbol="2330")` 取得 `lastPrice`。台股與 `x` 帳戶若有重複標的，同一次刷新只會抓一次，並寫入 Supabase `price_cache`。
