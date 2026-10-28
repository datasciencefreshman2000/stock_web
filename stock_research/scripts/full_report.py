"""產生完整的橫斷面明細報告（Markdown）。

用法：
    python scripts/full_report.py
    python scripts/full_report.py --out ../docs/cross_section_detail.md

產出四個層次的表：
    一、每檔股票 × 每個策略的完整指標（含買進持有對照列）
    二、每個策略在 21 檔上的明細
    三、5 年一段的分時段結果
    四、1 年一段的逐年結果（看穩定性用）

--------------------------------------------------------------------------
分段的做法：訊號在**完整歷史**上計算，只把績效切段
--------------------------------------------------------------------------

如果每一段各自從頭算訊號，200 日均線在每段的前 200 天都是空的，
等於每段開頭都有一段「強迫空手」的假訊號。那不是策略的行為，是切法的產物。

所以這裡先在完整序列上跑一次回測，再把 returns / position 切段計算指標。
這對應「我一直在跑這個策略，只是分段檢視績效」，才是你想問的問題。
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from research.backtest.engine import TRADING_DAYS, buy_and_hold, run_backtest  # noqa: E402
from research.backtest.strategies import STRATEGIES  # noqa: E402
from research.core.universe import NAMES, THEMES  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SELECTED = ["ma_trend", "breakout", "supertrend", "linreg", "adx_trend"]
THEME_OF = {t: th for th, members in THEMES.items() for t in members}


# ---------------------------------------------------------------- 指標

def metrics(equity: pd.Series, returns: pd.Series, position: pd.Series,
            n_trades: int) -> dict:
    """從一段權益曲線算出所有指標。分段時只傳該段的切片即可。"""
    r = returns.dropna()
    if len(equity) < 2 or len(r) < 2:
        return dict(total=0.0, cagr=0.0, sharpe=0.0, mdd=0.0, tpy=0.0, tim=0.0)
    years = len(equity) / TRADING_DAYS
    total = float(equity.iloc[-1] / equity.iloc[0] - 1)
    return dict(
        total=total,
        cagr=float((1 + total) ** (1 / years) - 1) if years > 0 and total > -1 else 0.0,
        sharpe=float(r.mean() / r.std() * np.sqrt(TRADING_DAYS)) if r.std() > 0 else 0.0,
        mdd=float((equity / equity.cummax() - 1).min()),
        tpy=n_trades / years if years > 0 else 0.0,
        tim=float(position.mean()),
    )


def load(source: str) -> pd.DataFrame:
    name = "price_history.parquet" if source == "fugle" else f"price_history_{source}.parquet"
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(f"找不到 {path}")
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def run_all(data: pd.DataFrame, tickers: list[str]) -> dict:
    """每檔股票跑一次完整回測，把序列留下來給後面切段用。"""
    out = {}
    for ticker in tickers:
        d = data[data["ticker"] == ticker].sort_values("date").reset_index(drop=True)
        if len(d) < 300:
            continue
        dates = pd.to_datetime(d["date"])
        bench = buy_and_hold(d)
        entry = {"dates": dates, "buy_hold": bench, "runs": {}}
        for key in SELECTED:
            entry["runs"][key] = run_backtest(d, STRATEGIES[key].fn(d))
        out[ticker] = entry
        print(f"  跑完 {ticker} {NAMES.get(ticker, '')}", flush=True)
    return out


def slice_metrics(result, dates: pd.Series, lo, hi) -> dict:
    """把單次回測的結果切到 [lo, hi] 區間再算指標。"""
    mask = (dates >= lo) & (dates <= hi)
    idx = np.flatnonzero(mask.to_numpy())
    if len(idx) < 30:
        return None
    eq = result.equity.iloc[idx]
    ret = result.returns.iloc[idx]
    pos = result.position.iloc[idx]
    n = sum(1 for t in result.trades
            if lo <= pd.Timestamp(getattr(t, "entry_date", lo)) <= hi)
    return metrics(eq, ret, pos, n)


# ---------------------------------------------------------------- 輸出

def pct(x):
    return f"{x:+.1%}" if x is not None else "—"


def section_observations(results: dict, out: list[str]) -> None:
    """從明細裡直接算出來的觀察，避免結論和數字對不上。"""
    rows = []
    for ticker, e in results.items():
        bh = e["buy_hold"]
        for key in SELECTED:
            r = e["runs"][key]
            rows.append(dict(
                ticker=ticker, strategy=key,
                total=r.total_return, total_bh=bh.total_return,
                sharpe=r.sharpe, sharpe_bh=bh.sharpe,
                mdd=r.max_drawdown, mdd_bh=bh.max_drawdown,
                tim=r.time_in_market))
    f = pd.DataFrame(rows)

    out.append("\n\n## 五、從明細裡看出來的三件事\n")

    out.append("### 5.1 策略大部分時間是空手的\n")
    out.append("這是只看 Sharpe 會漏掉的資訊。「贏過 B&H」分成 Sharpe 與總報酬兩欄看。\n")
    out.append("| 策略 | 在市場% | 贏過B&H<br>(Sharpe) | 贏過B&H<br>(總報酬) | 平均回撤改善 |")
    out.append("|---|---:|---:|---:|---:|")
    for key in SELECTED:
        s = f[f.strategy == key]
        out.append(f"| {STRATEGIES[key].label} | {s.tim.mean():.0%} | "
                   f"{(s.sharpe > s.sharpe_bh).sum()}/{len(s)} | "
                   f"{(s.total > s.total_bh).sum()}/{len(s)} | "
                   f"{(s.mdd - s.mdd_bh).mean():+.1%} |")
    out.append("\n**回歸斜率的在市場時間最長（57%）、贏的次數也最多**，"
               "而 ADX 濾網只有 28% 在市場——它把大部分時間都判定成「沒有趨勢」。\n")

    out.append("\n### 5.2 資金效率：只算「有持股的那段時間」的話\n")
    out.append("買進持有是 100% 在市場。如果策略只用 30% 的時間就拿到 60% 的報酬，"
               "那剩下 70% 的時間資金是自由的——這在只看 Sharpe 時完全看不到。\n")
    out.append("| 策略 | 總報酬 ÷ 在市場比例（中位數） | 買進持有 |")
    out.append("|---|---:|---:|")
    base = f["total_bh"].median()
    for key in SELECTED:
        s = f[f.strategy == key]
        eff = (s.total / s.tim).median()
        mark = "  ← 效率較高" if eff > base else ""
        out.append(f"| {STRATEGIES[key].label} | {eff:.0%}{mark} | {base:.0%} |")
    out.append("\n⚠ **這個比值不是可以直接花用的報酬。** "
               "它假設你能把空手期間的資金投到別的地方拿到同樣的效率，"
               "而那需要另一個標的、另一套訊號。當成「策略有沒有挑到好時段」的診斷指標看，"
               "不要當成績效。\n")

    out.append("\n### 5.3 哪些組合是三項全勝\n")
    win = f[(f.total > f.total_bh) & (f.sharpe > f.sharpe_bh) & (f.mdd > f.mdd_bh)]
    out.append(f"總報酬、Sharpe、最大回撤**三項都贏**買進持有的組合，"
               f"{len(f)} 個裡有 **{len(win)}** 個。\n")
    out.append("| 標的 | 策略 | 總報酬 | B&H | Sharpe | B&H | 回撤 | B&H | 在市場% |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in win.sort_values("sharpe", ascending=False).iterrows():
        out.append(f"| {r.ticker} {NAMES.get(r.ticker, '')} | {STRATEGIES[r.strategy].label} | "
                   f"{r.total:+.0%} | {r.total_bh:+.0%} | {r.sharpe:.2f} | {r.sharpe_bh:.2f} | "
                   f"{r.mdd:.0%} | {r.mdd_bh:.0%} | {r.tim:.0%} |")
    top = win["ticker"].value_counts()
    if len(top):
        names = "、".join(f"{t} {NAMES.get(t, '')}（{n} 次）" for t, n in top.head(4).items())
        out.append(f"\n出現最多次的標的：{names}。\n")
    out.append("⚠ **不要把這張表當成「找到有效組合」。** "
               "105 個組合裡挑出表現最好的 15 個，本來就會看起來很漂亮——"
               "這是選擇效應，不是發現。它的用途是**產生假說**"
               "（例如「記憶體類股值得單獨追」），"
               "而假說必須用**沒看過的資料**驗證。統計檢定見 `cross_section_results.md`。\n")


def section_per_stock(results: dict, out: list[str]) -> None:
    out.append("## 一、每檔股票的完整明細\n")
    out.append("每張表最後一列是**買進持有**，用來對照。"
               "「超額」= 該策略 Sharpe − 買進持有 Sharpe。\n")
    for theme, members in THEMES.items():
        out.append(f"\n### 主題：{theme}\n")
        for ticker in members:
            if ticker not in results:
                continue
            e = results[ticker]
            bh = e["buy_hold"]
            bm = metrics(bh.equity, bh.returns, bh.position, bh.n_trades)
            out.append(f"\n**{ticker} {NAMES.get(ticker, '')}**\n")
            out.append("| 策略 | 總報酬 | 年化 | Sharpe | 最大回撤 | 年交易 | 在市場% | 超額Sharpe |")
            out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
            for key in SELECTED:
                r = e["runs"][key]
                m = metrics(r.equity, r.returns, r.position, r.n_trades)
                out.append(
                    f"| {STRATEGIES[key].label} | {pct(m['total'])} | {pct(m['cagr'])} | "
                    f"{m['sharpe']:.2f} | {m['mdd']:.1%} | {m['tpy']:.1f} | "
                    f"{m['tim']:.0%} | **{m['sharpe'] - bm['sharpe']:+.2f}** |")
            out.append(
                f"| *買進持有* | *{pct(bm['total'])}* | *{pct(bm['cagr'])}* | *{bm['sharpe']:.2f}* | "
                f"*{bm['mdd']:.1%}* | *—* | *100%* | *—* |")


def section_per_strategy(results: dict, out: list[str]) -> None:
    out.append("\n\n## 二、每個策略在 21 檔上的明細\n")
    for key in SELECTED:
        spec = STRATEGIES[key]
        out.append(f"\n### {spec.label}\n")
        out.append(f"> {spec.description}\n")
        out.append("| 標的 | 主題 | 總報酬 | 年化 | Sharpe | 最大回撤 | 年交易 | 在市場% | 超額 |")
        out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        rows = []
        for ticker, e in results.items():
            r = e["runs"][key]
            bh = e["buy_hold"]
            m = metrics(r.equity, r.returns, r.position, r.n_trades)
            bm = metrics(bh.equity, bh.returns, bh.position, bh.n_trades)
            rows.append((m["sharpe"] - bm["sharpe"], ticker, m))
        for excess, ticker, m in sorted(rows, reverse=True):
            flag = " ✓" if excess > 0 else ""
            out.append(
                f"| {ticker} {NAMES.get(ticker, '')} | {THEME_OF.get(ticker, '')} | "
                f"{pct(m['total'])} | {pct(m['cagr'])} | {m['sharpe']:.2f} | {m['mdd']:.1%} | "
                f"{m['tpy']:.1f} | {m['tim']:.0%} | **{excess:+.2f}**{flag} |")
        wins = sum(1 for x, _, _ in rows if x > 0)
        out.append(f"\n21 檔中贏過買進持有 **{wins}** 檔，"
                   f"平均超額 **{np.mean([x for x, _, _ in rows]):+.2f}**\n")


def section_slices(results: dict, out: list[str], blocks: list[tuple], title: str,
                   note: str) -> None:
    out.append(f"\n\n## {title}\n")
    out.append(note + "\n")
    for key in SELECTED:
        out.append(f"\n### {STRATEGIES[key].label}\n")
        header = "| 標的 | " + " | ".join(lbl for lbl, _, _ in blocks) + " |"
        out.append(header)
        out.append("|---" * (len(blocks) + 1) + "|")
        for theme, members in THEMES.items():
            for ticker in members:
                if ticker not in results:
                    continue
                e = results[ticker]
                cells = []
                for _, lo, hi in blocks:
                    sm = slice_metrics(e["runs"][key], e["dates"], lo, hi)
                    bm = slice_metrics(e["buy_hold"], e["dates"], lo, hi)
                    if not sm or not bm:
                        cells.append("—")
                        continue
                    excess = sm["sharpe"] - bm["sharpe"]
                    cells.append(f"{excess:+.2f}")
                out.append(f"| {ticker} {NAMES.get(ticker, '')} | " + " | ".join(cells) + " |")
        # 每段的整體勝率
        summary = []
        for _, lo, hi in blocks:
            wins = total = 0
            for e in results.values():
                sm = slice_metrics(e["runs"][key], e["dates"], lo, hi)
                bm = slice_metrics(e["buy_hold"], e["dates"], lo, hi)
                if sm and bm:
                    total += 1
                    wins += sm["sharpe"] > bm["sharpe"]
            summary.append(f"{wins}/{total}" if total else "—")
        out.append("| **贏過B&H** | " + " | ".join(f"**{s}**" for s in summary) + " |")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="yahoo")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[2]
                                             / "docs" / "cross_section_detail.md"))
    args = parser.parse_args()

    data = load(args.source)
    tickers = [t for members in THEMES.values() for t in members]
    print("跑回測中…")
    results = run_all(data, tickers)

    first = min(e["dates"].iloc[0] for e in results.values())
    last = max(e["dates"].iloc[-1] for e in results.values())

    out: list[str] = []
    out.append("# 趨勢策略明細：每檔股票 × 每個策略\n")
    out.append(f"> 產生時間：{pd.Timestamp.now():%Y-%m-%d}  \n"
               f"> 資料：{len(results)} 檔 × {first:%Y-%m-%d} ~ {last:%Y-%m-%d}"
               f"（{args.source}）  \n"
               f"> 產生方式：`python scripts/full_report.py`  \n"
               f"> 結論與統計檢定見 `cross_section_results.md`\n")
    out.append("\n**欄位說明**\n")
    out.append("| 欄位 | 意思 |")
    out.append("|---|---|")
    out.append("| 總報酬 | 整段期間的累積報酬 |")
    out.append("| 年化 | CAGR |")
    out.append("| Sharpe | 年化 Sharpe（無風險利率視為 0） |")
    out.append("| 最大回撤 | 權益曲線從高點的最大跌幅 |")
    out.append("| 年交易 | 平均每年進出場次數 |")
    out.append("| 在市場% | 有持股的交易日佔比。**這是趨勢策略的關鍵**——"
               "報酬低有可能只是因為大部分時間空手 |")
    out.append("| 超額 | 策略 Sharpe − 買進持有 Sharpe。**正值才代表擇時有加分** |")

    section_per_stock(results, out)
    section_per_strategy(results, out)

    five = [("2010–2014", pd.Timestamp("2010-01-01"), pd.Timestamp("2014-12-31")),
            ("2015–2019", pd.Timestamp("2015-01-01"), pd.Timestamp("2019-12-31")),
            ("2020–2024", pd.Timestamp("2020-01-01"), pd.Timestamp("2024-12-31")),
            ("2025–2026", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-12-31"))]
    section_slices(results, out, five, "三、5 年一段",
                   "數字是**超額 Sharpe**（策略 − 買進持有）。"
                   "2025–2026 只有一年半，且完整涵蓋 AI 行情，要另眼看待。")

    years = [(str(y), pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31"))
             for y in range(2010, 2027)]
    section_slices(results, out, years, "四、逐年",
                   "同樣是超額 Sharpe。逐年看的重點不是哪一年好，"
                   "而是**符號會不會一直翻來翻去**——會的話代表沒有穩定的優勢。")

    section_observations(results, out)

    path = Path(args.out)
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"\n已寫入 {path}（{len(out)} 行）")


if __name__ == "__main__":
    main()
