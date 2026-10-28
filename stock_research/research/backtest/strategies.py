"""策略庫。

每個策略都是一個函式：(df, **params) -> 0/1 訊號序列。
訊號的語意是「**T 日收盤後決定，T+1 開盤執行**」，
所以策略內部絕對不能用到 T 日之後的資料。

新增策略只要寫一個函式 + 註冊到 STRATEGIES 就好。
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.core import indicators as ind


def _close(df: pd.DataFrame) -> pd.Series:
    """優先用還原價（含息），沒有就用原始收盤價。"""
    s = df["adj_close"] if "adj_close" in df.columns and df["adj_close"].notna().any() else df["close"]
    idx = df["date"] if "date" in df.columns else df.index
    return pd.Series(s.to_numpy(), index=pd.Index(idx))


# ============================================================ 趨勢 / 動能


def ma_trend(df: pd.DataFrame, window: int = 200, buffer: float = 0.03) -> pd.Series:
    """價格站上均線就持有，跌破就出場。

    buffer：出場後要站回均線上方 buffer 才重新進場，用來減少 whipsaw。
    這正是「跌多少才重新進場」那個問題的參數化。
    """
    px = _close(df)
    ma = px.rolling(window).mean()
    sig = np.zeros(len(px))
    holding = False
    for i in range(len(px)):
        if not np.isfinite(ma.iloc[i]):
            continue
        if holding and px.iloc[i] < ma.iloc[i]:
            holding = False
        elif not holding and px.iloc[i] > ma.iloc[i] * (1 + buffer):
            holding = True
        sig[i] = 1.0 if holding else 0.0
    return pd.Series(sig, index=px.index)


def ma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 60) -> pd.Series:
    """快線在慢線之上就持有。經典的雙均線。"""
    px = _close(df)
    f, s = px.rolling(fast).mean(), px.rolling(slow).mean()
    return (f > s).astype(float).where(s.notna(), 0.0)


def momentum(df: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.Series:
    """過去 lookback 日報酬 > 0 就持有，**跳過最近 skip 日**。

    跳過最近一個月是 Jegadeesh-Titman 的標準做法，
    因為短期是反轉不是動能，混進去會互相抵銷。
    """
    px = _close(df)
    mom = px.shift(skip) / px.shift(lookback) - 1
    return (mom > 0).astype(float).where(mom.notna(), 0.0)


def breakout(df: pd.DataFrame, window: int = 60, exit_window: int = 20) -> pd.Series:
    """創 N 日新高進場，跌破 M 日新低出場（海龜式）。"""
    px = _close(df)
    hi = px.rolling(window).max().shift(1)
    lo = px.rolling(exit_window).min().shift(1)
    sig = np.zeros(len(px))
    holding = False
    for i in range(len(px)):
        if not np.isfinite(hi.iloc[i]):
            continue
        if not holding and px.iloc[i] > hi.iloc[i]:
            holding = True
        elif holding and np.isfinite(lo.iloc[i]) and px.iloc[i] < lo.iloc[i]:
            holding = False
        sig[i] = 1.0 if holding else 0.0
    return pd.Series(sig, index=px.index)


def macd_trend(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD 柱狀圖翻正就持有。

    本質上是「指數加權的雙均線交叉」，與 ma_cross 高度相關（實測 0.93）。
    列進來是為了讓你親眼看到「換個名字不等於換個資訊」。
    """
    px = _close(df)
    macd = px.ewm(span=fast).mean() - px.ewm(span=slow).mean()
    sig = macd.ewm(span=signal).mean()
    return (macd > sig).astype(float).where(macd.notna(), 0.0)


def linreg_slope(df: pd.DataFrame, window: int = 120, min_r2: float = 0.0) -> pd.Series:
    """對過去 N 日價格做線性回歸，斜率為正就持有。

    與均線類的差別：**它衡量的是趨勢的「一致性」而不只是位置**。
    min_r2 > 0 時，還要求回歸的擬合度夠高 —— 也就是要求「漲得穩」，
    而不只是「漲得多」。這是均線做不到的事。
    """
    px = _close(df)
    x = np.arange(window)
    xc = x - x.mean()
    denom = (xc ** 2).sum()
    out = np.zeros(len(px))
    vals = px.to_numpy()
    for i in range(window, len(px)):
        y = vals[i - window : i]
        if not np.isfinite(y).all() or y.mean() == 0:
            continue
        beta = (xc * (y - y.mean())).sum() / denom
        if beta <= 0:
            continue
        if min_r2 > 0:
            pred = y.mean() + beta * xc
            ss_res = ((y - pred) ** 2).sum()
            ss_tot = ((y - y.mean()) ** 2).sum()
            if ss_tot == 0 or 1 - ss_res / ss_tot < min_r2:
                continue
        out[i] = 1.0
    return pd.Series(out, index=px.index)


def supertrend(df: pd.DataFrame, window: int = 10, mult: float = 3.0) -> pd.Series:
    """SuperTrend：以 ATR 為寬度的自適應軌道。

    與固定百分比的均線策略最大的差別：**軌道寬度會隨波動度伸縮**。
    高波動時容忍度自動放大，不會被雜訊掃出場；低波動時收緊，出場更快。
    """
    idx = df["date"] if "date" in df.columns else df.index
    high = pd.Series(df["high"].to_numpy(), index=pd.Index(idx))
    low = pd.Series(df["low"].to_numpy(), index=pd.Index(idx))
    close = _close(df)

    atr = ind.atr(high, low, close, window, normalize=False)
    mid = (high + low) / 2
    upper = (mid + mult * atr).to_numpy()
    lower = (mid - mult * atr).to_numpy()
    c = close.to_numpy()

    out = np.zeros(len(c))
    up, lo = upper.copy(), lower.copy()
    trend_up = True
    for i in range(1, len(c)):
        if not np.isfinite(up[i]) or not np.isfinite(lo[i]):
            continue
        up[i] = min(up[i], up[i - 1]) if c[i - 1] <= up[i - 1] else up[i]
        lo[i] = max(lo[i], lo[i - 1]) if c[i - 1] >= lo[i - 1] else lo[i]
        if trend_up and c[i] < lo[i]:
            trend_up = False
        elif not trend_up and c[i] > up[i]:
            trend_up = True
        out[i] = 1.0 if trend_up else 0.0
    return pd.Series(out, index=close.index)


def chandelier_exit(df: pd.DataFrame, entry_window: int = 60, atr_window: int = 22,
                    mult: float = 3.0) -> pd.Series:
    """吊燈出場：創 N 日新高進場，從**持有期最高點**回落 mult×ATR 才出場。

    這是**不對稱**策略的代表：進場看突破、出場看回落幅度。
    停損點只會往上移不會往下，所以獲利會被保護住。
    與 breakout（固定天數低點出場）的差別在於它會隨波動度調整。
    """
    idx = df["date"] if "date" in df.columns else df.index
    high = pd.Series(df["high"].to_numpy(), index=pd.Index(idx))
    low = pd.Series(df["low"].to_numpy(), index=pd.Index(idx))
    close = _close(df)

    atr = ind.atr(high, low, close, atr_window, normalize=False).to_numpy()
    hi_n = close.rolling(entry_window).max().shift(1).to_numpy()
    c = close.to_numpy()

    out = np.zeros(len(c))
    holding = False
    peak = 0.0
    for i in range(len(c)):
        if not np.isfinite(atr[i]):
            continue
        if not holding:
            if np.isfinite(hi_n[i]) and c[i] > hi_n[i]:
                holding, peak = True, c[i]
        else:
            peak = max(peak, c[i])
            if c[i] < peak - mult * atr[i]:
                holding = False
        out[i] = 1.0 if holding else 0.0
    return pd.Series(out, index=close.index)


def adx_filtered_trend(df: pd.DataFrame, ma_window: int = 100, adx_window: int = 14,
                       adx_min: float = 25.0) -> pd.Series:
    """趨勢跟隨 + ADX 濾網：只在「確實有趨勢」的時候才做。

    ADX 衡量的是趨勢**強度**（不分方向），與價格位置類指標相關性低，
    所以它提供的是真正的獨立資訊。盤整期會被濾掉，減少來回被巴。
    """
    idx = df["date"] if "date" in df.columns else df.index
    high = pd.Series(df["high"].to_numpy(), index=pd.Index(idx))
    low = pd.Series(df["low"].to_numpy(), index=pd.Index(idx))
    close = _close(df)
    trend = (close > close.rolling(ma_window).mean()).astype(float)
    strength = (ind.adx(high, low, close, adx_window) > adx_min).astype(float)
    return (trend * strength).fillna(0.0)


def dual_momentum(df: pd.DataFrame, lookback: int = 252, skip: int = 21,
                  ma_window: int = 200) -> pd.Series:
    """雙重確認：動能為正 **且** 站上長期均線，兩個條件都要成立。

    這是「同向確認」而非「新增資訊」—— 兩個條件高度相關，
    效果通常是降低交易次數與回撤，而不是提高報酬。
    """
    return momentum(df, lookback, skip) * ma_trend(df, ma_window, 0.0)


# ============================================================ 均值回歸


def rsi_reversal(df: pd.DataFrame, window: int = 14, entry: float = 30,
                 exit: float = 55) -> pd.Series:
    """RSI 跌破 entry 進場，回升到 exit 出場。"""
    px = _close(df)
    r = ind.rsi(px, window)
    sig = np.zeros(len(px))
    holding = False
    for i in range(len(px)):
        if not np.isfinite(r.iloc[i]):
            continue
        if not holding and r.iloc[i] < entry:
            holding = True
        elif holding and r.iloc[i] > exit:
            holding = False
        sig[i] = 1.0 if holding else 0.0
    return pd.Series(sig, index=px.index)


def short_reversal(df: pd.DataFrame, lookback: int = 5, hold: int = 20,
                   threshold: float = -0.08) -> pd.Series:
    """過去 N 日跌超過門檻就進場，固定持有 hold 日。"""
    px = _close(df)
    past = px / px.shift(lookback) - 1
    sig = np.zeros(len(px))
    remain = 0
    for i in range(len(px)):
        if remain > 0:
            sig[i] = 1.0
            remain -= 1
        elif np.isfinite(past.iloc[i]) and past.iloc[i] <= threshold:
            sig[i] = 1.0
            remain = hold - 1
    return pd.Series(sig, index=px.index)


# ============================================================ 風險控制


def vol_target(df: pd.DataFrame, window: int = 60, target: float = 0.20,
               max_vol: float = 0.60) -> pd.Series:
    """波動度目標。波動高於 max_vol 就空手，否則持有。

    這是唯一不預測方向的策略 —— 波動度的可預測性是報酬的 40 倍。
    """
    px = _close(df)
    vol = ind.realized_vol(px, window)
    return (vol < max_vol).astype(float).where(vol.notna(), 0.0)


def trend_with_vol_filter(df: pd.DataFrame, window: int = 200, buffer: float = 0.03,
                          vol_window: int = 60, max_vol: float = 0.60) -> pd.Series:
    """趨勢跟隨 + 波動度過濾。兩個條件都成立才持有。"""
    return ma_trend(df, window, buffer) * vol_target(df, vol_window, max_vol=max_vol)


# ============================================================ 註冊表


@dataclass(frozen=True)
class StrategySpec:
    fn: object
    label: str
    description: str
    grid: dict            # 參數掃描用的候選值


STRATEGIES: dict[str, StrategySpec] = {
    "ma_trend": StrategySpec(
        ma_trend, "均線趨勢",
        "站上均線持有、跌破出場，站回 +buffer 才重新進場",
        {"window": [60, 100, 150, 200, 250], "buffer": [0.0, 0.03, 0.05]},
    ),
    "ma_cross": StrategySpec(
        ma_cross, "雙均線交叉", "快線在慢線之上就持有",
        {"fast": [5, 10, 20, 40], "slow": [20, 60, 120, 200]},
    ),
    "momentum": StrategySpec(
        momentum, "動能（跳過近月）", "過去 N 日報酬為正就持有，跳過最近一個月",
        {"lookback": [63, 126, 252], "skip": [0, 21]},
    ),
    "breakout": StrategySpec(
        breakout, "區間突破", "創 N 日新高進場，跌破 M 日新低出場",
        {"window": [20, 60, 120, 250], "exit_window": [10, 20, 60]},
    ),
    "macd": StrategySpec(
        macd_trend, "MACD", "MACD 柱狀圖翻正就持有（本質是指數加權雙均線）",
        {"fast": [8, 12, 16], "slow": [21, 26, 34]},
    ),
    "linreg": StrategySpec(
        linreg_slope, "回歸斜率", "線性回歸斜率為正才持有，可要求擬合度（漲得穩）",
        {"window": [60, 120, 250], "min_r2": [0.0, 0.3, 0.5]},
    ),
    "supertrend": StrategySpec(
        supertrend, "SuperTrend", "ATR 自適應軌道，波動大時容忍度自動放大",
        {"window": [7, 10, 14, 20], "mult": [2.0, 3.0, 4.0]},
    ),
    "chandelier": StrategySpec(
        chandelier_exit, "吊燈出場", "突破進場，從持有期高點回落 N×ATR 才出場（不對稱）",
        {"entry_window": [20, 60, 120], "mult": [2.0, 3.0, 4.0]},
    ),
    "adx_trend": StrategySpec(
        adx_filtered_trend, "ADX 濾網趨勢", "只在 ADX 顯示有明確趨勢時才做趨勢",
        {"ma_window": [60, 100, 200], "adx_min": [20, 25, 30]},
    ),
    "dual_momentum": StrategySpec(
        dual_momentum, "雙重動能", "動能為正且站上長期均線，兩條件都要",
        {"lookback": [126, 252], "ma_window": [100, 200]},
    ),
    "rsi_reversal": StrategySpec(
        rsi_reversal, "RSI 反轉", "RSI 超賣進場、回升出場",
        {"window": [9, 14, 21], "entry": [20, 25, 30, 35]},
    ),
    "short_reversal": StrategySpec(
        short_reversal, "短期反轉", "短期跌深進場，固定持有 N 日",
        {"lookback": [3, 5, 10], "threshold": [-0.05, -0.08, -0.12], "hold": [10, 20]},
    ),
    "vol_target": StrategySpec(
        vol_target, "波動度過濾", "波動度低於門檻才持有，不預測方向",
        {"window": [20, 60, 120], "max_vol": [0.35, 0.45, 0.60, 0.80]},
    ),
    "trend_vol": StrategySpec(
        trend_with_vol_filter, "趨勢+波動過濾", "均線趨勢與波動度條件都成立才持有",
        {"window": [100, 200], "max_vol": [0.45, 0.60, 0.80]},
    ),
}
