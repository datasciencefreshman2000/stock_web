"""技術指標。

**刻意依「量測什麼」分類，而不是依名字分類。**

實測（見 docs/technical_indicators_guide.md）：
13 個常見指標之間，相關係數超過 0.7 的配對有 27 組，
PCA 顯示 5 個主成分就解釋 90% 變異。

也就是說「我用了 13 個指標所以很穩健」是錯覺——
它們全都是同一條價格序列的不同變換，你只有約 5 份獨立資訊。

所以：**每個維度挑一個就好。**
"""

import numpy as np
import pandas as pd

# ============================================================ 維度一：趨勢方向
# 問題：價格在往上還是往下？


def price_vs_ma(close: pd.Series, window: int = 60) -> pd.Series:
    """價格相對均線的位置。最直接的趨勢量測，優先用這個。"""
    return close / close.rolling(window).mean() - 1.0


def ma_slope(close: pd.Series, window: int = 20, lookback: int = 5) -> pd.Series:
    """均線本身的斜率。比 price_vs_ma 平滑，但反應慢。"""
    ma = close.rolling(window).mean()
    return ma / ma.shift(lookback) - 1.0


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """趨勢強度（不分方向）。ADX 高 = 有明確趨勢，低 = 盤整。

    這是少數不與 price_vs_ma 高度相關的趨勢類指標，因為它measure的是
    「有沒有趨勢」而不是「趨勢往哪」。
    """
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(high, low, close)
    atr_ = tr.ewm(alpha=1 / window, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(alpha=1/window, adjust=False).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(alpha=1/window, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / window, adjust=False).mean()


# ============================================================ 維度二：動能速度
# 問題：漲得多快？這是「趨勢」與「動能」的差別——方向 vs 速度。


def roc(close: pd.Series, window: int = 20) -> pd.Series:
    """N 日報酬率。最單純的動能量測，也最不容易過擬合。

    學術上的動能通常用 3–12 個月（60–250 日），不是幾天。
    """
    return close.pct_change(window)


def momentum_12_1(close: pd.Series) -> pd.Series:
    """Jegadeesh-Titman 經典動能：過去 12 個月報酬，**跳過最近 1 個月**。

    跳過最近一個月是關鍵，不能省。
    因為短期（1 個月內）是反轉不是動能，混進去會互相抵銷。
    """
    return close.shift(21) / close.shift(252) - 1.0


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """相對強弱指標。本質上是「上漲動能佔總動能的比例」。

    注意：與 price_vs_ma(20) 的相關係數約 0.9，兩者擇一即可。
    """
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()

    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    # 邊界情況：完全沒有下跌 → RSI = 100；完全沒有上漲 → RSI = 0
    out = out.mask((loss == 0) & (gain > 0), 100.0)
    out = out.mask((gain == 0) & (loss > 0), 0.0)
    out = out.mask((gain == 0) & (loss == 0), 50.0)
    out.iloc[0] = np.nan          # 第一筆沒有前值可比
    return out


# ============================================================ 維度三：波動度
# 問題：風險有多高？這是唯一真正可預測的維度（R² 約 0.08，是報酬的 40 倍）。


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev = close.shift()
    return pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14,
        normalize: bool = True) -> pd.Series:
    """平均真實區間。normalize=True 時除以價格，變成可跨股票比較的比例。"""
    a = true_range(high, low, close).ewm(alpha=1 / window, adjust=False).mean()
    return a / close if normalize else a


def realized_vol(close: pd.Series, window: int = 20, annualize: bool = True) -> pd.Series:
    """已實現波動度。波動度目標化的核心輸入。"""
    v = close.pct_change().rolling(window).std()
    return v * np.sqrt(250) if annualize else v


def vol_percentile(close: pd.Series, window: int = 20, lookback: int = 750) -> pd.Series:
    """目前波動度在過去 N 日中的百分位。

    **這是「可即時觀測的格局」的正確做法**——
    不像「升息循環」要等結束才知道，這個今天收盤就算得出來。
    """
    v = realized_vol(close, window)
    return v.rolling(lookback).rank(pct=True)


# ============================================================ 維度四：相對強度
# 問題：這檔比大盤強還是弱？橫斷面動能的核心，多數人忽略。


def relative_strength(close: pd.Series, benchmark: pd.Series, window: int = 60) -> pd.Series:
    """個股相對大盤的超額報酬。

    做選股時這比絕對報酬有用得多——
    大盤漲 20% 時個股漲 10%，絕對報酬是正的，但它其實是弱勢股。
    """
    return close.pct_change(window) - benchmark.pct_change(window)


# ============================================================ 維度五：量能
# 問題：這個價格變動有沒有成交量支撐？


def volume_ratio(volume: pd.Series, window: int = 20) -> pd.Series:
    """目前量能相對近期均量。> 2 通常視為爆量。"""
    return volume / volume.rolling(window).mean()


def turnover(volume: pd.Series, shares_outstanding: float) -> pd.Series:
    """週轉率。台股散戶比重高，週轉率是有意義的市場結構變數。"""
    return volume / shares_outstanding


# ============================================================ 台股特有


LIMIT_UP_THRESHOLD = 0.095      # 台股漲跌幅 10%，留一點誤差空間
LIMIT_DOWN_THRESHOLD = -0.095


def is_limit_up(close: pd.Series) -> pd.Series:
    """是否漲停。台股特有的微結構訊號——代表需求在該價位無法被滿足。"""
    return close.pct_change() >= LIMIT_UP_THRESHOLD


def is_limit_down(close: pd.Series) -> pd.Series:
    return close.pct_change() <= LIMIT_DOWN_THRESHOLD


def consecutive_limit_up(close: pd.Series) -> pd.Series:
    """連續漲停天數。

    「連續兩天漲停」在技術面上意味著：
      1. 買方需求強到連續兩天無法在漲停價以下被滿足
      2. 但也代表你**買不到**——漲停時掛單成交機率極低
    第 2 點是回測時最容易忽略的，會讓結果嚴重高估。
    """
    lu = is_limit_up(close)
    groups = (~lu).cumsum()
    return lu.groupby(groups).cumsum()


# ============================================================ 建議組合


def core_feature_set(high: pd.Series, low: pd.Series, close: pd.Series,
                     volume: pd.Series, benchmark: pd.Series | None = None) -> pd.DataFrame:
    """五個維度各挑一個，避免共線性。

    刻意只有 5–6 個特徵。實驗五顯示 13 個指標只有約 5 份獨立資訊，
    多加的只會增加過擬合空間，不會增加資訊。
    """
    feats = {
        "trend": price_vs_ma(close, 60),          # 維度一：方向
        "trend_strength": adx(high, low, close),   # 維度一：強度（獨立資訊）
        "momentum": momentum_12_1(close),          # 維度二：速度
        "volatility": realized_vol(close, 20),     # 維度三：風險
        "vol_regime": vol_percentile(close),       # 維度三：風險的相對位置
        "volume": volume_ratio(volume, 20),        # 維度五：量能
    }
    if benchmark is not None:
        feats["rel_strength"] = relative_strength(close, benchmark, 60)  # 維度四
    return pd.DataFrame(feats)
