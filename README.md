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

請先複製 `.env.example` 成根目錄的 `.env`，並填入 Supabase 與 Finnhub 設定。

## 需要提供的設定

你不需要把 key 貼在聊天裡。請在本機 `.env` 或部署平台環境變數填入：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `FINNHUB_KEY`
- `FUGLE_API_KEY`

Supabase 需要先建立 `trades`、`manual_values`、`price_cache`、`cash_accounts`、`manual_investments`，欄位可參考 `backend/sql/schema.sql`。

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
