# 快取設計與更新頻率

> 2026-10-28 更新：帳務寫入已改為 DB transaction、operation_id 去重及 revision 失效；快取只發布與起始版本一致的重算結果。以下保留舊設計背景，目前行為以 [修正說明](fixes_2026-10-28.md) 為準。

> 日期：2026-08-04

---

## 一、連續記帳不用等：延遲合併失效

### 問題

原本每存一筆就 `invalidateMoney()`，等於每筆都觸發一輪重算。
連記 10 筆支出 = 10 輪。

### 作法

新增 `useDeferredInvalidate(delay)`：呼叫時不立刻失效，而是排一個計時器，
期間內再次呼叫就把計時器重設。

```
記第 1 筆 → 排 1.5 秒後失效
記第 2 筆 → 取消上一個，重排
...
記第 10 筆 → 排 1.5 秒
停手 1.5 秒 → 只失效「一次」
```

三個 API：

| | |
|---|---|
| `schedule(scope)` | 排定延遲失效 |
| `flush()` | 立刻執行（例如按下完成鍵） |
| `pending` | 是否還在排隊，可拿來顯示「同步中…」 |

**離開頁面時會自動補做**（`useEffect` 的 cleanup），所以不會漏掉。

現金頁的 header 現在會在排隊時顯示「同步中…」，你就知道還沒寫完。

---

## 二、記帳按鈕

現金頁 header 的「記帳紀錄」旁邊多了一顆綠色的「記帳」。
按下去會直接展開下方的資金移動面板並切到**支出**模式。

實作方式：`CapitalMovementPanel` 新增兩個 prop。

```jsx
<CapitalMovementPanel
  openSignal={ledgerSignal}   // 遞增的數字，變動就觸發
  openMode="expense"          // 要切到哪個模式
/>
```

用**遞增計數器**而不是布林值，這樣連按第二次也有效
（布林值第二次按下去值沒變，就不會觸發）。

---

## 三、`clear_summary_cache()` 該怎麼改（你問的那題）

### 原本的問題

```python
# 寫入時
clear_summary_cache()      # 直接刪掉快取

# 下一個 GET
if not cached:
    calculate_summary()    # 約 11 次 DB 往返，讀全部交易、跑 FIFO…
```

**但改現金餘額根本不影響 FIFO。** 沒有理由重跑那一整套。

### 三種可能的做法

| 做法 | 優點 | 缺點 |
|---|---|---|
| **A. 刪除**（原本） | 簡單、絕不會錯 | 下一個 GET 必須完整重算 |
| **B. 標記過期但仍可讀** | GET 立刻回應 | 你剛改的東西不會馬上反映，要等排程 |
| **C. 就地更新（patch）** | 立刻正確、成本低 | 要想清楚「什麼影響什麼」 |

**我選 C。** B 的問題是你改完看不到變化，體驗更差。

### C 怎麼實作

關鍵是把資料分成兩半：

```
貴的一半（要跑 FIFO）        便宜的一半
  accounts[].cost              cash
  accounts[].realized_pnl      investments
  accounts[].market_value      invested
  holdings                     total_assets
```

**只有交易紀錄與除權息事件會動到「貴的一半」。**
現金、基金現值、資金移動只動到「便宜的一半」。

所以：

```python
# services/cache_patch.py
def refresh_cash_and_manual_in_cache() -> bool:
    cached = get_summary_cache()
    if not cached:
        return False                      # 沒快取可 patch，回 False

    usd_rate = cached["usd_rate"]         # 沿用快取裡的匯率，不重查

    # 只重算便宜的部分
    cash = cash_summary(list_cash_accounts(), usd_rate)
    investments = [...]

    # 帳戶（FIFO 結果）原封不動沿用
    own_account_total = sum(cached["accounts"][a]["account_total_twd"] ...)

    patch_summary_cache({"cash": cash, "investments": ..., "total_assets": ...})
    return True
```

路由端：

```python
def money_changed() -> None:
    try:
        if refresh_cash_and_manual_in_cache():
            return
    except Exception:
        pass
    clear_summary_cache()     # 兩層退路
```

**兩層退路很重要**：
1. 沒有快取可 patch → 刪除，讓下次 GET 重建
2. patch 過程出任何錯 → 也刪除

**快取算錯比慢更糟。** 寧可退回重算，也不要留下不一致的數字。

### 成本比較

| 動作 | 修正前 | 修正後 |
|---|---:|---:|
| 改一筆現金後的下一個 GET | 11 次往返（完整重算） | **0 次**（快取已是最新） |
| 寫入本身 | 2 次 | 5 次（patch） |
| **合計** | **13** | **5** |

> ⚠ **2026-08-06 更正**：上表的「5 次」是我沒實際量就寫下的。
> 真正跑起來是 **19 次** —— 因為 `patch_summary_cache()` 內部自己會先
> `get` 一次，四把快取各呼叫一次就是 12 次純快取往返，比它要取代的
> 完整重算還貴。已改成批次讀寫，實測降到 9 次。
> 細節見 `performance_audit.md` 第八節。

有 8 個測試守著這個行為，其中最重要的一條是
`test_preserves_fifo_derived_fields`——確認 patch 之後
`accounts` 區塊**完全沒被動到**。

### 什麼時候仍然會完整重算

- 新增／修改／刪除**交易**（FIFO 會變）
- 新增／刪除**除權息事件**
- 快取本身不存在（第一次進站、或排程剛清過）

這些沒辦法避免，也不該避免。

---

## 四、怎麼提升自動更新頻率（你的第二個問題）

有兩個獨立的「更新頻率」，常被混在一起。

### 頻率一：後端多久去抓一次新股價

由 **Cloudflare Worker 的 cron** 決定。目前排程（`cloudflare/cron-worker/README.md`）：

```
0 * * * *              每小時整點 → /jobs/snapshot
10,20,30,40,50 1 * * * 台北 09:10–09:50 → /jobs/refresh
30,40,50 13 * * *      台北 21:30–21:50
10,20,30 14 * * *      台北 22:10–22:30
```

而且台北 04:00–08:00、14:30–20:30 會跳過。

**想更頻繁，改 cron 運算式就好**，例如台股盤中每 5 分鐘：

```
*/5 1-5 * * *          台北 09:00–13:59，每 5 分鐘
```

**額度夠嗎？** 夠。

| | |
|---|---|
| Fugle 免費方案 | 60 次/分鐘 |
| 你的台股標的 | 21 檔 |
| 每次刷新用掉 | 21 次 |

每 5 分鐘跑一次完全在額度內。Cloudflare 免費方案的 cron 也支援每分鐘。

**但要注意**：每次 `/jobs/refresh` 會重算 summary + 3 個 portfolio，
約 40 次 Supabase 往返。每 5 分鐘一次 = 一天約 100 次 × 40 = 4000 次。
Supabase 免費方案撐得住，但不是零成本。

**我的建議**：盤中每 10 分鐘就很夠了。日線策略不需要更即時。

### 頻率二：你打開著頁面時，畫面多久自己更新

由 **TanStack Query** 決定。目前設定（`lib/queryClient.js`）：

```javascript
staleTime: 5 * 60 * 1000,        // 5 分鐘內視為新鮮，不重打
refetchOnWindowFocus: false,     // 切回分頁時不重打
```

也就是說**畫面現在完全不會自己更新**，除非你重整或觸發失效。

三個可調的開關：

```javascript
{
  staleTime: 60 * 1000,          // 縮短到 1 分鐘
  refetchInterval: 60 * 1000,    // 每分鐘自動重打（新增）
  refetchOnWindowFocus: true,    // 切回分頁時重打（新增）
}
```

| 設定 | 效果 | 代價 |
|---|---|---|
| `refetchOnWindowFocus: true` | 從別的分頁切回來時自動更新 | 幾乎零成本，**最推薦先開這個** |
| `refetchInterval: 60000` | 開著頁面時每分鐘自動更新 | 每分鐘 1 次 GET（讀快取，很便宜） |
| `staleTime` 縮短 | 切頁時更容易重打 | 切頁變慢 |

**重要**：`refetchInterval` 只是重讀**快取**，不會去抓新股價。
所以它只有在後端 cron 有更新的情況下才會看到新數字。
兩個頻率要一起調才有意義。

### 建議組合

```
後端 cron：盤中每 10 分鐘 refresh
前端：refetchOnWindowFocus: true
      refetchInterval: 2 分鐘（只在 Dashboard 開啟時）
```

這樣切回分頁就是最新的，開著也會慢慢跟上，而且成本很低。

**要我直接改嗎？** 這兩個都是一行設定的事，但會影響 API 用量，
所以我先問你要哪個組合。

---

## 五、這次改動的驗證

- 後端：75 個測試通過（新增 8 個 cache patch 測試）、ruff 乾淨
- 前端：隔離環境真實 `vite build` 成功

### 順帶抓到並修掉的一個 bug

我用批次取代把 `clear_summary_cache()` 換成 `money_changed()` 時，
不小心把 `money_changed()` **自己內部**的那一行也換掉了：

```python
def money_changed():
    if not refresh_cash_and_manual_in_cache():
        money_changed()      # ← 無限遞迴
```

已修正。這也提醒我批次取代要看清楚範圍。
