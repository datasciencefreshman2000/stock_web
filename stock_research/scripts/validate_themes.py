"""驗證 8 個主題成不成立，並檢查主題強度隨時間的變化。

用法：
    python scripts/validate_themes.py
    python scripts/validate_themes.py --source yahoo   # 或 fugle
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

from research.core import universe as uni  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PERIODS = [("2010–2016", "2010-01-01", "2016-12-31"),
           ("2017–2022", "2017-01-01", "2022-12-31"),
           ("2023–2026", "2023-01-01", "2026-12-31")]


def load(source: str) -> pd.DataFrame:
    path = DATA_DIR / ("price_history_yahoo.parquet" if source == "yahoo" else "price_history.parquet")
    if not path.exists():
        raise SystemExit(f"找不到 {path}，請先跑回補腳本")
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="yahoo", choices=["yahoo", "fugle"])
    args = p.parse_args()

    df = load(args.source)
    prices = df.pivot_table(index="date", columns="symbol", values="adj_close")
    stocks = [c for c in prices.columns if c != "TW:0050"]

    # 市場代理用等權重，而不是 0050 —— 0050 有 60% 是台積電
    rets = prices.pct_change(fill_method=None)
    ew = pd.Series(100 * np.cumprod(1 + rets[stocks].mean(axis=1).fillna(0)), index=rets.index)

    groups = [uni.to_symbols(m) for m in uni.THEMES.values()]

    print("=" * 84)
    print(f"主題驗證｜來源 {args.source}｜{prices.index.min():%Y-%m-%d} ~ {prices.index.max():%Y-%m-%d}")
    print("=" * 84)
    print("方法：先剝掉市場因子，再比較『組內殘差相關』與『跨主題配對』的基準")
    print("（直接比原始相關會誤判，因為單股 vs 多股平均不是同一個尺度）\n")
    print(f"{'主題':<12}{'檔數':>4}{'原始相關':>10}{'殘差相關':>10}{'基準':>9}{'z值':>8}  判定")
    print("-" * 84)

    results = []
    for name, members in uni.THEMES.items():
        v = uni.validate_theme(prices, uni.to_symbols(members), ew, name, control_members=groups)
        results.append((name, v))
    for name, v in sorted(results, key=lambda x: -x[1].z_score):
        print(f"{name:<12}{len(v.members):>4}{v.raw_pairwise_corr:>+10.3f}"
              f"{v.residual_pairwise_corr:>+10.3f}{v.control_corr:>+9.3f}"
              f"{v.z_score:>8.2f}  {v.verdict}")

    print("\n" + "=" * 84)
    print("主題強度隨時間變化（殘差相關的 z 值）")
    print("=" * 84)
    print(f"{'主題':<12}" + "".join(f"{lbl:>14}" for lbl, _, _ in PERIODS) + "   趨勢")
    print("-" * 84)
    for name, members in uni.THEMES.items():
        zs = []
        for _, a, b in PERIODS:
            seg = prices.loc[a:b]
            segret = seg.pct_change(fill_method=None)
            m = pd.Series(100 * np.cumprod(1 + segret[[c for c in stocks if c in seg.columns]]
                                           .mean(axis=1).fillna(0)), index=seg.index)
            try:
                zs.append(uni.validate_theme(seg, uni.to_symbols(members), m, name,
                                             control_members=groups).z_score)
            except (ValueError, KeyError):
                zs.append(float("nan"))
        arrow = "↑ 增強" if zs[-1] > zs[0] + 1 else "↓ 減弱" if zs[-1] < zs[0] - 1 else "→ 持平"
        print(f"{name:<12}" + "".join(f"{z:>14.2f}" for z in zs) + f"   {arrow}")

    print("\n" + "=" * 84)
    print("逐配對相關（剝掉市場因子後）")
    print("=" * 84)
    res = uni.market_residuals(rets[stocks], rets[stocks].mean(axis=1)).dropna()
    for name, members in uni.THEMES.items():
        syms = [s for s in uni.to_symbols(members) if s in res.columns]
        print(f"\n  {name}")
        for a, b in itertools.combinations(syms, 2):
            per = []
            for _, lo, hi in PERIODS:
                seg = res.loc[lo:hi]
                per.append(seg[a].corr(seg[b]) if len(seg) > 60 else float("nan"))
            print(f"    {uni.NAMES[a[3:]]:<7}-{uni.NAMES[b[3:]]:<7}"
                  f"  全期 {res[a].corr(res[b]):+.3f}   "
                  + "  ".join(f"{x:+.3f}" for x in per))


if __name__ == "__main__":
    main()
