"""回補台股日線。

預設抓 8 個主題共 22 檔 + 0050（benchmark）。
同時抓 **還原價** 與 **原始價** 兩份：

  還原價（adjusted=true） → 技術指標與回測用（連續、無除權息跳空）
  原始價（adjusted=false）→ 對帳用，而且兩者相除可以反推出除權息事件
                            （股務事件端點要付費方案才有，這是免費的替代辦法）

用法：
    python scripts/backfill_daily.py                    # 主題 22 檔 + 0050
    python scripts/backfill_daily.py --all              # 你交易過的全部 39 檔
    python scripts/backfill_daily.py --themes 記憶體 ABF載板
    python scripts/backfill_daily.py --start 2015-01-01
    python scripts/backfill_daily.py --resume           # 只補缺的部分
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from dotenv import load_dotenv  # noqa: E402

from research.core.universe import NAMES, THEMES, diagnose  # noqa: E402
from research.ingest.fugle import FugleClient, FugleError  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DAILY_PARQUET = DATA_DIR / "price_history.parquet"
BENCHMARK = "0050"
DEFAULT_START = "2010-01-01"
CHUNK_YEARS = 1          # 保守起見分年抓；probe 確認可以更大再調


def chunk_ranges(start: str, end: str, years: int = CHUNK_YEARS) -> list[tuple[str, str]]:
    out, cur = [], pd.Timestamp(start)
    last = pd.Timestamp(end)
    while cur <= last:
        stop = min(cur + pd.DateOffset(years=years) - pd.Timedelta(days=1), last)
        out.append((cur.strftime("%Y-%m-%d"), stop.strftime("%Y-%m-%d")))
        cur = stop + pd.Timedelta(days=1)
    return out


def fetch_one(client: FugleClient, ticker: str, start: str, end: str) -> pd.DataFrame:
    frames = []
    for adjusted in (True, False):
        rows = []
        for a, b in chunk_ranges(start, end):
            try:
                rows.extend(client.daily_candles(ticker, a, b, adjusted=adjusted))
            except FugleError as exc:
                print(f"      ! {ticker} {a}~{b} adjusted={adjusted}: {exc}")
        if not rows:
            continue
        df = pd.DataFrame(rows).drop_duplicates(subset=["date"])
        df = df.rename(columns={"close": "adj_close" if adjusted else "close"})
        keep = ["date", "adj_close"] if adjusted else ["date", "open", "high", "low", "close", "volume", "turnover"]
        frames.append(df[[c for c in keep if c in df.columns]])

    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")
    out["symbol"] = f"TW:{ticker}"
    out["ticker"] = ticker
    out["name"] = NAMES.get(ticker, "")
    out["source"] = "fugle"
    return out.sort_values("date").reset_index(drop=True)


def select_tickers(args) -> list[str]:
    if args.all:
        codes = list(NAMES)
    elif args.themes:
        codes = []
        for t in args.themes:
            if t not in THEMES:
                raise SystemExit(f"未知主題 {t}。可選：{list(THEMES)}")
            codes += THEMES[t]
    else:
        codes = [c for members in THEMES.values() for c in members]
    codes = sorted(set(codes) | {BENCHMARK})
    return [c for c in codes if c != "00981A" or args.all]   # 主動 ETF 歷史太短，預設略過


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true", help="抓你交易過的全部 39 檔")
    p.add_argument("--themes", nargs="*", help="只抓指定主題")
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--resume", action="store_true", help="已抓過的標的跳過")
    args = p.parse_args()

    tickers = select_tickers(args)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing = pd.DataFrame()
    if DAILY_PARQUET.exists():
        existing = pd.read_parquet(DAILY_PARQUET)
        if args.resume:
            done = set(existing["ticker"].unique())
            skipped = [t for t in tickers if t in done]
            tickers = [t for t in tickers if t not in done]
            if skipped:
                print(f"已存在，跳過 {len(skipped)} 檔：{', '.join(skipped)}")

    if not tickers:
        print("沒有需要抓的標的。")
        return

    n_chunks = len(chunk_ranges(args.start, args.end))
    print(f"標的 {len(tickers)} 檔｜期間 {args.start} ~ {args.end}")
    print(f"每檔 {n_chunks} 段 × 2（還原/原始）= 每檔 {n_chunks*2} 次請求")
    print(f"預估總請求 {len(tickers)*n_chunks*2} 次，以 58 次/分計算約 "
          f"{len(tickers)*n_chunks*2/58:.1f} 分鐘\n")

    try:
        client = FugleClient()
    except FugleError as exc:
        raise SystemExit(f"✗ {exc}")

    frames = [existing] if len(existing) else []
    for i, ticker in enumerate(tickers, 1):
        name = NAMES.get(ticker, "")
        print(f"[{i:>2}/{len(tickers)}] {ticker} {name}", flush=True)
        df = fetch_one(client, ticker, args.start, args.end)
        if df.empty:
            print("      → 無資料")
            continue
        print(f"      → {len(df):>5} 筆  {df['date'].min()} ~ {df['date'].max()}")
        frames.append(df)

    if not frames:
        print("沒有抓到任何資料。")
        return

    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["symbol", "date"], keep="last")
    all_df["date"] = pd.to_datetime(all_df["date"])
    all_df = all_df.sort_values(["symbol", "date"]).reset_index(drop=True)
    all_df.to_parquet(DAILY_PARQUET, index=False)

    print(f"\n已寫入 {DAILY_PARQUET}")
    print(f"共 {len(all_df):,} 筆、{all_df['symbol'].nunique()} 檔\n")

    print("=" * 62)
    print("各標的資料涵蓋範圍")
    print("=" * 62)
    summary = all_df.groupby(["ticker", "name"]).agg(
        筆數=("date", "size"), 最早=("date", "min"), 最晚=("date", "max")
    ).reset_index()
    summary["年數"] = ((summary["最晚"] - summary["最早"]).dt.days / 365.25).round(1)
    for _, r in summary.sort_values("年數").iterrows():
        flag = "  ⚠ 歷史偏短" if r["年數"] < 10 else ""
        print(f"  {r['ticker']:<7}{r['name']:<14}{r['筆數']:>6} 筆  "
              f"{r['最早']:%Y-%m-%d} ~ {r['最晚']:%Y-%m-%d}  {r['年數']:>5.1f} 年{flag}")

    print("\n" + "=" * 62)
    print("股票池診斷")
    print("=" * 62)
    print(diagnose(all_df).report())


if __name__ == "__main__":
    main()
