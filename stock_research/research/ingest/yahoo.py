"""Yahoo Finance（yfinance）台股抓取。

**這是非官方來源**，Yahoo 隨時可能改介面或擋流量，yfinance 歷史上壞過很多次。
但它有兩個 Fugle 沒有的優點：

  1. 不需要 API key
  2. 一次可以抓完整歷史，不用分段，也沒有 60 次/分的限制

建議用法：**當作 Fugle 的交叉驗證來源**，而不是唯一來源。
兩個獨立來源對不起來的地方，就是資料品質問題的線索
（見 scripts/compare_sources.py）。

台股代號規則：
  上市（TWSE） → 2330.TW
  上櫃（TPEx） → 3081.TWO
本模組會自動兩個都試，用有資料的那個。
"""

from dataclasses import dataclass

import pandas as pd

SUFFIXES = (".TW", ".TWO")


@dataclass
class FetchResult:
    ticker: str
    yahoo_symbol: str | None
    data: pd.DataFrame
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.data.empty


def _normalize(df: pd.DataFrame, ticker: str, yahoo_symbol: str) -> pd.DataFrame:
    """轉成與 Fugle 回補一致的欄位名稱。"""
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col]).dt.tz_localize(None).dt.normalize(),
        "open": df["Open"],
        "high": df["High"],
        "low": df["Low"],
        "close": df["Close"],
        "volume": df["Volume"],
    })
    # yfinance 的 auto_adjust=True 會把 Close 直接換成還原價；
    # 這裡兩份分開抓，由呼叫端決定放進 close 還是 adj_close
    out["symbol"] = f"TW:{ticker}"
    out["ticker"] = ticker
    out["yahoo_symbol"] = yahoo_symbol
    out["source"] = "yahoo"
    return out.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def fetch_one(ticker: str, start: str = "2010-01-01", end: str | None = None) -> FetchResult:
    """抓單一標的。自動判斷 .TW / .TWO，同時取得原始價與還原價。"""
    try:
        import yfinance as yf
    except ImportError:
        return FetchResult(ticker, None, pd.DataFrame(), "未安裝 yfinance：pip install yfinance")

    last_error = None
    for suffix in SUFFIXES:
        symbol = f"{ticker}{suffix}"
        try:
            t = yf.Ticker(symbol)
            raw = t.history(start=start, end=end, auto_adjust=False, actions=False)
            if raw is None or raw.empty:
                continue
            adj = t.history(start=start, end=end, auto_adjust=True, actions=False)
        except Exception as exc:                      # 網路 / API 變動
            last_error = f"{type(exc).__name__}: {exc}"
            continue

        df = _normalize(raw, ticker, symbol)
        if adj is not None and not adj.empty:
            a = _normalize(adj, ticker, symbol)[["date", "close"]]
            a = a.rename(columns={"close": "adj_close"})
            df = df.merge(a, on="date", how="left")
        else:
            df["adj_close"] = df["close"]
        return FetchResult(ticker, symbol, df)

    return FetchResult(ticker, None, pd.DataFrame(),
                       last_error or "在 .TW 與 .TWO 都找不到資料")


def fetch_many(tickers: list[str], start: str = "2010-01-01",
               end: str | None = None, verbose: bool = True) -> tuple[pd.DataFrame, list[FetchResult]]:
    frames, results = [], []
    for i, ticker in enumerate(tickers, 1):
        res = fetch_one(ticker, start, end)
        results.append(res)
        if verbose:
            if res.ok:
                d = res.data
                print(f"[{i:>2}/{len(tickers)}] {ticker:<7} {res.yahoo_symbol:<10} "
                      f"{len(d):>5} 筆  {d['date'].min():%Y-%m-%d} ~ {d['date'].max():%Y-%m-%d}")
            else:
                print(f"[{i:>2}/{len(tickers)}] {ticker:<7} ✗ {res.error}")
        if res.ok:
            frames.append(res.data)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, results
