"""交叉驗證 Fugle 與 Yahoo 兩個資料來源。

為什麼要做這件事：

  yfinance 是**非官方**來源，Yahoo 的台股資料在幾個地方常出問題：
    - 成交量單位（股 vs 張）
    - 除權息還原的方式與台灣慣例不同
    - 停牌／處置股的處理
    - 上櫃股票的資料完整度

  單一來源你永遠不知道它錯在哪。兩個獨立來源對不起來的地方，
  就是資料品質問題的位置。這是專業做法，不是龜毛。

用法：
    python scripts/compare_sources.py
    python scripts/compare_sources.py --tolerance 0.005
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from research.core.universe import NAMES  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FUGLE = DATA_DIR / "price_history.parquet"
YAHOO = DATA_DIR / "price_history_yahoo.parquet"


def compare_symbol(f: pd.DataFrame, y: pd.DataFrame, tol: float) -> dict:
    merged = f.merge(y, on="date", suffixes=("_f", "_y"), how="outer", indicator=True)
    both = merged[merged["_merge"] == "both"]
    only_f = int((merged["_merge"] == "left_only").sum())
    only_y = int((merged["_merge"] == "right_only").sum())

    res = {"共同日數": len(both), "只有Fugle": only_f, "只有Yahoo": only_y}
    if both.empty:
        return res | {"收盤價不符": None, "最大價差": None, "成交量比值中位數": None}

    rel = (both["close_f"] - both["close_y"]).abs() / both["close_y"].replace(0, np.nan)
    res["收盤價不符"] = int((rel > tol).sum())
    res["最大價差"] = float(rel.max()) if rel.notna().any() else None

    vf, vy = both["volume_f"], both["volume_y"]
    valid = (vy > 0) & vf.notna()
    res["成交量比值中位數"] = float((vf[valid] / vy[valid]).median()) if valid.any() else None
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tolerance", type=float, default=0.002, help="收盤價相對誤差容許值")
    args = p.parse_args()

    missing = [str(x) for x in (FUGLE, YAHOO) if not x.exists()]
    if missing:
        print("缺少檔案：")
        for m in missing:
            print(f"  {m}")
        print("\n請先執行：")
        print("  python scripts/backfill_daily.py    # Fugle")
        print("  python scripts/backfill_yahoo.py    # Yahoo")
        raise SystemExit(1)

    fug = pd.read_parquet(FUGLE)
    yah = pd.read_parquet(YAHOO)
    for d in (fug, yah):
        d["date"] = pd.to_datetime(d["date"])

    symbols = sorted(set(fug["symbol"]) & set(yah["symbol"]))
    print("=" * 88)
    print(f"來源交叉驗證｜共同標的 {len(symbols)} 檔｜容許誤差 {args.tolerance:.2%}")
    print("=" * 88)
    print(f"{'代號':<8}{'名稱':<13}{'共同日數':>9}{'只有F':>7}{'只有Y':>7}"
          f"{'價差超標':>9}{'最大價差':>10}{'量比值':>9}")
    print("-" * 88)

    flags = []
    for sym in symbols:
        ticker = sym.replace("TW:", "")
        cols = ["date", "close", "volume"]
        f = fug[fug["symbol"] == sym][cols].dropna(subset=["close"])
        y = yah[yah["symbol"] == sym][cols].dropna(subset=["close"])
        r = compare_symbol(f, y, args.tolerance)

        bad = r["收盤價不符"] or 0
        pct = bad / max(r["共同日數"], 1)
        mark = "  ⚠" if pct > 0.01 else ""
        if pct > 0.01:
            flags.append((ticker, f"{pct:.1%} 的交易日收盤價對不起來"))
        if r["成交量比值中位數"] and not (0.9 < r["成交量比值中位數"] < 1.1):
            flags.append((ticker, f"成交量比值 {r['成交量比值中位數']:.3f}，單位可能不同"))

        print(f"{ticker:<8}{NAMES.get(ticker,''):<13}{r['共同日數']:>9,}"
              f"{r['只有Fugle']:>7}{r['只有Yahoo']:>7}{bad:>9}"
              f"{(r['最大價差'] or 0):>9.2%}"
              f"{(r['成交量比值中位數'] or float('nan')):>9.3f}{mark}")

    print("\n" + "=" * 88)
    if flags:
        print("需要注意的項目")
        print("=" * 88)
        for t, msg in flags:
            print(f"  {t} {NAMES.get(t,'')}：{msg}")
        print("\n判讀建議：")
        print("  - 成交量比值 ≈ 1000 → 一邊是「張」一邊是「股」，換算即可")
        print("  - 少量日期價差 → 通常是除權息當天的處理差異，可接受")
        print("  - 大量日期價差 → 其中一個來源的還原方式不同，**以 Fugle 為準**")
        print("  - 只有單邊有的日期 → 停牌或資料缺漏，檢查是否落在同一段期間")
    else:
        print("兩個來源高度一致，可以放心使用。")

    print("\n結論：日線以 Fugle 為主（官方券商資料），")
    print("      Yahoo 當交叉驗證與備援。兩者不一致時相信 Fugle。")


if __name__ == "__main__":
    main()
