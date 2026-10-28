"""策略探索器。

選標的 × 選策略 × 選參數 → 看過去表現，順便看現在的訊號狀態。

用法：
    # 一檔股票上，所有策略的比較
    python scripts/explore.py --ticker 2408

    # 單一策略的參數掃描（看有沒有「平原」）
    python scripts/explore.py --ticker 2408 --strategy ma_trend

    # 同一策略跨整個主題
    python scripts/explore.py --strategy ma_trend --theme 記憶體

    # 同一策略跨全部 8 個主題（跨主題一致性檢驗）
    python scripts/explore.py --strategy ma_trend --all-themes

    # 只看現在的訊號狀態
    python scripts/explore.py --ticker 2408 --now

    # 換時間維度
    python scripts/explore.py --ticker 2408 --start 2018-01-01
    python scripts/explore.py --ticker 2408 --by-period
"""

import argparse
import itertools
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()
warnings.filterwarnings("ignore")

from research.backtest.engine import buy_and_hold, run_backtest  # noqa: E402
from research.backtest.strategies import STRATEGIES  # noqa: E402
from research.core import stats  # noqa: E402
from research.core.universe import NAMES, THEMES  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ETF = {"0050", "00981A"}
PERIODS = [("2010–2016", "2010-01-01", "2016-12-31"),
           ("2017–2022", "2017-01-01", "2022-12-31"),
           ("2023–2026", "2023-01-01", "2026-12-31")]


def load(source: str) -> pd.DataFrame:
    for name in ([f"price_history_{source}.parquet"] if source != "fugle"
                 else ["price_history.parquet"]):
        p = DATA_DIR / name
        if p.exists():
            df = pd.read_parquet(p)
            df["date"] = pd.to_datetime(df["date"])
            return df
    raise SystemExit(f"找不到資料檔，請先跑 scripts/backfill_{source}.py")


def slice_one(df: pd.DataFrame, ticker: str, start=None, end=None) -> pd.DataFrame:
    d = df[df["ticker"] == ticker].sort_values("date")
    if start:
        d = d[d["date"] >= start]
    if end:
        d = d[d["date"] <= end]
    return d.reset_index(drop=True)


def costs_for(ticker: str) -> dict:
    """實際費率取自你的交易紀錄（0.1395%，接近無折扣），不是理論 6 折。"""
    return {"cost_per_side": 0.001395, "sell_tax": 0.001 if ticker in ETF else 0.003}


def evaluate(d: pd.DataFrame, ticker: str, key: str, **params) -> dict | None:
    if len(d) < 300:
        return None
    spec = STRATEGIES[key]
    sig = spec.fn(d, **params)
    res = run_backtest(d, sig, **costs_for(ticker))
    bh = buy_and_hold(d, costs_for(ticker)["cost_per_side"])
    return {
        "sharpe": res.sharpe, "cagr": res.cagr, "mdd": res.max_drawdown,
        "trades_yr": res.trades_per_year, "win": res.win_rate,
        "in_mkt": res.time_in_market, "blocked": res.blocked,
        "bh_sharpe": bh.sharpe, "bh_cagr": bh.cagr, "bh_mdd": bh.max_drawdown,
        "edge": res.sharpe - bh.sharpe, "result": res, "signal": sig,
    }


# ------------------------------------------------------------------ 輸出


def show_all_strategies(df, ticker, start, end):
    d = slice_one(df, ticker, start, end)
    if d.empty:
        raise SystemExit(f"沒有 {ticker} 的資料")
    bh = buy_and_hold(d, costs_for(ticker)["cost_per_side"])
    print("=" * 92)
    print(f"{ticker} {NAMES.get(ticker,'')}｜{d['date'].min():%Y-%m-%d} ~ {d['date'].max():%Y-%m-%d}"
          f"｜{len(d):,} 個交易日")
    print("=" * 92)
    print(f"{'策略':<16}{'Sharpe':>8}{'年化':>9}{'最大回撤':>10}{'年交易':>8}"
          f"{'勝率':>7}{'在市場':>8}{'贏過B&H':>9}")
    print("-" * 92)
    print(f"{'買進持有(基準)':<16}{bh.sharpe:>8.2f}{bh.cagr:>9.1%}{bh.max_drawdown:>10.1%}"
          f"{0:>8.1f}{'-':>7}{'100%':>8}{'-':>9}")
    rows = []
    for key, spec in STRATEGIES.items():
        r = evaluate(d, ticker, key)      # 用預設參數
        if r:
            rows.append((spec.label, r))
    for label, r in sorted(rows, key=lambda x: -x[1]["sharpe"]):
        mark = "  ✓" if r["edge"] > 0 else ""
        print(f"{label:<16}{r['sharpe']:>8.2f}{r['cagr']:>9.1%}{r['mdd']:>10.1%}"
              f"{r['trades_yr']:>8.1f}{r['win']:>7.0%}{r['in_mkt']:>8.0%}"
              f"{r['edge']:>+9.2f}{mark}")
    print("\n  ※ 以上用各策略的預設參數，未經任何調整。")
    print("  ※ 「贏過B&H」為正才有討論價值。")


def show_param_sweep(df, ticker, key, start, end):
    d = slice_one(df, ticker, start, end)
    spec = STRATEGIES[key]
    names = list(spec.grid)
    combos = list(itertools.product(*(spec.grid[n] for n in names)))
    bh = buy_and_hold(d, costs_for(ticker)["cost_per_side"])

    print("=" * 92)
    print(f"{ticker} {NAMES.get(ticker,'')}｜{spec.label}｜參數掃描")
    print(f"{spec.description}")
    print(f"期間 {d['date'].min():%Y-%m-%d} ~ {d['date'].max():%Y-%m-%d}"
          f"｜買進持有 Sharpe {bh.sharpe:.2f}")
    print("=" * 92)

    results = []
    for combo in combos:
        params = dict(zip(names, combo))
        r = evaluate(d, ticker, key, **params)
        if r:
            results.append((params, r))

    if len(names) == 2:                     # 二維 → 印成矩陣
        a, b = names
        av, bv = spec.grid[a], spec.grid[b]
        print(f"\nSharpe 矩陣（列={a}，欄={b}）")
        print(f"{'':>10}" + "".join(f"{str(x):>9}" for x in bv))
        for x in av:
            line = f"{str(x):>10}"
            for y in bv:
                m = [r for p, r in results if p[a] == x and p[b] == y]
                line += f"{m[0]['sharpe']:>9.2f}" if m else f"{'-':>9}"
            print(line)

    print(f"\n{'排名':<5}{'參數':<34}{'Sharpe':>8}{'年化':>9}{'回撤':>9}{'年交易':>8}{'贏B&H':>8}")
    print("-" * 92)
    for i, (p, r) in enumerate(sorted(results, key=lambda x: -x[1]["sharpe"])[:10], 1):
        ps = ", ".join(f"{k}={v}" for k, v in p.items())
        print(f"{i:<5}{ps:<34}{r['sharpe']:>8.2f}{r['cagr']:>9.1%}"
              f"{r['mdd']:>9.1%}{r['trades_yr']:>8.1f}{r['edge']:>+8.2f}")

    sh = [r["sharpe"] for _, r in results]
    best = max(sh)
    print(f"\n  掃描了 {len(results)} 組參數")
    print(f"  Sharpe 分布：最佳 {best:.2f}｜中位數 {np.median(sh):.2f}｜最差 {min(sh):.2f}")

    nt = stats.null_distribution_test(best, len(d) // 20, max(len(results), 1),
                                      n_simulations=600, periods_per_year=12)
    print(f"\n  【多重測試檢定】試了 {len(results)} 組參數")
    print(f"  純運氣的 95 百分位：{nt.null_p95:.2f}")
    if best > nt.null_p95:
        print(f"  → 最佳結果 {best:.2f} 超過門檻，值得繼續看")
    else:
        print(f"  → 最佳結果 {best:.2f} **沒有超過門檻**，這個數字用擲骰子就做得出來")

    spread = np.std(sh)
    print(f"\n  參數穩定度：Sharpe 標準差 {spread:.3f}")
    print("  → 平原（標準差小）比山峰（標準差大）可信" if spread < 0.15
          else "  → ⚠ 參數之間差異大，很可能是在擬合雜訊")


def show_across(df, key, tickers, label, start, end):
    spec = STRATEGIES[key]
    print("=" * 92)
    print(f"{spec.label}｜跨 {label}｜{len(tickers)} 檔")
    print(f"{spec.description}")
    print("=" * 92)
    print(f"{'標的':<16}{'Sharpe':>8}{'B&H':>8}{'贏B&H':>8}{'年化':>9}{'回撤':>9}{'年交易':>8}")
    print("-" * 92)
    wins = 0
    rows = []
    for t in tickers:
        d = slice_one(df, t, start, end)
        r = evaluate(d, t, key)
        if not r:
            print(f"{t} {NAMES.get(t,''):<10}  資料不足")
            continue
        wins += r["edge"] > 0
        rows.append(r)
        mark = "  ✓" if r["edge"] > 0 else ""
        print(f"{t+' '+NAMES.get(t,''):<16}{r['sharpe']:>8.2f}{r['bh_sharpe']:>8.2f}"
              f"{r['edge']:>+8.2f}{r['cagr']:>9.1%}{r['mdd']:>9.1%}{r['trades_yr']:>8.1f}{mark}")

    n = len(rows)
    if n:
        from math import comb
        p = sum(comb(n, k) for k in range(wins, n + 1)) / 2 ** n
        print(f"\n  {n} 檔中有 {wins} 檔贏過買進持有")
        print(f"  若策略完全無效（每檔 50% 機率），出現這個結果的機率 = {p:.1%}")
        verdict = ("強證據" if p < 0.05 else "有點意思" if p < 0.20 else "沒有意義")
        print(f"  → {verdict}")
        print(f"\n  平均 Sharpe {np.mean([r['sharpe'] for r in rows]):.2f}"
              f"｜平均贏過 B&H {np.mean([r['edge'] for r in rows]):+.2f}")


def _windows(mode: str, lo: pd.Timestamp, hi: pd.Timestamp) -> list[tuple]:
    out = [("全期間", lo, hi)]
    if mode in ("5y", "all"):
        y = lo.year
        while y <= hi.year:
            a, b = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{min(y+4, hi.year)}-12-31")
            if b > lo:
                out.append((f"{y}–{min(y+4, hi.year)}", max(a, lo), min(b, hi)))
            y += 5
    if mode in ("1y", "all"):
        for y in range(lo.year, hi.year + 1):
            a, b = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31")
            if b > lo:
                out.append((str(y), max(a, lo), min(b, hi)))
    return out


def show_time_slices(df, ticker, key, mode, start, end):
    """同一策略在不同時間窗的表現。

    重點是找出「這個策略是不是只靠某一兩年撐起來的」。
    """
    spec = STRATEGIES[key]
    full = slice_one(df, ticker, start, end)
    lo, hi = full["date"].min(), full["date"].max()

    print("=" * 96)
    print(f"{ticker} {NAMES.get(ticker,'')}｜{spec.label}｜分時段表現")
    print(f"{spec.description}")
    print("=" * 96)
    print(f"{'期間':<13}{'交易日':>7}{'Sharpe':>9}{'B&H':>9}{'贏B&H':>9}"
          f"{'策略年化':>10}{'B&H年化':>10}{'回撤':>9}{'交易':>6}")
    print("-" * 96)

    yearly = []
    for label, a, b in _windows(mode, lo, hi):
        d = slice_one(df, ticker, a, b)
        if len(d) < 60:
            continue
        # 短窗要放寬最小長度限制
        spec_sig = spec.fn(d)
        res = run_backtest(d, spec_sig, **costs_for(ticker))
        bh = buy_and_hold(d, costs_for(ticker)["cost_per_side"])
        edge = res.sharpe - bh.sharpe
        mark = ""
        if label.isdigit() and int(label) >= 2025:
            mark = "  ← AI 行情"
        if len(label) == 4 and label.isdigit():
            yearly.append((label, res.sharpe, bh.sharpe, res.cagr, edge))
        if label == "全期間":
            print("-" * 96)
        print(f"{label:<13}{len(d):>7}{res.sharpe:>9.2f}{bh.sharpe:>9.2f}{edge:>+9.2f}"
              f"{res.cagr:>10.1%}{bh.cagr:>10.1%}{res.max_drawdown:>9.1%}"
              f"{res.n_trades:>6}{mark}")

    if len(yearly) >= 4:
        print("\n" + "=" * 96)
        print("排除近期 AI 行情後的樣貌")
        print("=" * 96)
        recent = [y for y in yearly if int(y[0]) >= 2025]
        older = [y for y in yearly if int(y[0]) < 2025]
        for name, grp in [("2025 年以前", older), ("2025–2026", recent)]:
            if not grp:
                continue
            s = np.mean([g[1] for g in grp]); b = np.mean([g[2] for g in grp])
            e = np.mean([g[4] for g in grp]); w = sum(1 for g in grp if g[4] > 0)
            print(f"  {name:<12} {len(grp):>2} 年｜平均 Sharpe {s:>6.2f}"
                  f"｜B&H {b:>6.2f}｜平均贏 {e:>+6.2f}｜贏過 B&H {w}/{len(grp)} 年")
        if older and recent:
            gap = np.mean([g[1] for g in recent]) - np.mean([g[1] for g in older])
            print(f"\n  近兩年比先前高 {gap:+.2f} Sharpe")
            if gap > 0.5:
                print("  ⚠ 這個策略的表現高度集中在 2025–2026，"
                      "全期間的數字被近期行情灌水，不要據此推論未來")
            else:
                print("  → 近期沒有異常灌水，全期間數字相對可信")


def show_by_period(df, ticker, key, start, end):
    spec = STRATEGIES[key]
    print("=" * 92)
    print(f"{ticker} {NAMES.get(ticker,'')}｜{spec.label}｜分期表現")
    print("=" * 92)
    print(f"{'期間':<14}{'Sharpe':>9}{'B&H':>9}{'贏B&H':>9}{'年化':>10}{'回撤':>10}{'年交易':>9}")
    print("-" * 92)
    for label, a, b in PERIODS:
        d = slice_one(df, ticker, a, b)
        r = evaluate(d, ticker, key)
        if not r:
            print(f"{label:<14}  資料不足")
            continue
        print(f"{label:<14}{r['sharpe']:>9.2f}{r['bh_sharpe']:>9.2f}{r['edge']:>+9.2f}"
              f"{r['cagr']:>10.1%}{r['mdd']:>10.1%}{r['trades_yr']:>9.1f}")
    print("\n  ※ 只在某一段有效的策略，通常是那段期間的巧合。")


def show_now(df, ticker, key, start, end):
    d = slice_one(df, ticker, start, end)
    keys = [key] if key else list(STRATEGIES)
    print("=" * 92)
    print(f"{ticker} {NAMES.get(ticker,'')}｜目前訊號狀態"
          f"（資料截至 {d['date'].max():%Y-%m-%d}）")
    print("=" * 92)
    px = d["close"].iloc[-1]
    print(f"  收盤價 {px:,.2f}\n")
    print(f"{'策略':<16}{'現在':<8}{'維持':>8}{'這段期間股價':>13}{'意義':<10}{'歷史Sharpe':>11}")
    print("-" * 92)
    for k in keys:
        spec = STRATEGIES[k]
        r = evaluate(d, ticker, k)
        if not r:
            continue
        sig = r["signal"]
        cur = sig.iloc[-1] > 0.5
        flip = sig.iloc[::-1].ne(sig.iloc[-1]).idxmax() if sig.nunique() > 1 else sig.index[0]
        days = int((sig.index[-1] - flip).days) if flip != sig.index[-1] else 0
        since_px = d.set_index("date")["close"].asof(flip)
        chg = px / since_px - 1 if since_px and np.isfinite(since_px) else np.nan
        state = "持有" if cur else "空手"
        meaning = "已賺到" if cur else "已錯過"
        print(f"{spec.label:<16}{state:<8}{days:>6} 天{chg:>13.1%}  {meaning:<10}{r['sharpe']:>11.2f}")
    print("\n  ※ 「現在」只是訊號狀態，不是建議。")
    print("  ※ 空手的策略，那個報酬是它讓你錯過的；持有的，是它讓你賺到的。")
    print("  ※ 右邊的歷史 Sharpe 才是判斷這個訊號值不值得聽的依據。")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker")
    p.add_argument("--strategy", choices=list(STRATEGIES))
    p.add_argument("--theme", choices=list(THEMES))
    p.add_argument("--all-themes", action="store_true")
    p.add_argument("--now", action="store_true")
    p.add_argument("--by-period", action="store_true")
    p.add_argument("--slices", choices=["1y", "5y", "all"],
                   help="分時段回測：1y 每年、5y 每五年、all 兩者都跑")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--source", default="yahoo")
    p.add_argument("--list", action="store_true", help="列出可用策略與標的")
    args = p.parse_args()

    if args.list:
        print("可用策略：")
        for k, s in STRATEGIES.items():
            print(f"  {k:<16}{s.label:<14}{s.description}")
        print("\n可用主題：")
        for t, m in THEMES.items():
            print(f"  {t:<12}{'、'.join(f'{c} {NAMES[c]}' for c in m)}")
        return

    df = load(args.source)

    if args.all_themes and args.strategy:
        for t, members in THEMES.items():
            show_across(df, args.strategy, members, f"主題「{t}」", args.start, args.end)
            print()
    elif args.theme and args.strategy:
        show_across(df, args.strategy, THEMES[args.theme], f"主題「{args.theme}」",
                    args.start, args.end)
    elif args.ticker and args.now:
        show_now(df, args.ticker, args.strategy, args.start, args.end)
    elif args.ticker and args.strategy and args.slices:
        show_time_slices(df, args.ticker, args.strategy, args.slices, args.start, args.end)
    elif args.ticker and args.strategy and args.by_period:
        show_by_period(df, args.ticker, args.strategy, args.start, args.end)
    elif args.ticker and args.strategy:
        show_param_sweep(df, args.ticker, args.strategy, args.start, args.end)
    elif args.ticker:
        show_all_strategies(df, args.ticker, args.start, args.end)
    else:
        p.print_help()
        print("\n先試試：python scripts/explore.py --list")


if __name__ == "__main__":
    main()
