"""事件驅動回測引擎。

三個正確性要求，缺一結果就不能信：

1. **T 日訊號 → T+1 開盤成交**。用當日收盤價下單是最常見的前視偏誤。
2. **漲跌停買不到**。訊號要買但隔日開盤就漲停時，實際成交不了。
3. **成本在換倉當下扣**。不是最後統一扣。
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

LIMIT = 0.095          # 台股漲跌幅 10%，留一點誤差空間
TRADING_DAYS = 250


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp | None
    entry_price: float
    exit_price: float | None
    holding_days: int
    gross_return: float
    net_return: float


@dataclass
class BacktestResult:
    equity: pd.Series
    position: pd.Series
    returns: pd.Series
    trades: list[Trade] = field(default_factory=list)
    blocked: int = 0            # 因漲跌停而無法成交的次數

    # ---------------------------------------------------------------- 績效

    @property
    def total_return(self) -> float:
        return float(self.equity.iloc[-1] / self.equity.iloc[0] - 1) if len(self.equity) else 0.0

    @property
    def cagr(self) -> float:
        if len(self.equity) < 2:
            return 0.0
        years = len(self.equity) / TRADING_DAYS
        return float((self.equity.iloc[-1] / self.equity.iloc[0]) ** (1 / years) - 1)

    @property
    def sharpe(self) -> float:
        r = self.returns.dropna()
        if len(r) < 2 or r.std() == 0:
            return 0.0
        return float(r.mean() / r.std() * np.sqrt(TRADING_DAYS))

    @property
    def max_drawdown(self) -> float:
        if self.equity.empty:
            return 0.0
        return float((self.equity / self.equity.cummax() - 1).min())

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def trades_per_year(self) -> float:
        years = len(self.equity) / TRADING_DAYS
        return self.n_trades / years if years > 0 else 0.0

    @property
    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.exit_date is not None]
        return float(np.mean([t.net_return > 0 for t in closed])) if closed else 0.0

    @property
    def avg_holding_days(self) -> float:
        return float(np.mean([t.holding_days for t in self.trades])) if self.trades else 0.0

    @property
    def time_in_market(self) -> float:
        return float(self.position.mean()) if len(self.position) else 0.0

    def summary(self) -> dict:
        return {
            "總報酬": self.total_return,
            "年化報酬": self.cagr,
            "Sharpe": self.sharpe,
            "最大回撤": self.max_drawdown,
            "交易次數": self.n_trades,
            "年交易次數": self.trades_per_year,
            "勝率": self.win_rate,
            "平均持有天數": self.avg_holding_days,
            "在market比例": self.time_in_market,
            "漲跌停擋掉": self.blocked,
        }


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    cost_per_side: float = 0.001425,
    sell_tax: float = 0.003,
    check_limits: bool = True,
) -> BacktestResult:
    """把訊號序列跑成權益曲線。

    參數
    ----
    df     : 需含 date（index 或欄位）、open、close
    signal : 與 df 對齊的 0/1 序列。1 = 持有，0 = 空手
             **signal[T] 代表 T 日收盤後決定，T+1 開盤執行**
    """
    data = df.copy()
    if "date" in data.columns:
        data = data.set_index("date")
    data = data.sort_index()

    sig = signal.reindex(data.index).fillna(0).astype(float).clip(0, 1)
    target = sig.shift(1).fillna(0)          # T 日訊號 → T+1 才生效

    open_, close = data["open"].to_numpy(), data["close"].to_numpy()
    prev_close = data["close"].shift(1).to_numpy()
    tgt = target.to_numpy()
    n = len(data)

    pos = np.zeros(n)
    ret = np.zeros(n)
    trades: list[Trade] = []
    blocked = 0
    holding = False
    entry_i = entry_px = None

    for i in range(1, n):
        want = tgt[i] > 0.5
        # 隔日開盤相對前一日收盤的漲跌幅，用來判斷是否漲跌停
        gap = (open_[i] / prev_close[i] - 1) if prev_close[i] and np.isfinite(prev_close[i]) else 0.0
        limit_up = check_limits and gap >= LIMIT
        limit_down = check_limits and gap <= -LIMIT

        if want and not holding:
            if limit_up:                       # 漲停買不到
                blocked += 1
                pos[i] = 0.0
            else:
                holding = True
                entry_i, entry_px = i, open_[i]
                pos[i] = 1.0
                ret[i] = close[i] / open_[i] - 1 - cost_per_side
        elif not want and holding:
            if limit_down:                     # 跌停賣不掉
                blocked += 1
                pos[i] = 1.0
                ret[i] = close[i] / close[i - 1] - 1
            else:
                holding = False
                exit_px = open_[i]
                ret[i] = exit_px / close[i - 1] - 1 - cost_per_side - sell_tax
                gross = exit_px / entry_px - 1
                trades.append(Trade(
                    entry_date=data.index[entry_i], exit_date=data.index[i],
                    entry_price=float(entry_px), exit_price=float(exit_px),
                    holding_days=i - entry_i, gross_return=float(gross),
                    net_return=float(gross - 2 * cost_per_side - sell_tax),
                ))
                pos[i] = 0.0
        elif holding:
            pos[i] = 1.0
            ret[i] = close[i] / close[i - 1] - 1
        else:
            pos[i] = 0.0

    if holding and entry_i is not None:        # 期末仍持有
        gross = close[-1] / entry_px - 1
        trades.append(Trade(
            entry_date=data.index[entry_i], exit_date=None,
            entry_price=float(entry_px), exit_price=None,
            holding_days=n - 1 - entry_i, gross_return=float(gross),
            net_return=float(gross - cost_per_side),
        ))

    returns = pd.Series(ret, index=data.index)
    return BacktestResult(
        equity=(1 + returns).cumprod(),
        position=pd.Series(pos, index=data.index),
        returns=returns,
        trades=trades,
        blocked=blocked,
    )


def buy_and_hold(df: pd.DataFrame, cost_per_side: float = 0.001425) -> BacktestResult:
    """基準線。任何策略贏不過這個就沒有意義。"""
    sig = pd.Series(1.0, index=df["date"] if "date" in df.columns else df.index)
    return run_backtest(df, sig, cost_per_side, sell_tax=0.0, check_limits=False)
