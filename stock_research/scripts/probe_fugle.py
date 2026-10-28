"""先跑這支：確認 Fugle 的三個未知數，再決定回補程式怎麼寫。

要確認的：
1. 單次查詢的區間上限是多少？（文件標題寫「1 年內」但說明寫可回溯 2010）
2. 實際能回溯到哪一年？
3. adjusted=true 的還原基準日是哪天？
   → 若是「以最新價往回還原」，每次除權息後整段歷史都會變，
     更新策略就必須是「定期整檔重抓」而不是「只補最新一天」。

用法：
    python scripts/probe_fugle.py
    python scripts/probe_fugle.py --ticker 2408
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from dotenv import load_dotenv  # noqa: E402

from research.ingest.fugle import FugleClient, FugleError  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")   # 也讀 stock_site/.env


def probe_range_limit(client: FugleClient, ticker: str) -> None:
    print("\n【問題 1】單次查詢的區間上限")
    print("-" * 62)
    for label, start, end in [
        ("6 個月", "2024-01-01", "2024-06-30"),
        ("1 年",   "2023-01-01", "2023-12-31"),
        ("2 年",   "2022-01-01", "2023-12-31"),
        ("5 年",   "2019-01-01", "2023-12-31"),
        ("15 年",  "2010-01-01", "2024-12-31"),
    ]:
        try:
            rows = client.daily_candles(ticker, start, end)
            if rows:
                print(f"  {label:<7} {start} ~ {end}  →  {len(rows):>5} 筆"
                      f"  實得 {rows[0]['date']} ~ {rows[-1]['date']}")
            else:
                print(f"  {label:<7} {start} ~ {end}  →  無資料")
        except FugleError as exc:
            print(f"  {label:<7} {start} ~ {end}  →  ✗ {exc}")


def probe_earliest(client: FugleClient, ticker: str) -> None:
    print("\n【問題 2】實際能回溯到哪一年")
    print("-" * 62)
    for year in [2008, 2010, 2012, 2015, 2018, 2020]:
        try:
            rows = client.daily_candles(ticker, f"{year}-01-01", f"{year}-03-31")
            mark = f"{len(rows):>4} 筆，最早 {rows[0]['date']}" if rows else "無資料"
            print(f"  {year} Q1  →  {mark}")
        except FugleError as exc:
            print(f"  {year} Q1  →  ✗ {exc}")


def probe_adjustment(client: FugleClient, ticker: str) -> None:
    print("\n【問題 3】adjusted=true 的還原基準")
    print("-" * 62)
    start, end = "2024-01-02", "2024-01-31"
    try:
        adj = client.daily_candles(ticker, start, end, adjusted=True)
        raw = client.daily_candles(ticker, start, end, adjusted=False)
    except FugleError as exc:
        print(f"  ✗ {exc}")
        return
    if not adj or not raw:
        print("  無資料，換一檔試試")
        return

    print(f"  {'日期':<12}{'還原價':>10}{'原始價':>10}{'比值':>9}")
    by_date = {r["date"]: r for r in raw}
    ratios = []
    for row in adj[:6]:
        r = by_date.get(row["date"])
        if not r:
            continue
        ratio = row["close"] / r["close"]
        ratios.append(ratio)
        print(f"  {row['date']:<12}{row['close']:>10.2f}{r['close']:>10.2f}{ratio:>9.4f}")

    if ratios:
        spread = max(ratios) - min(ratios)
        print()
        if all(abs(x - 1) < 1e-6 for x in ratios):
            print("  → 這段期間還原價 = 原始價（期間內沒有除權息）")
            print("    請換一檔有配息的標的再測一次")
        elif spread < 1e-6:
            print(f"  → 比值固定為 {ratios[0]:.4f}")
            print("    ⚠ 代表是『以最新價為基準往回還原』")
            print("    → 每次新的除權息發生後，整段歷史都會變動")
            print("    → 更新策略必須是『定期整檔重抓』，不能只補最新一天")
        else:
            print("  → 比值會變動，代表是逐次事件還原（基準日固定在過去）")
            print("    → 可以安全地做增量更新")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="2330", help="拿來測試的股票代號")
    args = parser.parse_args()

    print("=" * 62)
    print(f"Fugle 歷史行情探測 —— 測試標的 {args.ticker}")
    print("=" * 62)

    try:
        client = FugleClient()
    except FugleError as exc:
        print(f"\n✗ {exc}")
        raise SystemExit(1)

    info = client.stats(args.ticker)
    if info:
        print(f"標的：{info.get('name', '?')}｜市場 {info.get('market', '?')}"
              f"｜最後交易日 {info.get('date', '?')}")

    probe_range_limit(client, args.ticker)
    probe_earliest(client, args.ticker)
    probe_adjustment(client, args.ticker)

    print("\n" + "=" * 62)
    print("把上面三個答案告訴我，我再依實際行為調整回補程式。")


if __name__ == "__main__":
    main()
