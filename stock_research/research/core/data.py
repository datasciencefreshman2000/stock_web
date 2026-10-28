"""資料載入。

三個來源，依序嘗試：
1. 本地 parquet 快取（研究時反覆讀取，不要每次都打 DB）
2. Supabase 的 price_history 表
3. 合成資料（資料還沒回補時，先讓整條管線跑得起來）

第 3 點很重要：你可以在還沒有任何真實資料的今天，
就把研究流程完整跑一遍，確認管線沒問題。
"""

from pathlib import Path
import json
import time

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE = DATA_DIR / "price_history.parquet"
CACHE_META = DATA_DIR / "price_history.meta.json"

REQUIRED_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_from_cache(symbols: list[str] | None = None, max_age_hours=24) -> pd.DataFrame | None:
    if not CACHE.exists() or not CACHE_META.exists():
        return None  # Legacy cache has no provenance or coverage guarantee.
    try:
        meta = json.loads(CACHE_META.read_text(encoding="utf-8"))
        if time.time() - meta["saved_at"] > max_age_hours * 3600:
            return None
        if meta.get("price_basis") != "adjusted_ohlc_v1":
            return None
        if symbols is None and meta.get("scope") != "all":
            return None
        if symbols and not set(symbols).issubset(meta.get("symbols", [])):
            return None
        df = _normalize(pd.read_parquet(CACHE))
        if symbols:
            df = df[df["symbol"].isin(symbols)]
        return df
    except (OSError, ValueError, KeyError):
        return None
    return None


def adjust_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Use the same adjustment factor for execution prices and valuation prices."""
    if "adj_close" not in df:
        return df
    df = df.copy()
    factor = pd.to_numeric(df["adj_close"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce").replace(0, np.nan)
    if factor.isna().any() or (factor <= 0).any():
        raise ValueError("還原價格缺漏或無效，不能產生一致的 OHLC")
    for column in ("open", "high", "low", "close"):
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce") * factor
    return df


def load_from_supabase(symbols: list[str] | None = None) -> pd.DataFrame | None:
    """從 Supabase 讀 price_history。需要 .env 裡有 SUPABASE_* 設定。"""
    try:
        import os

        from dotenv import load_dotenv
        from supabase import create_client
    except ImportError:
        return None

    load_dotenv()
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None

    try:
        client = create_client(url, key)
        rows: list[dict] = []
        page, size = 0, 1000
        while True:
            q = client.table("price_history").select("*").order("symbol").order("date").range(page * size, (page + 1) * size - 1)
            if symbols:
                q = q.in_("symbol", symbols)
            chunk = q.execute().data or []
            rows.extend(chunk)
            if len(chunk) < size:
                break
            page += 1
    except Exception as exc:  # 連不上就往下退到合成資料，不要讓研究流程整個掛掉
        print(f"[data] Supabase 讀取失敗，改用其他來源：{type(exc).__name__}: {exc}")
        return None

    if not rows:
        return None
    df = pd.DataFrame(rows)
    return _normalize(adjust_ohlc(df))


def make_synthetic(
    n_symbols: int = 40,
    start: str = "2010-01-01",
    days: int = 4000,
    seed: int = 7,
    reversal_edge: float = 0.0,
) -> pd.DataFrame:
    """合成台股日線，用來驗證研究管線。

    reversal_edge > 0 時會刻意植入短期反轉效應，
    可以用來確認你的研究程式「找得到真的存在的訊號」——
    這是很重要的健全性檢查（sanity check）。
    如果連植入的訊號都找不到，那你在真實資料上找到的更不可信。
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=days)
    frames = []

    for i in range(n_symbols):
        vol = rng.uniform(0.012, 0.030)
        rets = rng.normal(0.0002, vol, days)

        if reversal_edge > 0:
            # 前 5 日跌越多，隔日期望報酬越高
            for t in range(5, days):
                past5 = rets[t - 5 : t].sum()
                rets[t] += -reversal_edge * past5

        close = 50 * np.exp(np.cumsum(rets))
        noise = rng.normal(0, 0.004, days)
        frames.append(pd.DataFrame({
            "symbol": f"TW:{1000 + i * 7}",
            "date": dates,
            "open": close * (1 + noise),
            "high": close * (1 + np.abs(noise) + 0.002),
            "low": close * (1 - np.abs(noise) - 0.002),
            "close": close,
            "volume": rng.integers(500_000, 20_000_000, days),
        }))

    return _normalize(pd.concat(frames, ignore_index=True))


def load_prices(symbols: list[str] | None = None,
                allow_synthetic: bool = True,
                **synthetic_kwargs) -> tuple[pd.DataFrame, str]:
    """回傳 (資料, 來源說明)。來源會被印出來，避免你不小心拿合成資料當真的分析。"""
    df = load_from_cache(symbols)
    if df is not None:
        if symbols:
            df = df[df["symbol"].isin(symbols)]
        return df, "本地快取 (data/price_history.parquet)"

    df = load_from_supabase(symbols)
    if df is not None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE, index=False)
        CACHE_META.write_text(json.dumps({"saved_at": time.time(), "scope": "all" if symbols is None else "subset",
            "symbols": sorted(df["symbol"].unique().tolist()), "source": "supabase", "price_basis": "adjusted_ohlc_v1"}), encoding="utf-8")
        return df, "Supabase price_history（已寫入本地快取）"

    if not allow_synthetic:
        raise RuntimeError("找不到真實資料，且 allow_synthetic=False")

    return make_synthetic(**synthetic_kwargs), "★ 合成資料（不是真實市場！僅供驗證管線）"
