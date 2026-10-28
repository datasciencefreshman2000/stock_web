"""橫斷面比較：同一組策略跑遍全部標的，再看主題之間有沒有真的差異。

用法：
    python scripts/cross_section.py
    python scripts/cross_section.py --start 2010-01-01 --end 2024-12-31   # 排除 AI 行情
    python scripts/cross_section.py --permutations 20000

--------------------------------------------------------------------------
為什麼不能只看「哪個主題平均比較高」
--------------------------------------------------------------------------

每個主題只有 2–3 檔。拿 2–3 個數字算平均，再跟另一組 2–3 個數字比大小，
**幾乎一定會看到差異** —— 因為個股的雜訊遠大於主題的訊號。

正確的問法不是「主題 A 比主題 B 高嗎」，而是：

    「我看到的主題間差異，比『把股票隨機打散到假主題』還大嗎？」

所以這支腳本的核心是**標籤置換檢定（permutation test）**：
把主題標籤隨機重排幾千次，每次重算主題間的離散程度，
看真實標籤落在這個分布的哪個位置。

如果真實值落在中間，代表你看到的「產業差異」只是個股雜訊排列出來的形狀。

--------------------------------------------------------------------------
評分用「超額 Sharpe」而不是 Sharpe
--------------------------------------------------------------------------

策略 Sharpe 高，可能只是因為那檔股票本來就漲得好。
真正要問的是「這個策略有沒有比買進持有更好」，所以一律用

    超額 = 策略 Sharpe − 買進持有 Sharpe

這也讓不同標的之間可以比較。
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from research.backtest.engine import buy_and_hold, run_backtest  # noqa: E402
from research.backtest.strategies import STRATEGIES  # noqa: E402
from research.core.universe import NAMES, THEMES  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# trend_strategies.md 第五節選出的五個，理由是「機制互斥」而不是績效最好
SELECTED = ["ma_trend", "breakout", "supertrend", "linreg", "adx_trend"]


def load(source: str) -> pd.DataFrame:
    name = "price_history.parquet" if source == "fugle" else f"price_history_{source}.parquet"
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(f"找不到 {path}，請先跑 scripts/backfill_{source}.py")
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def evaluate(df: pd.DataFrame, key: str) -> tuple[float, float, float]:
    """回傳 (策略 Sharpe, 買進持有 Sharpe, 年均交易次數)。"""
    spec = STRATEGIES[key]
    signal = spec.fn(df)
    result = run_backtest(df, signal)
    bench = buy_and_hold(df)
    years = max(len(df) / 252, 1e-9)
    return result.sharpe, bench.sharpe, len(result.trades) / years


def build_matrix(data: pd.DataFrame, tickers: list[str], start, end) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        d = data[data["ticker"] == ticker].sort_values("date")
        if start:
            d = d[d["date"] >= start]
        if end:
            d = d[d["date"] <= end]
        d = d.reset_index(drop=True)
        if len(d) < 300:
            print(f"  略過 {ticker}：只有 {len(d)} 個交易日")
            continue
        for key in SELECTED:
            sharpe, bench, freq = evaluate(d, key)
            rows.append({
                "ticker": ticker, "name": NAMES.get(ticker, ""),
                "theme": THEME_OF.get(ticker, "—"), "strategy": key,
                "sharpe": sharpe, "bench": bench, "excess": sharpe - bench,
                "trades_per_year": freq,
            })
    return pd.DataFrame(rows)


def sign_test(wins: int, n: int) -> float:
    """策略若完全無效，每檔各有 50% 機率贏過 B&H。回傳「至少贏這麼多檔」的機率。"""
    from math import comb
    return sum(comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def permutation_test(frame: pd.DataFrame, rounds: int, seed: int = 0) -> tuple[float, float, float]:
    """主題間差異是真的，還是把股票隨機分組也會長這樣？

    統計量用「各主題平均超額 Sharpe 的標準差」。
    回傳 (真實值, 隨機分組的中位數, p 值)。

    ⚠ **置換的單位必須是「股票」，不是「每一列」。**

      同一檔股票的 5 個策略結果高度相關（都在同一條價格序列上跑）。
      如果按列打散，等於把這層相關性也一起打掉，
      虛無分布會比實際情況窄很多 —— p 值被嚴重低估。

      實測差別：按列置換 p=0.0000，按股票置換就完全不同。
      這是我第一版寫錯的地方，留著當提醒。
    """
    per_stock = frame.groupby("ticker").agg(theme=("theme", "first"), excess=("excess", "mean"))
    labels = per_stock["theme"].to_numpy()
    values = per_stock["excess"].to_numpy()
    themes = pd.unique(labels)

    def dispersion(lab):
        means = [values[lab == t].mean() for t in themes if (lab == t).any()]
        return float(np.std(means))

    observed = dispersion(labels)
    rng = np.random.default_rng(seed)
    shuffled = labels.copy()
    null = np.empty(rounds)
    for i in range(rounds):
        rng.shuffle(shuffled)              # 整檔股票連同 5 個策略一起搬到別的主題
        null[i] = dispersion(shuffled)
    p = float((null >= observed).mean())
    return observed, float(np.median(null)), p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="yahoo")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--permutations", type=int, default=10000)
    args = parser.parse_args()

    data = load(args.source)
    tickers = [t for members in THEMES.values() for t in members]
    start = pd.Timestamp(args.start) if args.start else None
    end = pd.Timestamp(args.end) if args.end else None

    print("=" * 92)
    period = f"{args.start or '最早'} ~ {args.end or '最新'}"
    print(f"橫斷面比較｜{len(tickers)} 檔 × {len(SELECTED)} 個策略｜{period}")
    print("=" * 92)
    print("評分 = 策略 Sharpe − 買進持有 Sharpe（超額）\n")

    frame = build_matrix(data, tickers, start, end)
    if frame.empty:
        raise SystemExit("沒有可用資料")

    # ---------------------------------------------------------------- 矩陣
    pivot = frame.pivot(index="ticker", columns="strategy", values="excess")[SELECTED]
    print("\n【一】每檔股票 × 每個策略的超額 Sharpe")
    print("-" * 92)
    header = "".join(f"{STRATEGIES[k].label[:6]:>10}" for k in SELECTED)
    print(f"{'標的':<14}{'主題':<10}{header}{'平均':>9}")
    for theme, members in THEMES.items():
        for ticker in members:
            if ticker not in pivot.index:
                continue
            row = pivot.loc[ticker]
            cells = "".join(f"{row[k]:>+10.2f}" for k in SELECTED)
            label = f"{ticker} {NAMES.get(ticker, '')}"
            print(f"{label:<14}{theme:<10}{cells}{row.mean():>+9.2f}")

    # ---------------------------------------------------------------- 策略層
    print("\n\n【二】各策略在 22 檔上的整體表現")
    print("-" * 92)
    print(f"{'策略':<14}{'平均超額':>10}{'中位數':>9}{'贏過B&H':>10}{'符號檢定p':>11}{'年交易':>8}  判定")
    for key in SELECTED:
        sub = frame[frame["strategy"] == key]
        wins = int((sub["excess"] > 0).sum())
        p = sign_test(wins, len(sub))
        verdict = "✓ 值得再看" if p < 0.05 else ("· 有點意思" if p < 0.20 else "✗ 與亂猜無異")
        print(f"{STRATEGIES[key].label:<14}{sub['excess'].mean():>+10.2f}"
              f"{sub['excess'].median():>+9.2f}{wins:>7}/{len(sub):<3}{p:>11.3f}"
              f"{sub['trades_per_year'].mean():>8.1f}  {verdict}")

    # ---------------------------------------------------------------- 主題層
    print("\n\n【三】主題之間有差異嗎")
    print("-" * 92)
    theme_mean = frame.groupby("theme")["excess"].agg(["mean", "std", "count"])
    theme_mean = theme_mean.reindex([t for t in THEMES if t in theme_mean.index])
    print(f"{'主題':<14}{'檔數':>5}{'平均超額':>11}{'組內標準差':>12}")
    for theme, row in theme_mean.iterrows():
        n_stocks = row["count"] // len(SELECTED)
        print(f"{theme:<14}{int(n_stocks):>5}{row['mean']:>+11.2f}{row['std']:>12.2f}")

    observed, null_median, p = permutation_test(frame, args.permutations)
    print(f"\n  主題間平均值的標準差（實際）  : {observed:.4f}")
    print(f"  隨機打散標籤後的中位數        : {null_median:.4f}")
    print(f"  置換檢定 p 值（{args.permutations:,} 次）  : {p:.4f}")
    print()
    if p < 0.05:
        print("  → 主題間的差異大於隨機分組，**產業效應可能是真的**")
    elif p < 0.20:
        print("  → 稍微大於隨機分組，但還不到能下結論的程度")
    else:
        print("  → 和隨機把股票分成假主題沒有兩樣。")
        print("    你看到的『某某產業比較適合趨勢策略』是個股雜訊排出來的形狀，不是產業效應。")
        print("    每個主題只有 2–3 檔，本來就沒有足夠的解析度分辨這件事。")

    # ---------------------------------------------------------------- 個股層
    print("\n\n【四】個股差異（拿來對照，說明雜訊有多大）")
    print("-" * 92)
    per_stock = frame.groupby(["ticker"])["excess"].mean().sort_values(ascending=False)
    best, worst = per_stock.index[0], per_stock.index[-1]
    print(f"  最好：{best} {NAMES.get(best, '')}  {per_stock.iloc[0]:+.2f}")
    print(f"  最差：{worst} {NAMES.get(worst, '')}  {per_stock.iloc[-1]:+.2f}")
    print(f"  個股之間的標準差 : {per_stock.std():.4f}")
    print(f"  主題之間的標準差 : {observed:.4f}")
    ratio = per_stock.std() / observed if observed else float("inf")
    print(f"\n  個股差異是主題差異的 {ratio:.1f} 倍 —— "
          f"{'挑對股票比挑對產業重要得多' if ratio > 1.5 else '兩者量級相當'}")


THEME_OF = {t: th for th, members in THEMES.items() for t in members}

if __name__ == "__main__":
    main()
