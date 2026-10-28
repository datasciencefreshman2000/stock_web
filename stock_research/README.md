# stock_research

台股回測與訊號研究。與 `stock_site`（網站）分開，因為相依套件與執行方式完全不同。

## 為什麼獨立成一個專案

- 需要 `pandas` / `numpy` / `scikit-learn`，會讓 Vercel 的 Python bundle 爆掉
- 執行時間動輒數分鐘，serverless 上限 10–60 秒
- 職責清楚：網站負責顯示，這裡負責運算

結果最終寫回 Supabase，網站只讀。

## 安裝

```bash
cd stock_research
pip install -r requirements.txt
```

## 跑第一個研究

```bash
# 沒有真實資料時會自動用合成資料，整條管線照樣跑得起來
python studies/01_short_term_reversal.py

# 健全性檢查：植入一個真的存在的反轉效應，確認程式找得到
python studies/01_short_term_reversal.py --synthetic-edge 0.08

# 樣本外驗證（只能跑一次！）
python studies/01_short_term_reversal.py --final
```

**健全性檢查很重要。** 如果連刻意植入的訊號都找不到，
那你在真實資料上「找到」的東西更不可信。

## 目錄

```
research/core/
├── costs.py      台股成本模型（來回 0.471%）
├── labeling.py   Triple-barrier 標籤
├── cv.py         Purged / embargoed 時序切分
├── stats.py      Null 分布檢定、Sharpe 標準誤
├── journal.py    研究日誌（強迫記錄試了幾個變體）
└── data.py       資料載入（本地快取 → Supabase → 合成）

studies/          一個檔案一個研究題目
journal/          研究記錄（JSON），不要手動改
data/             本地 parquet 快取（gitignore）
tests/            核心工具的測試
```

## 三條不能破的規則

**1. 記錄你試了幾個變體**

每呼叫一次 `log.record()` 就是一個變體。這個數字決定你的結果要多好才算數。

真實優勢 = 0 的策略，試 50 個變體取最好的，平均 Sharpe 會是 **0.58**；
試 500 個會是 **0.77**。不記錄這個數字，你會把運氣當成發現。

**2. 樣本外只能用一次**

`ResearchLog.mark_out_of_sample_used()` 第二次呼叫會直接拋錯，這是刻意的。

樣本外結果不理想 → 回去調參 → 再驗一次，這樣做過一次，
樣本外就跟樣本內沒兩樣，你等於白做。

**3. 一定要有對照組**

「這批股票平均漲 1.6%」沒有意義，除非你同時知道「全部股票平均漲 0.6%」。

`studies/01` 的第 3 階段就示範了這件事——少了對照組那一行，
整個結論都是錯的。

## 測試

```bash
python -m pytest tests/ -q
```

## 相關文件

- [`../docs/backtest_methodology.md`](../docs/backtest_methodology.md) —— 方法論，含兩個實測模擬
- [`../docs/taiwan_data_and_backtest_plan.md`](../docs/taiwan_data_and_backtest_plan.md) —— 資料層規劃
- [`../docs/momentum_and_regime.md`](../docs/momentum_and_regime.md) —— 動能、總經格局、避險
