"""標籤設計。

天真的「未來 N 日報酬」忽略路徑：中間跌 30% 但第 N 天剛好回來，
會被標成「賺」，但實際上你早就被停損出場了。

Triple-barrier 用停利／停損／時間三道界線，哪道先碰到就是哪個標籤，
這才符合你實際會怎麼交易。
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


def forward_return(close: pd.Series, horizon: int) -> pd.Series:
    """固定期間報酬。簡單，但忽略路徑，只適合做初步探索。"""
    return close.shift(-horizon) / close - 1.0


def realized_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """日報酬的滾動標準差，用來動態調整障礙寬度。

    高波動時期的 5% 跟低波動時期的 5% 意義完全不同，
    所以障礙寬度要用波動度縮放，不要用固定百分比。
    """
    return close.pct_change().rolling(window).std()


@dataclass(frozen=True)
class TripleBarrierResult:
    label: pd.Series        # +1 觸及停利 / -1 觸及停損 / 0 時間到期
    ret: pd.Series          # 出場時的實際毛報酬
    holding_days: pd.Series  # 實際持有天數（可能短於 horizon）
    exit_reason: pd.Series   # 'take_profit' | 'stop_loss' | 'timeout'


def triple_barrier(
    close: pd.Series,
    horizon: int = 20,
    upper_mult: float = 2.0,
    lower_mult: float = 2.0,
    vol_window: int = 20,
    vol: pd.Series | None = None,
) -> TripleBarrierResult:
    """三重障礙標籤。

    參數
    ----
    horizon      : 時間障礙（交易日）
    upper_mult   : 停利距離 = upper_mult × 日波動度 × sqrt(horizon)
    lower_mult   : 停損距離 = lower_mult × 日波動度 × sqrt(horizon)
    vol          : 自行提供的波動度序列；不給則用 realized_volatility 計算

    回傳的 ret 是**毛報酬**，成本要另外扣（見 core.costs）。
    """
    close = close.astype(float)
    if vol is None:
        vol = realized_volatility(close, vol_window)

    scale = vol * np.sqrt(horizon)
    upper = upper_mult * scale
    lower = lower_mult * scale

    values = close.to_numpy()
    up = upper.to_numpy()
    lo = lower.to_numpy()
    n = len(values)

    label = np.full(n, np.nan)
    ret = np.full(n, np.nan)
    held = np.full(n, np.nan)
    reason = np.array([None] * n, dtype=object)

    for i in range(n):
        if i + 1 >= n or not np.isfinite(up[i]) or not np.isfinite(lo[i]):
            continue
        entry = values[i]
        if entry <= 0:
            continue

        end = min(i + horizon, n - 1)
        path = values[i + 1 : end + 1]
        if len(path) == 0:
            continue

        rel = path / entry - 1.0
        hit_up = np.argmax(rel >= up[i]) if (rel >= up[i]).any() else None
        hit_lo = np.argmax(rel <= -lo[i]) if (rel <= -lo[i]).any() else None

        if hit_up is not None and (hit_lo is None or hit_up <= hit_lo):
            k = hit_up
            label[i], reason[i] = 1.0, "take_profit"
        elif hit_lo is not None:
            k = hit_lo
            label[i], reason[i] = -1.0, "stop_loss"
        else:
            k = len(path) - 1
            label[i], reason[i] = 0.0, "timeout"

        ret[i] = rel[k]
        held[i] = k + 1

    index = close.index
    return TripleBarrierResult(
        label=pd.Series(label, index=index, name="label"),
        ret=pd.Series(ret, index=index, name="ret"),
        holding_days=pd.Series(held, index=index, name="holding_days"),
        exit_reason=pd.Series(reason, index=index, name="exit_reason"),
    )
