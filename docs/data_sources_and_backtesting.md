# 金融資料源比較與回測學習路徑

> 撰寫日期：2026-08-04
> 前提：預算「盡量免費，必要時月付 10–30 美元」
> 目標：支撐 Phase 0（日線資料）、Phase 1（歸因分析）、Phase 3（回測）

---

## 一、結論先講

**台股的歷史日線可以完全免費，你已經有 key 了。**

Fugle 的「基本用戶」方案（註冊富果會員即免費）就包含**台股歷史行情 60 次/分鐘**。
你 `.env` 裡的 `FUGLE_API_KEY` 現在只用來抓即時報價，歷史 candles 端點是同一把 key。
這代表 Phase 0 的台股部分，成本是零。

**美股是唯一需要花錢的地方，而且不一定要花。**

Finnhub 免費版已經沒有歷史 candle。建議路徑：

1. 先用 **Twelve Data 免費版**（800 credits/日）補美股日線。你的美股標的數量不多，每天 800 次額度綽綽有餘。
2. 等到要認真做回測、需要完整的除權息與已下市標的時，再升級 **EODHD 的 EOD All World（$19.99/月）**。這個價格在你的預算內，而且它的 corporate actions 資料完整度是回測正確性的關鍵。

**Shioaji 免費，但要開永豐證券戶。** 它的定位和上面幾個不同——見第四節。

---

## 二、資料源比較表

### 台股

| 來源 | 費用 | 歷史日線 | 除權息 | 備註 |
|------|------|---------|--------|------|
| **Fugle 基本用戶** | **免費**（註冊富果會員） | ✅ 60 次/分 | ❌ | **你已經有 key**。個股可回溯至 2010、指數至 2015 |
| Fugle 開發者 | NT$1,499/月 | ✅ 60 次/分 | ✅ 30 次/分 | 多的是日內快照、技術指標、股務事件 |
| Fugle 進階用戶 | NT$2,999/月 | ✅ 60 次/分 | ✅ | WebSocket 2000 訂閱數，個人用不到 |
| TWSE / TPEx OpenAPI | 免費 | ✅ | ✅ | 官方原始資料，格式較雜但**除權息免費** |
| FinMind | 部分免費，贊助制分級 | ✅ | ✅ | 50+ 資料集含籌碼面，免費層有 rate limit |
| Shioaji | 免費（需券商戶） | ✅ 含 tick、分K | — | 見第四節 |

**台股建議**：Fugle 免費版抓日線 + TWSE/TPEx OpenAPI 抓除權息。
Fugle 的股務事件要 NT$1,499/月才有，但除權息從證交所官方 OpenAPI 免費就能拿，沒必要為此付費。

### 美股

| 來源 | 免費額度 | 付費起點 | 歷史日線 | Corporate Actions |
|------|---------|---------|---------|------------------|
| **Twelve Data** | **800 credits/日** | — | ✅ | 部分 |
| **EODHD** | 20 calls/日（太少） | **$19.99/月**（EOD All World） | ✅ | ✅ 完整 |
| Alpha Vantage | 25 req/日、5 req/分 | $49.99/月 | ✅ | ✅ | 免費層無即時與 15 分延遲資料 |
| Finnhub | 報價可用 | — | ❌ 免費版已無 | — | 你目前只用它抓即時報價，這部分繼續用沒問題 |

**注意 EODHD 的計費單位**：一次 EOD 價格查詢算 1 call，但盤中、技術指標、新聞端點各算 5 calls，
基本面與選擇權算 10 calls。免費版 20 calls/日基本上只夠試玩。

**美股建議**：
- **現在**：Twelve Data 免費版（800/日）夠你補完所有持有過的標的日線。
- **要做回測時**：EODHD EOD All World $19.99/月。理由是回測結果的可信度取決於分割與股利資料的正確性，這正是 EODHD 相對便宜且完整的地方。

### 匯率

你現在用的 `open.er-api.com` + `currency-api` 都免費且沒有 key，**維持現狀即可**，不需要換。

---

## 三、建議的最終組合

```
台股日線     → Fugle 基本用戶（免費，已有 key）
台股除權息   → TWSE / TPEx OpenAPI（免費）
美股日線     → Twelve Data 免費版（起步）
             → EODHD EOD All World $19.99/月（要做認真回測時）
美股即時報價 → Finnhub（免費，維持現狀）
匯率         → open.er-api.com（免費，維持現狀）

起步月成本：NT$0
認真做回測後：約 US$20/月（NT$630 左右）
```

---

## 四、Shioaji 的定位（未來的自動交易）

Shioaji 是永豐金證券的 Python API，**對永豐客戶免費**。它和前面幾個資料源不是同一類東西：

**它能做什麼**
- 歷史 tick 與分 K（`kbars`），顆粒度比任何一家免費 API 都細。
- 即時行情訂閱。
- **自動下單**——這是其他資料源都做不到的。

**限制（都很重要）**
- 需要在永豐開戶。
- 快照、ticks、kbars 官方定位是「**盤後分析與回測用**」，不是即時資料源。
- 流量超限時查詢會回空值；頻率超限會停權一分鐘；每日連續違規會封鎖該 IP 與 ID。
- **每 24 小時要重新登入**——這對排程系統是實質的架構限制。
- 下單需要下載電子憑證並保存在本地，通過憑證驗證後才能下單與查詢帳務。

**對你的規劃的意義**

憑證必須在本地、每 24 小時要重登，這兩點基本上排除了「在 Vercel serverless 上跑 Shioaji」的可能。
如果之後真的要走自動交易，架構會變成：

```
Vercel（網站 UI + API，唯讀）
        ↕ Supabase
本地或 VPS 的常駐 worker（Shioaji 登入、憑證、下單、抓 tick）
```

這其實和 Phase 3 回測引擎需要獨立 worker 的結論一致——**同一個 worker 可以同時承擔回測與 Shioaji**。
所以在決定回測架構時就把這件事考慮進去，之後接 Shioaji 會省很多事。

**一個務實的建議**：自動交易先從「紙上交易」開始。讓系統產生訊號、記錄「如果照做會怎樣」，
跑滿三到六個月，跟你自己的實際操作比對。確認策略真的有效再接真實下單。
Shioaji 的下單 API 隨時都在，但錯誤的策略接上自動下單，虧損速度會遠快於手動。

---

## 五、回測學習路徑（給資料科學背景的人）

你有資料科學的底子，所以下面跳過 pandas 基礎，直接講金融資料特有的坑。

### 階段一：先把「正確性」的直覺建立起來

金融回測跟一般 ML 的差別，幾乎全在資料洩漏的形式上。建議依序理解這四個偏誤：

**1. 前視偏誤（Look-ahead bias）**
用當日收盤價產生訊號，卻假設當日收盤成交——實務上你在收盤那一刻才知道收盤價。
正確做法：訊號用 T 日收盤產生，成交價用 T+1 日開盤。

**2. 倖存者偏誤（Survivorship bias）**
只用「今天還存在的股票」回測，會系統性高估報酬，因為下市的都是表現最差的。
這就是為什麼 EODHD 那種「含已下市標的」的資料源值得付費。

**3. 過度擬合（Overfitting）**
這個你熟悉，但金融資料的訊噪比遠低於一般 ML 問題，過擬合的誘惑大得多。
務必保留一段完全沒參與調參的資料做樣本外驗證。
**回測的正確用途是排除明顯爛的策略，不是找到最佳策略。**

**4. 交易成本**
手續費、證交稅、滑價。你的 `services/fees.py` 已經有台股的正確算法，這是你相對於通用回測工具的優勢——
多數開源回測框架的台股成本模型都是錯的。

### 階段二：先做歸因，不要先做策略

在寫任何策略之前，先用你的 719 筆真實交易算出這些（對應 roadmap 的 Phase 1）：

- **TWR vs XIRR**：兩者的差距會告訴你「擇時能力」是正還是負。
- **對照 0050 / VOO**：把每一筆投入套用到指數上，看你贏還是輸大盤。
- **Buy-and-hold 反事實**：如果買了完全不動會怎樣。
- **處置效應檢查**：賺錢的部位平均持有多久 vs 虧錢的部位。

這一步的價值在於：它會告訴你「你的問題到底出在哪」。
如果歸因顯示你的選股其實不錯、但擇時很差，那該做的是紀律型策略（定期定額、再平衡）而不是技術指標。
**先診斷再開藥。**

### 階段三：工具選擇

| 工具 | 適合 | 不適合 |
|------|------|--------|
| `backtesting.py` | 入門、事件驅動、程式碼好讀 | 大規模參數掃描 |
| `vectorbt` | 向量化、快、參數網格掃描 | 學習曲線陡，複雜訂單邏輯難寫 |
| 自己寫 | 完全掌控成本模型 | 容易寫出有前視偏誤的 bug |

**建議**：從 `backtesting.py` 開始，因為它的事件驅動模型天然避免前視偏誤，適合建立正確的直覺。
等到要跑參數掃描才換 `vectorbt`。

不要一開始就自己寫——不是能力問題，是前視偏誤的 bug 極難自己發現。

### 階段四：評估指標

不要只看總報酬。至少要有：

- CAGR（年化報酬）
- **最大回撤（Max Drawdown）**——這決定你能不能真的抱得住
- Sharpe / Sortino
- 勝率與賺賠比（兩者要一起看，高勝率低賺賠比常是災難）
- **與 buy-and-hold 的對照**——如果贏不過買了不動，這個策略就沒有存在意義

### 推薦讀物

- **《Advances in Financial Machine Learning》**（López de Prado）——講資料洩漏與交叉驗證在金融資料上為何失效，對你的背景最對症。第 7 章的 purged cross-validation 特別重要。
- **《Systematic Trading》**（Robert Carver）——講如何不過度擬合，實務導向。
- Quantopian 的 lecture series（已停業但內容仍在 GitHub）——免費且紮實。

---

## 六、需要你決定的事

1. **美股資料源要先試 Twelve Data 嗎？** 我建議先申請免費 key 試抓一檔，確認資料品質再決定要不要付 EODHD。
2. **回測 worker 要放哪？** Railway / Fly.io 的免費或低價方案就夠，但如果之後要接 Shioaji，可能直接放本地常駐機器更合適（憑證問題）。
3. **要不要現在就開永豐戶？** 不急。Phase 0~2 完全不需要 Shioaji，等到真的要做自動交易前再開就好。

---

## 資料來源

- [Fugle 台股行情方案及價格](https://developer.fugle.tw/docs/pricing/)
- [Fugle Historical Candles 文件](https://developer.fugle.tw/docs/data/http-api/historical/candles/)
- [Shioaji 使用限制](https://sinotrade.github.io/zh/tutor/limit/)
- [永豐金證券 Python API](https://ai.sinotrade.com.tw/python/Main/index.aspx)
- [The 2026 Market Data API Scorecard（EODHD）](https://eodhd.com/financial-academy/financial-faq/the-2026-market-data-api-scorecard-comparing-6-leading-providers)
- [EODHD vs Alpha Vantage 比較（2026）](https://wire.insiderfinance.io/eodhd-vs-alpha-vantage-stock-api-comparison-2026-932de2c4a378)
- [Alpha Vantage Pricing 與替代方案](https://qveris.ai/guides/alpha-vantage-pricing-alternative/)
- [FinMind 官方網站](https://finmindtrade.com/)
