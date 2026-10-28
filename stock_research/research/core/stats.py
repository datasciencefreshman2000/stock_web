"""統計檢定：處理多重測試偏誤。

一般的 p < 0.05 在這裡沒有意義，因為它假設你只做一次測試。
實際上你調一次參數就是一次測試，一個下午隨手試掉 50 個。

實測：真實優勢 = 0 的策略，試 50 個變體取最好的，
平均 Sharpe 會是 0.58；試 500 個會是 0.77。
"""

from dataclasses import dataclass

import numpy as np

TRADING_DAYS = 250


def sharpe_ratio(returns: np.ndarray, periods_per_year: int = TRADING_DAYS) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_standard_error(n_obs: int, sharpe: float = 0.0,
                          periods_per_year: int = TRADING_DAYS) -> float:
    """Sharpe 估計值的標準誤（年化）。

    16 年日資料 → 標準誤約 0.25。
    所以「A 策略 0.9 比 B 策略 0.7 好」在統計上站不住。
    """
    if n_obs < 2:
        return float("inf")
    years = n_obs / periods_per_year
    return float(np.sqrt((1 + 0.5 * sharpe ** 2) / years))


@dataclass
class NullTestResult:
    observed: float
    null_mean: float
    null_p95: float
    null_p99: float
    p_value: float
    variants_tested: int
    passes: bool

    def report(self) -> str:
        verdict = "通過" if self.passes else "沒有通過 —— 這個結果用運氣就做得出來"
        return (
            f"  你的結果          {self.observed:>8.3f}\n"
            f"  試了幾個變體      {self.variants_tested:>8d}\n"
            f"  純運氣的平均值    {self.null_mean:>8.3f}\n"
            f"  純運氣的 95 分位  {self.null_p95:>8.3f}   ← 要超過這個才有意義\n"
            f"  純運氣的 99 分位  {self.null_p99:>8.3f}\n"
            f"  p-value           {self.p_value:>8.3f}\n"
            f"  判定：{verdict}"
        )


def null_distribution_test(
    observed: float,
    n_obs: int,
    variants_tested: int,
    daily_vol: float = 0.015,
    n_simulations: int = 2000,
    periods_per_year: int = TRADING_DAYS,
    seed: int = 0,
) -> NullTestResult:
    """自己建 null 分布——最直觀也最推薦的多重測試校正。

    做法：產生 `variants_tested` 個真實優勢 = 0 的假策略，
    取其中最好的 Sharpe，重複 n_simulations 次得到分布。
    你的結果要超過這個分布的 95 百分位才算有意義。

    這比背 Deflated Sharpe Ratio 的公式直觀，而且你完全知道自己在算什麼。
    """
    rng = np.random.default_rng(seed)
    best = np.empty(n_simulations)
    for i in range(n_simulations):
        fake = rng.normal(0.0, daily_vol, size=(variants_tested, n_obs))
        sr = fake.mean(axis=1) / fake.std(axis=1, ddof=1) * np.sqrt(periods_per_year)
        best[i] = sr.max()

    p95, p99 = np.percentile(best, [95, 99])
    p_value = float((best >= observed).mean())
    return NullTestResult(
        observed=float(observed),
        null_mean=float(best.mean()),
        null_p95=float(p95),
        null_p99=float(p99),
        p_value=p_value,
        variants_tested=variants_tested,
        passes=bool(observed > p95),
    )


def permutation_test(
    returns: np.ndarray,
    signal: np.ndarray,
    n_permutations: int = 2000,
    seed: int = 0,
) -> dict:
    """置換檢定：打亂訊號與報酬的對應關係，看原本的優勢還在不在。

    比 null_distribution_test 更貼近真實資料，因為它保留了報酬的實際分布
    （偏度、峰度、厚尾），只破壞訊號與報酬的關聯。
    """
    rng = np.random.default_rng(seed)
    returns = np.asarray(returns, dtype=float)
    signal = np.asarray(signal, dtype=float)
    mask = np.isfinite(returns) & np.isfinite(signal)
    returns, signal = returns[mask], signal[mask]

    observed = float(np.mean(returns[signal > 0]) - np.mean(returns[signal <= 0])) \
        if (signal > 0).any() and (signal <= 0).any() else 0.0

    null = np.empty(n_permutations)
    for i in range(n_permutations):
        shuffled = rng.permutation(signal)
        a, b = returns[shuffled > 0], returns[shuffled <= 0]
        null[i] = a.mean() - b.mean() if len(a) and len(b) else 0.0

    return {
        "observed": observed,
        "null_mean": float(null.mean()),
        "null_p95": float(np.percentile(null, 95)),
        "p_value": float((np.abs(null) >= abs(observed)).mean()),
        "passes": bool(abs(observed) > np.percentile(np.abs(null), 95)),
    }


def deflated_sharpe_threshold(n_obs: int, variants_tested: int,
                              periods_per_year: int = TRADING_DAYS) -> float:
    """多重測試下，純運氣預期能達到的最大 Sharpe（解析近似）。

    N 個獨立標準常態的期望最大值 ≈ sqrt(2 ln N)，
    再乘上 Sharpe 估計的標準誤。
    這是 null_distribution_test 的快速版本，用來交叉核對。
    """
    if variants_tested < 2:
        return 0.0
    se = sharpe_standard_error(n_obs, 0.0, periods_per_year)
    return float(se * np.sqrt(2 * np.log(variants_tested)))
