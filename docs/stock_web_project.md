# stock_web — 投資組合追蹤系統

> 給 AI Coding Agent（Codex）的完整專案規格文件  
> 架構：React 前端 + FastAPI 後端，部署在同一個 Vercel 專案  
> 請完整閱讀後再開始撰寫任何程式碼

---

## 目錄

1. [專案概述](#1-專案概述)
2. [技術架構](#2-技術架構)
3. [資料夾結構](#3-資料夾結構)
4. [資料庫結構（Supabase）](#4-資料庫結構supabase)
5. [後端規格（FastAPI）](#5-後端規格fastapi)
6. [前端規格（React）](#6-前端規格react)
7. [計算邏輯](#7-計算邏輯)
8. [股價 API（Finnhub）](#8-股價-apifinnhub)
9. [環境變數](#9-環境變數)
10. [部署設定](#10-部署設定)
11. [注意事項](#11-注意事項)

---

## 1. 專案概述

### 目標
管理個人多個投資帳戶（台股、美股、基金、加密貨幣），提供損益計算、持倉總覽、交易輸入功能。

### 帳戶清單
| account 值 | 說明 | 幣別 |
|-----------|------|------|
| `台股` | 個人台股 | TWD |
| `美股` | 個人美股（凱基複委託） | USD |
| `爸媽美股` | 父母美股帳戶 | USD |
| `x` | 協助管理的第三方台股帳戶 | TWD |

### 其他資產（手動更新現值）
- 摩根新興科技基金
- 野村高科技基金
- 加密貨幣

---

## 2. 技術架構

```
stock_web/（單一 GitHub Repo）
      │
      ├── frontend/   React + Vite
      │     瀏覽器發送請求到 /api/*
      │
      └── backend/    FastAPI（Python）
            從 Supabase 讀寫資料
            呼叫 Finnhub 抓股價
            計算 FIFO / 損益
            回傳 JSON 給前端

部署：Vercel（前後端同一專案）
資料庫：Supabase（PostgreSQL）
股價：Finnhub API（免費 60次/分鐘）
```

### 請求流程
```
使用者操作
  → React 呼叫 /api/portfolio/台股
  → Vercel 將 /api/* 導向 FastAPI
  → FastAPI 查詢 Supabase + 呼叫 Finnhub
  → 計算 FIFO 和損益
  → 回傳 JSON
  → React 更新畫面
```

### 技術選型
| 層級 | 技術 |
|------|------|
| 前端框架 | React 18 + Vite |
| 前端樣式 | Tailwind CSS |
| 前端圖表 | Recharts |
| 前端路由 | React Router v6 |
| 後端框架 | FastAPI（Python 3.11+） |
| 資料庫 | Supabase（PostgreSQL） |
| 股價 API | Finnhub |
| 部署 | Vercel |

---

## 3. 資料夾結構

```
stock_web/
├── vercel.json                  ← Vercel 部署設定（前後端路由）
├── .env.example                 ← 環境變數範本
│
├── frontend/                    ← React 前端
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              ← Router 設定
│       ├── constants.js         ← 固定常數
│       ├── api/
│       │   └── client.js        ← 所有對 /api/* 的 fetch 封裝
│       ├── hooks/
│       │   ├── usePortfolio.js  ← 取得持倉資料
│       │   ├── useSummary.js    ← 取得總覽資料
│       │   └── useTrades.js     ← 取得交易紀錄
│       ├── pages/
│       │   ├── Dashboard.jsx    ← /
│       │   ├── Holdings.jsx     ← /holdings
│       │   ├── AddTrade.jsx     ← /add-trade
│       │   └── History.jsx      ← /history
│       └── components/
│           ├── NavBar.jsx
│           ├── SummaryCard.jsx
│           ├── AssetPieChart.jsx
│           ├── HoldingsTable.jsx
│           ├── ManualValueEditor.jsx
│           └── TradeForm.jsx
│
└── backend/                     ← FastAPI 後端
    ├── main.py                  ← FastAPI app 入口
    ├── requirements.txt
    ├── config.py                ← 環境變數讀取
    ├── database.py              ← Supabase client
    ├── routers/
    │   ├── portfolio.py         ← /api/portfolio/*
    │   ├── trades.py            ← /api/trades/*
    │   ├── summary.py           ← /api/summary
    │   └── manual.py            ← /api/manual/*（基金/現金）
    ├── services/
    │   ├── fifo.py              ← FIFO 計算邏輯
    │   ├── fees.py              ← 手續費 / 證交稅計算
    │   ├── prices.py            ← Finnhub 股價抓取
    │   └── calculator.py        ← 整合 fifo + prices → 持倉損益
    └── models.py                ← Pydantic 資料模型
```

---

## 4. 資料庫結構（Supabase）

### 4.1 trades（交易紀錄）

已有 719 筆初始資料匯入。

```sql
CREATE TABLE trades (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account    TEXT NOT NULL,     -- '台股' | '美股' | '爸媽美股' | 'x'
  ticker     TEXT NOT NULL,     -- '2330'、'NVDA' 等
  date       DATE,              -- 部分早期爸媽美股為 NULL
  buy_qty    DECIMAL,           -- 買入股數（賣出時為 NULL）
  sell_qty   DECIMAL,           -- 賣出股數（買入時為 NULL）
  price      DECIMAL NOT NULL,
  fee        DECIMAL DEFAULT 0,
  total      DECIMAL,
  note       TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 manual_values（手動更新值）

```sql
CREATE TABLE manual_values (
  key        TEXT PRIMARY KEY,  -- 'morgan_value' | 'nomura_value' | 'crypto_value'
  value      DECIMAL NOT NULL,  -- 台幣金額
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

初始資料：
| key | value |
|-----|-------|
| `morgan_value` | 65000 |
| `nomura_value` | 26000 |
| `crypto_value` | 17039.97 |

### 4.3 cash_accounts（現金帳戶）

```sql
CREATE TABLE cash_accounts (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  currency   TEXT DEFAULT 'TWD',
  amount     DECIMAL DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. 後端規格（FastAPI）

### 5.1 入口（backend/main.py）

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import portfolio, trades, summary, manual

app = FastAPI(title="stock_web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境改為前端的 Vercel 網址
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/api/portfolio")
app.include_router(trades.router,    prefix="/api/trades")
app.include_router(summary.router,   prefix="/api")
app.include_router(manual.router,    prefix="/api/manual")
```

### 5.2 Pydantic 模型（backend/models.py）

```python
from pydantic import BaseModel
from typing import Optional
from datetime import date

class Trade(BaseModel):
    id: Optional[str] = None
    account: str
    ticker: str
    date: Optional[date] = None
    buy_qty: Optional[float] = None
    sell_qty: Optional[float] = None
    price: float
    fee: float = 0
    total: Optional[float] = None
    note: str = ""

class TradeCreate(BaseModel):
    account: str
    ticker: str
    date: date
    buy_qty: Optional[float] = None
    sell_qty: Optional[float] = None
    price: float
    fee: float = 0
    note: str = ""

class Holding(BaseModel):
    ticker: str
    qty: float
    avg_price: float
    current_price: Optional[float] = None
    cost: float
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    weight: Optional[float] = None

class ManualValueUpdate(BaseModel):
    key: str
    value: float

class CashUpdate(BaseModel):
    id: str
    amount: float
```

### 5.3 API 端點完整清單

#### GET /api/summary
總覽資料，整合所有帳戶損益和資產。

回傳：
```json
{
  "usd_rate": 31.316,
  "accounts": {
    "台股": {
      "cost": 262151,
      "realized_pnl": 37730.29,
      "unrealized_pnl": 78884,
      "total_fee": 420,
      "total_tax": 430
    },
    "美股": {
      "cost": 207882.6,
      "realized_pnl": -2838.7,
      "unrealized_pnl": 71622.7,
      "total_fee": 305.8
    },
    "爸媽美股": { ... },
    "x": { ... }
  },
  "manual": {
    "morgan_cost": 74000,
    "morgan_value": 65000,
    "nomura_cost": 47500,
    "nomura_value": 26000,
    "crypto_cost": 68785,
    "crypto_value": 17039.97
  },
  "cash": {
    "twd_total": 18700,
    "usd_total": 3126.6,
    "twd_equivalent": 116463.9
  },
  "total_assets": 892517
}
```

---

#### GET /api/portfolio/{account}
單一帳戶的持倉明細，含即時損益。

- `account`：`台股` | `美股` | `爸媽美股` | `x`

回傳：
```json
{
  "account": "台股",
  "holdings": [
    {
      "ticker": "00981A",
      "qty": 3500,
      "avg_price": 22.43,
      "current_price": 28.91,
      "cost": 78519,
      "market_value": 101185,
      "pnl": 22666,
      "pnl_pct": 0.2886,
      "weight": 0.2995
    }
  ],
  "dashboard": {
    "total_cost": 262151,
    "realized_pnl": 37730.29,
    "unrealized_pnl": 78884,
    "total_fee": 420,
    "total_tax": 430,
    "updated_at": "2026-05-09T16:20:00"
  }
}
```

---

#### GET /api/trades/{account}
取得單一帳戶的所有交易紀錄。

Query params：
- `ticker`（選填）：篩選特定股票
- `start_date`（選填）：`2026-01-01`
- `end_date`（選填）：`2026-05-09`

回傳：
```json
{
  "trades": [
    {
      "id": "uuid",
      "account": "台股",
      "ticker": "2330",
      "date": "2026-03-21",
      "buy_qty": 1,
      "sell_qty": null,
      "price": 1970,
      "fee": 3,
      "total": 1973,
      "note": ""
    }
  ]
}
```

---

#### POST /api/trades
新增一筆交易。

Request body：
```json
{
  "account": "台股",
  "ticker": "2330",
  "date": "2026-05-09",
  "buy_qty": 1,
  "sell_qty": null,
  "price": 2250,
  "fee": 3,
  "note": "覺得價格不錯"
}
```

回傳：
```json
{
  "success": true,
  "trade": { ...新增的完整交易資料... }
}
```

**台股手續費自動計算**：後端收到台股帳戶的請求後，若 `fee` 為 0，自動計算並填入。

---

#### DELETE /api/trades/{trade_id}
刪除一筆交易。

回傳：
```json
{ "success": true }
```

---

#### GET /api/manual
取得所有手動更新值（基金現值 + 現金帳戶）。

回傳：
```json
{
  "values": [
    { "key": "morgan_value", "value": 65000, "updated_at": "..." },
    { "key": "nomura_value", "value": 26000, "updated_at": "..." },
    { "key": "crypto_value", "value": 17039.97, "updated_at": "..." }
  ],
  "cash": [
    { "id": "uuid", "name": "國泰現金", "currency": "TWD", "amount": 13000 },
    { "id": "uuid", "name": "身上現金", "currency": "USD", "amount": 3126.6 }
  ]
}
```

---

#### PATCH /api/manual/value
更新基金或加密現值。

Request body：
```json
{ "key": "morgan_value", "value": 68000 }
```

---

#### PATCH /api/manual/cash/{cash_id}
更新現金帳戶餘額。

Request body：
```json
{ "amount": 15000 }
```

---

### 5.4 Supabase 連接（backend/database.py）

```python
from supabase import create_client, Client
from config import settings

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY  # 後端用 service key，不是 anon key
)
```

### 5.5 requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
supabase==2.7.0
httpx==0.27.0
pydantic==2.7.0
python-dotenv==1.0.0
```

---

## 6. 前端規格（React）

### 6.1 路由（frontend/src/App.jsx）

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard  from './pages/Dashboard'
import Holdings   from './pages/Holdings'
import AddTrade   from './pages/AddTrade'
import History    from './pages/History'
import NavBar     from './components/NavBar'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-white pb-20">
        <Routes>
          <Route path="/"          element={<Dashboard />} />
          <Route path="/holdings"  element={<Holdings />} />
          <Route path="/add-trade" element={<AddTrade />} />
          <Route path="/history"   element={<History />} />
        </Routes>
        <NavBar />
      </div>
    </BrowserRouter>
  )
}
```

### 6.2 API Client（frontend/src/api/client.js）

```javascript
const BASE = '/api'  // Vercel 自動路由到 FastAPI

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  getSummary:        ()           => request('/summary'),
  getPortfolio:      (account)    => request(`/portfolio/${encodeURIComponent(account)}`),
  getTrades:         (account)    => request(`/trades/${encodeURIComponent(account)}`),
  addTrade:          (data)       => request('/trades', { method: 'POST', body: JSON.stringify(data) }),
  deleteTrade:       (id)         => request(`/trades/${id}`, { method: 'DELETE' }),
  getManual:         ()           => request('/manual'),
  updateManualValue: (key, value) => request('/manual/value', { method: 'PATCH', body: JSON.stringify({ key, value }) }),
  updateCash:        (id, amount) => request(`/manual/cash/${id}`, { method: 'PATCH', body: JSON.stringify({ amount }) }),
}
```

### 6.3 頁面一：總覽儀表板（/）

資料來源：`GET /api/summary`

版面：
```
[ 總資產 ]  [ 未實現損益 ]  [ 已實現損益 ]
[ 現金比例 ] [ 總手續費+稅 ]

[ 資產分布圓餅圖 ]
  台股 / 美股 / 爸媽美股 / 基金 / 加密 / 現金

[ 各帳戶快速摘要 ]
  台股      $XXX,XXX  +X.X%  →
  美股      $XXX,XXX  +X.X%  →
  爸媽美股  $XXX,XXX  +X.X%  →
  基金&其他 $XXX,XXX  +X.X%  →

[ 現金管理（可展開）]
  新光 [____] 第一 [____] 郵局 [____] 國泰 [____]
  合計：$XX,XXX
```

### 6.4 頁面二：持倉明細（/holdings）

資料來源：`GET /api/portfolio/{account}`

Tab 切換：台股 ／ 美股 ／ 爸媽美股 ／ 基金&其他 ／ x帳戶

**台股 / 美股 / 爸媽美股 / x 每行顯示：**

| 欄位 | 說明 |
|------|------|
| 代號 | ticker |
| 股數 | qty |
| 均價 | avg_price |
| 現價 | current_price（來自 Finnhub） |
| 市值 | market_value |
| 損益金額 | pnl |
| 損益% | pnl_pct（綠色正值 / 紅色負值） |
| 佔比 | weight |

排序：預設依市值由高到低

**基金&其他 Tab：**

| 名稱 | 投入金額 | 現在價值 | 損益 | 損益% |
|------|---------|---------|------|------|
| 摩根新興科技 | 74,000 | 可編輯 | 計算 | 計算 |
| 野村高科技 | 47,500 | 可編輯 | 計算 | 計算 |
| 加密貨幣 | 68,785 | 可編輯 | 計算 | 計算 |

點擊現在價值可直接輸入，失去焦點後自動送出 `PATCH /api/manual/value`。

### 6.5 頁面三：新增交易（/add-trade）

資料來源：`POST /api/trades`

表單欄位：

| 欄位 | 說明 |
|------|------|
| 帳戶 | 按鈕選擇：台股 / 美股 / 爸媽美股 / x |
| 代號 | 文字輸入，自動轉大寫 |
| 買賣 | 按鈕選擇：買入 / 賣出 |
| 股數 | 數字輸入 |
| 價格 | 數字輸入 |
| 日期 | 日期選擇器，預設今天 |
| 備註 | 選填 |

台股選取時，即時顯示自動計算結果：
```
手續費：$XX
證交稅：$XX（賣出才顯示）
交易總額：$XX,XXX
```

送出後導向 `/holdings`。

### 6.6 頁面四：交易紀錄（/history）

資料來源：`GET /api/trades/{account}`

篩選：帳戶、代號、日期範圍

列表欄位：日期、帳戶、代號、買/賣、股數、成交價、手續費、備註、刪除按鈕

刪除：確認後呼叫 `DELETE /api/trades/{id}`

### 6.7 固定常數（frontend/src/constants.js）

```javascript
export const OTC_LIST = [
  '3324', '3555', '3661', '3665', '6869',
  '8299', '4971', '2455', '2368', '3081',
  '3037', '3189', '3264', '8046', '7871'
]

export const ETF_LIST = ['0050', '00981A']

export const TW_ACCOUNTS = ['台股', 'x']

export const MANUAL_COSTS = {
  morgan: 74000,
  nomura: 47500,
  crypto: 68785,
}
```

---

## 7. 計算邏輯

**所有計算在後端（Python）完成，前端只負責顯示。**

### 7.1 台股手續費（backend/services/fees.py）

```python
BROKER_DISCOUNT = 0.6
MINIMUM_FEE = 1

def calc_tw_fee(price: float, qty: float) -> int:
    fee = price * qty * 0.001425 * BROKER_DISCOUNT
    return max(int(fee), MINIMUM_FEE)

def calc_tw_tax(price: float, qty: float, ticker: str) -> int:
    ETF_LIST = ['0050', '00981A']
    rate = 0.001 if ticker in ETF_LIST else 0.003
    return int(price * qty * rate)
```

### 7.2 FIFO 計算（backend/services/fifo.py）

```python
from dataclasses import dataclass, field
from typing import List

EPSILON = 1e-7

@dataclass
class BuyLot:
    qty: float
    price: float

def calc_fifo(trades: list, account: str, ticker: str) -> dict:
    """
    trades: 依日期排序的交易清單（同帳戶同 ticker）
    回傳：{ current_qty, total_cost, avg_price, realized_pnl }
    """
    buy_lots: List[BuyLot] = []
    current_qty  = 0.0
    total_cost   = 0.0
    realized_pnl = 0.0

    is_tw = account in ['台股', 'x']

    for t in trades:
        buy_qty  = t.get('buy_qty')  or 0
        sell_qty = t.get('sell_qty') or 0
        price    = t['price']

        if buy_qty > 0:
            buy_lots.append(BuyLot(qty=buy_qty, price=price))
            current_qty += buy_qty
            total_cost  += buy_qty * price

        if sell_qty > 0:
            fee = calc_tw_fee(price, sell_qty) if is_tw else (t.get('fee') or 0)
            tax = calc_tw_tax(price, sell_qty, ticker) if is_tw else 0
            revenue = price * sell_qty - fee - tax

            remaining    = sell_qty
            cost_of_sold = 0.0

            while remaining > EPSILON and buy_lots:
                lot = buy_lots[0]
                qty = min(lot.qty, remaining)
                cost_of_sold += qty * lot.price
                lot.qty      -= qty
                remaining    -= qty
                if lot.qty < EPSILON:
                    buy_lots.pop(0)

            current_qty  -= sell_qty
            total_cost   -= cost_of_sold
            realized_pnl += revenue - cost_of_sold

    if abs(current_qty) < EPSILON:
        current_qty = 0
        total_cost  = 0

    avg_price = total_cost / current_qty if current_qty > 0 else 0

    return {
        'current_qty':  current_qty,
        'total_cost':   total_cost,
        'avg_price':    avg_price,
        'realized_pnl': realized_pnl,
    }
```

### 7.3 損益整合（backend/services/calculator.py）

```python
async def build_holdings(account: str, trades: list, prices: dict) -> list:
    """
    trades: 該帳戶所有交易
    prices: { ticker: current_price }
    回傳: List[Holding]
    """
    from collections import defaultdict

    # 依 ticker 分組
    by_ticker = defaultdict(list)
    for t in trades:
        by_ticker[t['ticker']].append(t)

    holdings = []
    total_cost = 0

    for ticker, ticker_trades in by_ticker.items():
        sorted_trades = sorted(ticker_trades, key=lambda x: x.get('date') or '')
        result = calc_fifo(sorted_trades, account, ticker)

        if result['current_qty'] <= 0:
            continue

        total_cost += result['total_cost']
        holdings.append({
            'ticker':    ticker,
            'qty':       result['current_qty'],
            'avg_price': result['avg_price'],
            'cost':      result['total_cost'],
            'realized_pnl': result['realized_pnl'],
        })

    # 加入現價和損益
    for h in holdings:
        price = prices.get(h['ticker'])
        h['current_price'] = price
        if price:
            h['market_value'] = price * h['qty']
            h['pnl']          = h['market_value'] - h['cost']
            h['pnl_pct']      = h['pnl'] / h['cost'] if h['cost'] > 0 else 0
        h['weight'] = h['cost'] / total_cost if total_cost > 0 else 0

    # 依市值排序
    holdings.sort(key=lambda x: x.get('market_value') or 0, reverse=True)
    return holdings
```

---

## 8. 股價 API（Finnhub）

### 台股代號格式

| 類型 | Finnhub symbol | 範例 |
|------|---------------|------|
| 上市股票 | `{代號}.TW` | `2330.TW` |
| 上櫃股票 | `{代號}.TWO` | `3264.TWO` |
| ETF（含 00981A） | `{代號}.TWO` | `00981A.TWO` |
| 美股 | 直接用 ticker | `NVDA` |

### 抓價邏輯（backend/services/prices.py）

```python
import httpx
import asyncio

OTC_LIST = ['3324','3555','3661','3665','6869','8299','4971',
            '2455','2368','3081','3037','3189','3264','8046','7871','00981A']

def get_finnhub_symbol(ticker: str, account: str) -> str:
    is_tw = account in ['台股', 'x'] or ticker[:4].isdigit()
    if not is_tw:
        return ticker  # 美股直接用
    if ticker in OTC_LIST:
        return f"{ticker}.TWO"
    return f"{ticker}.TW"

async def fetch_price(ticker: str, symbol: str, api_key: str) -> tuple:
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, timeout=5)
            data = res.json()
            price = data.get('c')  # current price
            return ticker, price
        except Exception:
            return ticker, None

async def fetch_prices_batch(tickers: list, account: str, api_key: str) -> dict:
    """批次抓取，每筆間隔 100ms 避免超過速率限制"""
    results = {}
    for ticker in tickers:
        symbol = get_finnhub_symbol(ticker, account)
        _, price = await fetch_price(ticker, symbol, api_key)
        results[ticker] = price
        await asyncio.sleep(0.1)
    return results
```

### 匯率（USD/TWD）

```python
async def fetch_usd_rate(api_key: str) -> float:
    url = f"https://finnhub.io/api/v1/forex/rates?base=USD&token={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, timeout=5)
            data = res.json()
            return data['quote'].get('TWD', 31.316)
        except Exception:
            return 31.316  # fallback
```

---

## 9. 環境變數

### .env.example

```
# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...         # 前端用（若有直接呼叫）
SUPABASE_SERVICE_KEY=eyJhbGci...      # 後端用（有完整讀寫權限）

# Finnhub
FINNHUB_KEY=your_finnhub_api_key

# 前端讀取（Vite 需要 VITE_ 前綴）
VITE_API_BASE=/api
```

### 取得方式

| 變數 | 取得位置 |
|------|---------|
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Supabase Dashboard → Settings → API → anon public |
| `SUPABASE_SERVICE_KEY` | Supabase Dashboard → Settings → API → service_role |
| `FINNHUB_KEY` | finnhub.io 免費註冊 |

---

## 10. 部署設定

### vercel.json（根目錄）

```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "/backend/main.py"
    }
  ],
  "functions": {
    "backend/main.py": {
      "runtime": "python3.11"
    }
  }
}
```

### 部署步驟

1. GitHub 建立 repo `stock_web`，推送所有程式碼
2. 前往 vercel.com → Import Project → 選擇 repo
3. 在 Vercel 設定所有環境變數（Settings → Environment Variables）
4. Deploy

之後每次 `git push main` 自動觸發部署。

### 本地開發

```bash
# 後端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端（另開一個 terminal）
cd frontend
npm install
npm run dev
# Vite dev server 預設 localhost:5173
# 需在 vite.config.js 設定 proxy 將 /api 導向 localhost:8000
```

#### frontend/vite.config.js 的 proxy 設定

```javascript
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
}
```

---

## 11. 注意事項

### 股數單位：股，不是張
所有 `buy_qty` / `sell_qty` 單位是**股**，不是張。台股 1 張 = 1000 股，此系統統一用股，計算時不需要乘以 1000。

### 爸媽美股早期資料無日期
11 筆早期交易 `date` 統一填為 `2026-02-03`（估計日期）。FIFO 排序時這些筆排在最前面。

### 美股手續費
美股 `fee` 為實際支付金額（美金），後端不自動計算，直接使用前端傳入的值。早期部分交易手續費為 0。

### 台股 00981A
此 ETF 代號含英文字母，在 OTC_LIST 裡，Finnhub symbol 為 `00981A.TWO`。同時在 ETF_LIST，賣出稅率 0.1%。

### x 帳戶
協助第三方管理的台股帳戶，計算邏輯與「台股」完全相同（手續費自動計算），但顯示上獨立分開。

### CORS
本地開發透過 Vite proxy 解決。Vercel 部署後前後端同 domain，不需要 CORS 設定。但若前後端分開部署（不同 domain），需在 FastAPI 的 CORSMiddleware 設定允許的 origin。

### Finnhub 速率限制
免費方案 60 次/分鐘。持倉頁面一次可能要抓 40+ 檔，批次處理每筆間隔 100ms，約 4 秒可抓完。建議在後端快取結果（同一 session 內不重複呼叫）。

---

*文件版本：v4.0 | 2026/05/09*  
*架構：React + FastAPI + Supabase，部署於 Vercel*  
*資料庫：719 筆交易資料已匯入 Supabase*
