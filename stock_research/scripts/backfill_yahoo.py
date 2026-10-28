"""用 yfinance 回補台股日線（Fugle 的備援／交叉驗證來源）。

比 Fugle 快很多（沒有 60 次/分限制、不用分段），但**是非官方來源**，
資料品質需要驗證 —— 這正是 scripts/compare_sources.py 的用途。

用法：
    python scripts/backfill_yahoo.py                  # 8 個主題 21 檔 + 0050
    python scripts/backfill_yahoo.py --all            # 你交易過的全部 39 檔
    python scripts/backfill_yahoo.py --themes 記憶體
    python scripts/backfill_yahoo.py --start 2005-01-01
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from research.core.universe import NAMES, THEMES, diagnose  # noqa: E402
from research.ingest.yahoo import fetch_many  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT = DATA_DIR / "price_history_yahoo.parquet"
BENCHMARK = "0050"


def select(args) -> list[str]:
    if args.all:
        codes = list(NAMES)
    elif args.themes:
        codes = []
        for t in args.themes:
            if t not in THEMES:
                raise SystemExit(f"未知主題 {t}。可選：{list(THEMES)}")
            codes += THEMES[t]
    else:
        codes = [c for m in THEMES.values() for c in m]
    return sorted(set(codes) | {BENCHMARK})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--themes", nargs="*")
    p.add_argument("--start", default="2010-01-01")
    p.add_argument("--end", default=date.today().isoformat())
    args = p.parse_args()

    tickers = select(args)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Yahoo Finance 回補：{len(tickers)} 檔｜{args.start} ~ {args.end}")
    print("（非官方來源，抓完務必跑 compare_sources.py 交叉驗證）\n")

    df, results = fetch_many(tickers, args.start, args.end)

    failed = [r.ticker for r in results if not r.ok]
    if failed:
        print(f"\n✗ 失敗 {len(failed)} 檔：{', '.join(failed)}")

    if df.empty:
        print("\n完全沒抓到資料。可能是網路問題或 Yahoo 擋流量。")
        return

    df["name"] = df["ticker"].map(NAMES).fillna("")
    df = df.drop_duplicates(subset=["symbol", "date"], keep="last")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df.to_parquet(OUT, index=False)
    print(f"\n已寫入 {OUT}｜{len(df):,} 筆、{df['symbol'].nunique()} 檔")

    print("\n" + "=" * 74)
    print("各標的涵蓋範圍")
    print("=" * 74)
    s = df.groupby(["ticker", "name", "yahoo_symbol"]).agg(
        筆數=("date", "size"), 最早=("date", "min"), 最晚=("date", "max")).reset_index()
    s["年數"] = ((s["最晚"] - s["最早"]).dt.days / 365.25).round(1)
    for _, r in s.sort_values("年數").iterrows():
        flag = "  ⚠ 歷史偏短" if r["年數"] < 10 else ""
        print(f"  {r['ticker']:<7}{r['name']:<14}{r['yahoo_symbol']:<10}"
              f"{r['筆數']:>6} 筆  {r['最早']:%Y-%m-%d} ~ {r['最晚']:%Y-%m-%d}"
              f"  {r['年數']:>5.1f} 年{flag}")

    print("\n" + "=" * 74)
    print("主題可用性")
    print("=" * 74)
    years = dict(zip(s["ticker"], s["年數"]))
    for theme, members in THEMES.items():
        ok = [m for m in members if years.get(m, 0) >= 10]
        short = [f"{m}({years.get(m, 0):.1f}年)" for m in members if 0 < years.get(m, 0) < 10]
        missing = [m for m in members if m not in years]
        status = "✅" if len(ok) == len(members) else "⚠" if len(ok) >= 2 else "❌"
        note = ""
        if short:
            note += f"  歷史偏短：{', '.join(short)}"
        if missing:
            note += f"  抓不到：{', '.join(missing)}"
        print(f"  {status} {theme:<10} 可用 {len(ok)}/{len(members)} 檔{note}")

    print("\n" + "=" * 74)
    print("股票池診斷")
    print("=" * 74)
    print(diagnose(df).report())

    print("\n下一步：")
    print("  1. python scripts/backfill_daily.py     # 抓 Fugle 版本")
    print("  2. python scripts/compare_sources.py    # 交叉驗證兩個來源")


if __name__ == "__main__":
    main()
