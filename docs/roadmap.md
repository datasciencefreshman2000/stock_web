# stock_web 優化與「智慧投資」演進規劃

> 撰寫日期：2026-08-04
> 現況：React + FastAPI + Supabase，部署 Vercel，Cloudflare Worker 定時刷新 / 快照
> 目標：從「投資組合記帳」演進成「會提醒我該做什麼的投資決策系統」

---

## Part A — 現有系統的優化

依「先修再擴充」的順序排列。A1~A3 建議在做任何新功能之前處理。

### A1. 安全性（最高優先）

**問題**

- 後端用 Supabase `service_role` key，擁有完整讀寫權限。
- `cors_origins` 預設 `*`。
- `/api/trades` 的 POST / PATCH / DELETE 沒有任何驗證。

也就是說，任何人只要知道網址，就能讀取全部資產、新增或刪除交易紀錄。

**選項（由簡到繁）**

| 方案 | 成本 | 說明 |
|------|------|------|
| Vercel Deployment Protection | 最低 | 需 Pro 方案，整站加密碼／SSO |
| Cloudflare Access | 低 | 已在用 Cloudflare，可放 Zero Trust 前面，Email OTP 登入 |
| 單一密碼 + JWT | 中 | 自己寫 `/api/auth/login`，發 JWT，FastAPI 加 dependency 驗證 |
| Supabase Auth | 中高 | 完整帳號系統，未來要多使用者才需要 |

**建議**：個人使用 → Cloudflare Access 或單一密碼 JWT。同時把 `CORS_ORIGINS` 設成實際網域，不要留 `*`。

---

### A2. Serverless 環境下的快取假設有誤

`services/prices.py` 的 `PRICE_CACHE`、`RATE_CACHE`、`COMPANY_NAME_CACHE` 都是 module-level dict。

在 Vercel serverless 上，每個 function instance 是獨立的、會被回收的。這代表：

- 這些記憶體快取**大部分時間是空的**，命中率遠低於預期。
- 不同請求可能打到不同 instance，快取狀態不一致。
- `PRICE_FETCH_STATE` 回報的統計數字在多 instance 下沒有意義。

**建議**

1. 記憶體快取降級為「同一次 request 內的 memo」，跨請求一律以 `price_cache` 表為準（這張表已經存在，邏輯已經寫好，只要把記憶體那層當成 best-effort）。
2. 匯率也存進 DB（新增 `fx_rate` 表或塞進 `price_cache`），不要只靠 `RATE_CACHE`。
3. 公司名稱存進新的 `tickers` 主檔（見 A5），不要用記憶體 dict。

---

### A3. BackgroundTasks 在 serverless 上不可靠

`routers/summary.py` 與 `routers/portfolio.py` 用 `BackgroundTasks` 在回應之後刷新快取。Serverless function 在回傳 response 後可能立刻被凍結／回收，背景任務有機會做到一半就死掉（而且 `SUMMARY_REFRESH_STATE` 會卡在 `in_progress: True`）。

**建議：責任分離**

- **寫入端（cron）**：Cloudflare Worker 是唯一負責「抓價 + 重算 + 寫 cache」的角色。已經有 `/api/jobs/refresh` 和 `/api/jobs/snapshot`，架構是對的。
- **讀取端（前端）**：`GET /api/summary`、`GET /api/portfolio/{account}` 一律只讀 cache，不觸發任何刷新。
- **手動刷新**：前端的「刷新」按鈕改成呼叫一個同步的 `POST /api/jobs/refresh`（帶使用者 token），等它跑完再回傳。誠實地讓使用者等 3 秒，好過不確定的背景任務。

---

### A4. FIFO 重複計算

目前 `/api/summary` 和 `/api/portfolio/{account}` 各自從頭跑一次完整 FIFO（讀全部 trades → 重算）。719 筆還撐得住，但：

- 每次 cron 刷新等於算了 1（summary）+ 4（各帳戶）= 5 次相同的 FIFO。
- 交易筆數會持續成長。

**建議**

1. 短期：`refresh_all` 裡先算一次 FIFO，結果傳給 summary 與各 portfolio 共用（現在 `jobs.py` 是分別呼叫兩個 refresh 函式，各自重讀 DB）。
2. 中期：加 `position_checkpoint` 表，每年底（或每季）存一次各 ticker 的 FIFO 狀態（剩餘 lots 的 JSON + 累計已實現損益），之後只需從 checkpoint 往後重算。
3. `list_trades()` 目前 `select("*")`，只取需要的欄位可以省一點傳輸。

---

### A5. 缺少的資料表（這是 Part B 的前提）

現在資料庫只有「交易」和「當下價格」，缺三張關鍵表：

**`tickers`（標的主檔）**

```sql
create table tickers (
  symbol      text primary key,     -- 'TW:2330' / 'NVDA'
  ticker      text not null,
  name        text,
  market      text,                 -- 'TWSE' | 'TPEX' | 'US'
  is_etf      boolean default false,
  currency    text,
  sector      text,
  updated_at  timestamptz default now()
);
```

解決：OTC_LIST / ETF_LIST 目前硬編在 `constants.js` 與後端常數裡、公司名稱每次都要打 API。

**`corporate_actions`（除權息與分割）**

```sql
create table corporate_actions (
  id          uuid primary key default gen_random_uuid(),
  symbol      text not null,
  action_type text not null,        -- 'split' | 'dividend' | 'stock_dividend'
  ex_date     date not null,
  ratio       numeric,              -- 分割比例，如 4 表示 1 股變 4 股
  amount      numeric,              -- 每股配息
  currency    text,
  applied     boolean default false,
  created_at  timestamptz default now(),
  unique (symbol, action_type, ex_date)
);
```

這正是 `功能想法記錄/20260722.txt` 裡 MUU 分割問題的解法。**不要直接改寫歷史 trades**，而是保留原始交易，在 FIFO 計算時套用 corporate action 調整。理由：原始紀錄是事實，調整是衍生；直接改寫會讓你永遠對不回券商對帳單。

**`price_history`（日線 OHLCV）**

```sql
create table price_history (
  symbol     text not null,
  date       date not null,
  open       numeric,
  high       numeric,
  low        numeric,
  close      numeric,
  adj_close  numeric,      -- 還原權值後價格
  volume     numeric,
  primary key (symbol, date)
);
create index on price_history(symbol, date desc);
```

**沒有這張表，技術分析和回測完全做不了。** 這是 Part B 的第 0 步。

---

### A6. 沒有測試

FIFO 是處理錢的邏輯，`20260622.txt` 記錄的 2455 均價異常就是典型症狀。建議加 `backend/tests/`：

- `test_fifo.py`：純買入、部分賣出、多次賣出拆單、賣超（unmatched sell）、股票分割後的 FIFO。
- `test_fees.py`：台股手續費最低 1 元、ETF 與一般股票稅率差異。
- 用固定的假資料，不碰 DB、不碰網路。

這件事在導入回測前特別重要——回測結果的可信度完全建立在成本計算正確之上。

---

### A7. 前端

- `Cash.jsx` 682 行、`History.jsx` 545 行、`Dashboard.jsx` 435 行、`HoldingsTable.jsx` 409 行。建議拆分：把資料處理搬到 hooks，把重複的卡片／表格列抽成小元件。
- 沒有 request 快取層，每次切頁都重打 API。導入 **TanStack Query**（react-query）可以直接解決快取、背景重新整理、loading／error 狀態，也能順手移除 `useAsync.js` 的手工樣板。
- `frontend/dist/` 有被 commit 進 repo（`.gitignore` 有寫 `dist/` 但看起來曾經進去過），確認一下 `git rm -r --cached frontend/dist`。

---

## Part B — 「智慧投資」的規劃

### 先釐清一個關鍵區分

你說想加「回測」，但這其實是兩件價值完全不同的事：

| | 策略回測 | 個人操作歸因 |
|---|---|---|
| 問題 | 「如果我用某某策略，過去會賺多少？」 | 「我實際的操作，錢是賺在哪、虧在哪？」 |
| 資料 | 需要完整市場歷史資料 | **你已經有了**——719 筆真實交易 |
| 差異化 | 市面上一堆工具做得比你好 | 沒有任何網站能幫你做，因為只有你有這份資料 |
| 建議 | 之後再做 | **優先做** |

你手上最稀有的資產是「你自己完整的交易史」。先從這裡榨出洞察，比一開始就去做通用回測引擎有價值得多。

---

### Phase 0：資料基礎（沒有這步，後面全部做不了）

**要做的事**

1. 建立 A5 的三張表。
2. 寫一個每日收盤後的 cron job，抓所有持有過的標的日線資料補進 `price_history`。
   - 台股：Fugle 的 historical candles API。
   - 美股：Finnhub 免費版的 candle API 已停用，需要換來源——Alpha Vantage（免費 25 次/日）、Twelve Data（免費 800 次/日）、或 EOD Historical Data（付費但穩定）。**建議先評估這件事，它會決定整個 Phase 1~3 的可行性。**
3. 一次性回補：把每個標的從你第一筆交易日期開始的歷史補齊。
4. 處理 corporate actions，把 MUU 這類分割問題修正。

**驗收標準**：能畫出「我的總資產 vs 0050 vs S&P 500」從第一筆交易到今天的曲線圖。

**估計工作量**：這是整個規劃裡最大的一塊，但也是唯一無法跳過的。

---

### Phase 1：個人操作歸因（差異化最高，優先做）

有了 `price_history`，就能算出這些——這些數字市面上的 App 都不會幫你算：

**報酬率**

- **TWR（時間加權報酬）**：排除你何時投入資金的影響，用來跟指數公平比較。
- **XIRR（金額加權報酬）**：把每次入金出金當現金流算年化報酬，這才是「你的錢實際賺了幾 %」。
- 兩者的差距本身就是洞察：TWR > XIRR 代表你「在高點加碼、低點縮手」。

**Benchmark 對照**

- 把你每一筆投入的金額與時間點，套用到 0050 / VOO 上，得到「如果我把每一分錢在同一天買指數會怎樣」。
- 這是最誠實的一面鏡子。

**反事實分析**

- 「如果我買了就完全不動（buy and hold），現在會是多少？」——量化你所有「進出操作」的總價值。
- 「我賣掉的股票，賣掉之後表現如何？」——量化賣出決策品質。

**行為統計**

- 勝率、平均賺賠比、平均持有天數。
- 最大回撤（用 `account_snapshots` 就能算，你已經在存了）。
- 賺錢的部位平均持有多久 vs 虧錢的部位持有多久（處置效應：是否太早賣賺的、抱著虧的）。
- 各帳戶／各產業的貢獻拆解。

**建議做成一個新頁面 `/analytics`**，這會是整個站最有價值的東西。

---

### Phase 2：提醒引擎（你說的「提醒我該做什麼」）

這是把系統從「看板」變成「助手」的關鍵。核心是一個規則引擎。

**資料表**

```sql
create table alert_rules (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  scope       text not null,        -- 'portfolio' | 'account' | 'ticker'
  target      text,                 -- 帳戶名或 ticker，portfolio 時為 null
  rule_type   text not null,        -- 見下方分類
  params      jsonb not null,       -- { threshold: 0.25, window: 20, ... }
  enabled     boolean default true,
  cooldown_hours int default 24,    -- 避免同一條規則每小時轟炸
  created_at  timestamptz default now()
);

create table alerts (
  id          uuid primary key default gen_random_uuid(),
  rule_id     uuid references alert_rules(id) on delete cascade,
  triggered_at timestamptz default now(),
  severity    text default 'info',  -- 'info' | 'warn' | 'action'
  title       text not null,
  message     text,
  context     jsonb,                -- 觸發當下的數值快照
  acknowledged_at timestamptz
);
```

**規則分三類，建議照這個順序做**

**(a) 部位／風險管理**——最相關、只有你的系統做得到

| 規則 | 說明 |
|------|------|
| `concentration` | 單一標的佔投資組合 > X%（例如 25%） |
| `cash_ratio` | 現金比例低於 X% 或高於 Y%（該加碼／該留彈藥了） |
| `stop_loss` | 單一持股未實現虧損 > X% |
| `take_profit` | 單一持股未實現獲利 > X%（考慮部分獲利了結） |
| `drawdown` | 總資產從歷史高點回撤 > X% |
| `allocation_drift` | 實際配置偏離目標配置 > X%（需要先定義目標配置） |
| `idle_cash` | 帳上現金超過 X 元且閒置超過 N 天 |

注意：這一類**完全不需要 `price_history`**，用現有資料就能做。如果你想快速看到成果，可以先做這一類，再回頭做 Phase 0。

**(b) 技術訊號**——需要 Phase 0 的日線資料

| 規則 | 說明 |
|------|------|
| `ma_cross` | 收盤價站上／跌破 MA20、MA60、MA200 |
| `golden_cross` | MA20 上穿 MA60 |
| `rsi` | RSI(14) > 70 或 < 30 |
| `macd` | MACD 柱狀圖翻正／翻負 |
| `bollinger` | 觸及布林通道上下軌 |
| `atr_spike` | ATR 相對放大（波動異常） |
| `volume_spike` | 成交量 > 20 日均量 × 2 |
| `new_high_low` | 創 52 週新高／新低 |

實作上，指標都是純函數，用 `pandas` + `pandas-ta` 幾行就有。**不要存指標值進 DB**，每次從 `price_history` 現算即可（一檔股票 5 年日線也才 1200 筆）。

**(c) 事件與紀律提醒**

| 規則 | 說明 |
|------|------|
| `dividend_ex_date` | 除權息日將至 |
| `earnings_date` | 財報公布日將至 |
| `rebalance_due` | 距上次再平衡已滿 N 個月 |
| `dca_reminder` | 定期定額日提醒 |
| `tax_lot` | 接近長期持有稅務門檻（美股） |

**推播管道**

規則掃描跑在既有的 Cloudflare Worker cron（每小時已經在跑了），觸發後：

1. 寫入 `alerts` 表 → 前端顯示紅點與通知中心（最簡單，先做這個）。
2. Telegram Bot：一個 bot token + chat id，`POST` 一個 URL 就送出，是成本最低的即時推播。
3. Email：Resend 免費額度足夠個人使用。

**前端**：新增 `/alerts` 頁面 + NavBar 上的未讀數字。Dashboard 頂端放「今天需要你注意的事」區塊。

---

### Phase 3：回測引擎

**架構警訊：這一步不要放在 Vercel 上。**

原因：

- Vercel Hobby function 執行上限 10 秒、Pro 60 秒。跑一次多年期回測會 timeout。
- `pandas` + `numpy` + `pandas-ta` 會讓 Python function bundle 逼近 Vercel 250MB 上限。

**建議架構**

把運算搬出去，變成非同步 job：

```
前端送出回測請求
  → POST /api/backtest  → 寫入 backtest_runs (status: 'queued')
  → 回傳 run_id

Worker（Railway / Fly.io 的小容器，或本機排程）
  → 輪詢 queued 的 run
  → 讀 price_history、跑回測
  → 寫回 backtest_runs (status: 'done', result: jsonb)

前端輪詢 GET /api/backtest/{run_id}
```

`backtest_runs` 表：

```sql
create table backtest_runs (
  id          uuid primary key default gen_random_uuid(),
  strategy    text not null,
  params      jsonb not null,
  universe    text[],            -- 標的清單
  start_date  date,
  end_date    date,
  status      text default 'queued',
  result      jsonb,
  error       text,
  created_at  timestamptz default now(),
  finished_at timestamptz
);
```

**回測必須正確處理的事**（否則結果會過度樂觀）

1. 手續費與證交稅——你的 `services/fees.py` 可以直接複用，這是你相對於通用工具的優勢。
2. 股利再投入。
3. 股票分割（用 `adj_close`）。
4. **避免前視偏誤（look-ahead bias）**：訊號用當日收盤產生，成交價用隔日開盤。
5. **避免倖存者偏誤**：universe 要包含已下市的標的。
6. 滑價（slippage）假設。

**要輸出的指標**：總報酬、年化報酬（CAGR）、最大回撤、Sharpe、Sortino、勝率、賺賠比、交易次數、與 buy-and-hold 對照。

**工具選擇**：`vectorbt`（快、適合參數掃描）或 `backtesting.py`（簡單、事件驅動）。除非有特殊需求，不要自己從零寫。

**一個誠實的提醒**：回測很容易做出漂亮但沒用的結果。參數調到過去表現最好，通常代表未來表現最差（過度擬合）。務必保留一段資料不參與調參，用來做樣本外驗證。回測的正確用途是「排除明顯爛的策略」，不是「找到最佳策略」。

---

### Phase 4：決策簡報

當前面都到位，最後一步是把資訊主動送到你面前：

- **每日晨間簡報**（開盤前）：昨日變動、觸發的警示、今日需注意的事件。
- **每週回顧**：本週績效 vs benchmark、配置變化、規則觸發統計。
- **每月／每季**：再平衡建議、歸因分析、行為檢討。

可以用 Telegram 推送，或做成一個 `/briefing` 頁面。

---

## 建議執行順序

```
✅ 1. A1 安全性（密碼 + JWT，fail closed）
✅ 2. A2 + A3 快取與背景任務（修正 serverless 假設）
✅ 3. A4 FIFO checkpoint 增量結算
✅ 4. A5 tickers / corporate_actions / price_history / fx_rates
✅ 5. A6 pytest（50 個測試，含 checkpoint == 全量重算）

   6. B/Phase 2(a) 部位風險提醒      ← 不需要新資料源，最快看到成果
   7. Phase 0 補 price_history 資料   ← 台股免費、美股見資料源文件
   8. B/Phase 1 個人操作歸因          ← 差異化最高的功能
   9. B/Phase 2(b)(c) 技術與事件提醒
  10. A7 前端重構 + TanStack Query    ← 頁面變多之後再做
  11. B/Phase 3 回測引擎              ← 需要獨立 worker 架構
  12. B/Phase 4 決策簡報
```

第 6 步是刻意插在前面的：它不需要任何新資料源，用現有的 summary 就能實作，可以讓你很快感受到「系統開始會提醒我了」，也順便驗證整個 alert 資料模型設計得對不對，再投入最花時間的 Phase 0。

---

## 三個需要先決定的問題

1. ~~**美股歷史資料要用哪個來源？**~~ → 已研究，見 [`data_sources_and_backtesting.md`](./data_sources_and_backtesting.md)。
   結論：**台股用 Fugle 免費版就有歷史日線**（你已經有 key）；美股先用 Twelve Data 免費版（800 credits/日），
   要認真回測時再上 EODHD $19.99/月。

2. **要不要引入獨立的運算 worker？** 如果決定要做回測，Vercel serverless 一定不夠。
   而且 Shioaji 的憑證與「每 24 小時重新登入」限制也需要常駐環境——**這兩件事可以共用同一個 worker**。
   早點決定，Phase 0 的 job 就可以直接寫在那個 worker 上，不用寫兩次。

3. **「目標配置」要怎麼定義？** 很多有價值的提醒（再平衡、配置偏離）都建立在「你想要的配置是什麼」之上。這需要你先想清楚，不是技術問題。
