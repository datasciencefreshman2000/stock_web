import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core import costs, labeling, stats  # noqa: E402
from research.core.cv import effective_sample_size, purged_walk_forward, train_test_by_date  # noqa: E402
from research.core.journal import ResearchLog  # noqa: E402


# ------------------------------------------------------------------ 成本

def test_round_trip_cost_is_about_047_percent():
    assert costs.STOCK_ROUND_TRIP == pytest.approx(0.004710, abs=1e-6)


def test_etf_cost_is_lower_than_stock():
    assert costs.ETF_ROUND_TRIP < costs.STOCK_ROUND_TRIP


def test_weekly_trading_burns_a_quarter_of_capital():
    """每週換股一年 52 次，成本拖累約 24.5%。"""
    assert costs.annual_cost_drag(52) == pytest.approx(0.245, abs=0.01)


def test_fees_match_backend_implementation():
    assert costs.buy_fee(100, 1000) == 85
    assert costs.sell_tax(100, 1000, is_etf=False) == 300
    assert costs.sell_tax(100, 1000, is_etf=True) == 100


def test_minimum_fee_applies():
    assert costs.buy_fee(0.01, 1) == 1


# ------------------------------------------------------------------ 標籤

def _series(values):
    return pd.Series(values, index=pd.bdate_range("2020-01-01", periods=len(values)))


def test_triple_barrier_hits_upper_first():
    close = _series([100] * 25 + [130] + [100] * 25)
    vol = pd.Series(0.01, index=close.index)
    res = labeling.triple_barrier(close, horizon=20, vol=vol)
    assert res.label.iloc[10] == 1
    assert res.exit_reason.iloc[10] == "take_profit"


def test_triple_barrier_hits_lower_first():
    close = _series([100] * 25 + [70] + [100] * 25)
    vol = pd.Series(0.01, index=close.index)
    res = labeling.triple_barrier(close, horizon=20, vol=vol)
    assert res.label.iloc[10] == -1
    assert res.exit_reason.iloc[10] == "stop_loss"


def test_triple_barrier_times_out_when_flat():
    close = _series([100.0] * 60)
    vol = pd.Series(0.02, index=close.index)
    res = labeling.triple_barrier(close, horizon=20, vol=vol)
    assert res.label.iloc[5] == 0
    assert res.exit_reason.iloc[5] == "timeout"


def test_triple_barrier_holding_days_never_exceed_horizon():
    rng = np.random.default_rng(0)
    close = _series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))))
    res = labeling.triple_barrier(close, horizon=20)
    assert res.holding_days.dropna().max() <= 20


def test_triple_barrier_captures_path_not_just_endpoint():
    """關鍵差異：中間暴跌但最後回到原點，固定期間報酬看不出來，triple-barrier 會標成停損。"""
    close = _series([100] * 25 + [60] + [100] * 30)
    vol = pd.Series(0.01, index=close.index)
    fixed = labeling.forward_return(close, 20)
    tb = labeling.triple_barrier(close, horizon=20, vol=vol)
    assert fixed.iloc[10] == pytest.approx(0.0)   # 固定期間：看起來沒事
    assert tb.label.iloc[10] == -1                 # 實際上早就被停損


# ------------------------------------------------------------------ 切分

def test_purged_split_removes_overlapping_training_samples():
    splits = purged_walk_forward(1000, n_splits=5, horizon=20, embargo=0)
    for s in splits:
        assert s.train.max() < s.test.min() - 20


def test_purged_split_train_always_before_test():
    for s in purged_walk_forward(1000, n_splits=5, horizon=10):
        assert s.train.max() < s.test.min()


def test_effective_sample_size_divides_by_horizon():
    assert effective_sample_size(2000, 20) == 100
    assert effective_sample_size(156000, 20) == 7800


def test_train_test_by_date_splits_correctly():
    dates = pd.bdate_range("2020-01-01", periods=100)
    ins, oos = train_test_by_date(dates, "2020-03-01")
    assert len(ins) + len(oos) == 100
    assert dates[ins].max() < pd.Timestamp("2020-03-01") <= dates[oos].min()


# ------------------------------------------------------------------ 統計

def test_sharpe_of_pure_noise_is_near_zero():
    rng = np.random.default_rng(1)
    assert abs(stats.sharpe_ratio(rng.normal(0, 0.015, 4000))) < 0.35


def test_null_threshold_rises_with_more_variants():
    """核心洞察：試越多變體，門檻越高。"""
    few = stats.null_distribution_test(0.5, 1000, variants_tested=1, n_simulations=300)
    many = stats.null_distribution_test(0.5, 1000, variants_tested=100, n_simulations=300)
    assert many.null_p95 > few.null_p95


def test_noise_result_fails_null_test_when_many_variants_tried():
    """Sharpe 0.6 在只試 1 次時像有東西，試了 200 次就只是運氣。"""
    r = stats.null_distribution_test(0.6, 4000, variants_tested=200, n_simulations=400)
    assert not r.passes


def test_strong_result_passes_null_test():
    r = stats.null_distribution_test(2.5, 4000, variants_tested=50, n_simulations=400)
    assert r.passes


def test_sharpe_standard_error_is_large_for_short_history():
    """16 年日資料的 Sharpe 標準誤約 0.25。"""
    assert stats.sharpe_standard_error(16 * 250) == pytest.approx(0.25, abs=0.02)


def test_permutation_test_finds_no_edge_in_random_signal():
    rng = np.random.default_rng(3)
    r = stats.permutation_test(rng.normal(0, 0.02, 2000), rng.normal(0, 1, 2000), n_permutations=300)
    assert not r["passes"]


def test_permutation_test_finds_planted_edge():
    rng = np.random.default_rng(4)
    signal = rng.normal(0, 1, 2000)
    returns = 0.01 * np.sign(signal) + rng.normal(0, 0.005, 2000)
    r = stats.permutation_test(returns, signal, n_permutations=300)
    assert r["passes"]


def test_deflated_threshold_agrees_with_simulation():
    n, v = 4000, 50
    analytic = stats.deflated_sharpe_threshold(n, v)
    sim = stats.null_distribution_test(0, n, v, n_simulations=400).null_mean
    assert analytic == pytest.approx(sim, abs=0.15)


# ------------------------------------------------------------------ 研究日誌

def test_journal_counts_variants():
    log = ResearchLog(study="t", hypothesis="h", mechanism="m")
    for lb in (3, 5, 10):
        log.record({"lookback": lb}, "ret", 0.01 * lb, n_obs=100)
    assert log.variants_tested == 3
    assert log.best().params["lookback"] == 10


def test_out_of_sample_can_only_be_used_once():
    log = ResearchLog(study="t", hypothesis="h", mechanism="m")
    log.mark_out_of_sample_used()
    with pytest.raises(RuntimeError, match="樣本外已經用過"):
        log.mark_out_of_sample_used()


def test_journal_roundtrip(tmp_path):
    log = ResearchLog(study="t", hypothesis="h", mechanism="m", falsification="f")
    log.record({"a": 1}, "ret", 0.05, n_obs=10)
    log.save(tmp_path)
    loaded = ResearchLog.load("t", tmp_path)
    assert loaded.variants_tested == 1
    assert loaded.hypothesis == "h"


# ------------------------------------------------------------------ 技術指標

from research.core import indicators as ind  # noqa: E402


def _ohlc(values):
    idx = pd.bdate_range("2020-01-01", periods=len(values))
    close = pd.Series(values, index=idx, dtype=float)
    return close * 1.01, close * 0.99, close


def test_price_vs_ma_positive_in_uptrend():
    close = pd.Series(np.linspace(100, 200, 200), index=pd.bdate_range("2020-01-01", periods=200))
    assert ind.price_vs_ma(close, 60).iloc[-1] > 0


def test_rsi_bounded_and_high_when_only_rising():
    close = pd.Series(np.linspace(100, 200, 100), index=pd.bdate_range("2020-01-01", periods=100))
    r = ind.rsi(close).dropna()
    assert r.between(0, 100).all()
    assert r.iloc[-1] > 90


def test_momentum_12_1_skips_recent_month():
    """最近一個月的變動不該影響 12-1 動能。"""
    base = np.concatenate([np.linspace(100, 150, 260), np.full(21, 150.0)])
    spiked = base.copy()
    spiked[-21:] = 300.0                     # 最近一個月暴漲
    idx = pd.bdate_range("2020-01-01", periods=len(base))
    a = ind.momentum_12_1(pd.Series(base, index=idx)).iloc[-1]
    b = ind.momentum_12_1(pd.Series(spiked, index=idx)).iloc[-1]
    assert a == pytest.approx(b)


def test_atr_rises_with_volatility():
    rng = np.random.default_rng(0)
    calm = 100 + np.cumsum(rng.normal(0, 0.2, 200))
    wild = 100 + np.cumsum(rng.normal(0, 3.0, 200))
    assert ind.atr(*_ohlc(wild)).iloc[-1] > ind.atr(*_ohlc(calm)).iloc[-1]


def test_vol_percentile_is_between_zero_and_one():
    rng = np.random.default_rng(1)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 1200))),
                      index=pd.bdate_range("2018-01-01", periods=1200))
    p = ind.vol_percentile(close, 20, 750).dropna()
    assert p.between(0, 1).all()


def test_relative_strength_negative_when_underperforming():
    idx = pd.bdate_range("2020-01-01", periods=100)
    stock = pd.Series(np.linspace(100, 110, 100), index=idx)
    bench = pd.Series(np.linspace(100, 130, 100), index=idx)
    assert ind.relative_strength(stock, bench, 60).iloc[-1] < 0


def test_limit_up_detection():
    close = pd.Series([100, 110, 121, 122], index=pd.bdate_range("2020-01-01", periods=4))
    assert ind.is_limit_up(close).tolist() == [False, True, True, False]


def test_consecutive_limit_up_counts_streak():
    close = pd.Series([100, 110, 121, 122, 134], index=pd.bdate_range("2020-01-01", periods=5))
    assert ind.consecutive_limit_up(close).tolist() == [0, 1, 2, 0, 1]


def test_core_feature_set_has_few_features():
    """刻意只留 5-7 個。指標多不等於資訊多。"""
    rng = np.random.default_rng(2)
    idx = pd.bdate_range("2018-01-01", periods=800)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 800))), index=idx)
    vol = pd.Series(rng.lognormal(15, 0.5, 800), index=idx)
    feats = ind.core_feature_set(close * 1.01, close * 0.99, close, vol)
    assert feats.shape[1] <= 7


# ------------------------------------------------------------------ 股票池

from research.core import universe as uni  # noqa: E402


def test_effective_holdings_equal_weights():
    assert uni.effective_holdings([0.1] * 10) == pytest.approx(10.0)


def test_effective_holdings_concentrated():
    """0050 的真實權重：名目 50 檔，有效約 3 檔。"""
    top10 = [0.5737, 0.0611, 0.0367, 0.0299, 0.0220, 0.0187, 0.0175, 0.0153, 0.0137, 0.0123]
    rest = [(1 - sum(top10)) / 40] * 40
    eff = uni.effective_holdings(top10 + rest)
    assert 2.5 < eff < 3.5


def test_effective_holdings_single_asset():
    assert uni.effective_holdings([1.0]) == pytest.approx(1.0)


def _universe_frame(n_symbols=5, days=400, turnover=1e9, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=days)
    out = []
    for i in range(n_symbols):
        close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, days))))
        out.append(pd.DataFrame({
            "symbol": f"TW:{2000+i}", "date": dates, "close": close.values,
            "volume": turnover / close.values,
        }))
    return pd.concat(out, ignore_index=True)


def test_build_universe_excludes_short_history():
    df = _universe_frame(days=400)
    res = uni.build_universe(df, uni.UniverseConfig(min_history_days=250))
    early = res[res["date"] < res["date"].min() + pd.Timedelta(days=100)]
    assert not early["in_universe"].any()


def test_build_universe_excludes_illiquid():
    df = _universe_frame(turnover=1e5)          # 成交金額遠低於門檻
    res = uni.build_universe(df, uni.UniverseConfig(min_avg_turnover=1e7))
    assert not res["in_universe"].any()


def test_build_universe_uses_only_past_information():
    """avg_turnover 必須 shift(1)，不能包含當天資料。"""
    df = _universe_frame(n_symbols=1, days=300)
    res = uni.build_universe(df)
    g = res.sort_values("date")
    manual = (g["close"] * g["volume"]).rolling(60).mean().shift(1)
    pd.testing.assert_series_equal(g["avg_turnover"].reset_index(drop=True),
                                   manual.reset_index(drop=True), check_names=False)


def test_max_symbols_caps_universe_size():
    df = _universe_frame(n_symbols=10, days=400)
    res = uni.build_universe(df, uni.UniverseConfig(max_symbols=3))
    per_day = res[res["in_universe"]].groupby("date")["symbol"].nunique()
    assert per_day.max() <= 3


def test_diagnose_warns_about_survivorship():
    df = _universe_frame(n_symbols=40, days=800)   # 全部活到最後
    d = uni.diagnose(df)
    assert d.survivorship_ratio > 0.98
    assert any("倖存者偏誤" in w for w in d.warnings)


def test_diagnose_warns_about_small_universe():
    df = _universe_frame(n_symbols=5, days=800)
    assert any("統計檢定力" in w for w in uni.diagnose(df).warnings)


def test_diagnose_detects_delisted_symbols():
    df = _universe_frame(n_symbols=10, days=800)
    # 讓一半的標的提早消失
    cutoff = df["date"].quantile(0.5)
    drop = df["symbol"].unique()[:5]
    df = df[~((df["symbol"].isin(drop)) & (df["date"] > cutoff))]
    d = uni.diagnose(df)
    assert d.survivorship_ratio == pytest.approx(0.5, abs=0.01)


def test_to_symbols_adds_prefix():
    assert uni.to_symbols(["2330", "0050"]) == ["TW:2330", "TW:0050"]


def test_my_holdings_list_is_sane():
    assert len(uni.MY_HOLDINGS) == 39
    assert "2330" in uni.MY_HOLDINGS and uni.BENCHMARK in uni.MY_HOLDINGS


# ------------------------------------------------------------------ 主題驗證

def _theme_prices(theme_strength=1.5, market_strength=1.0, n_theme=3, n_other=8,
                  days=900, seed=0):
    """造出「市場因子 + 主題因子 + 個股雜訊」的價格。

    n_theme 檔共享主題因子，n_other 檔沒有 —— 用來當對照組。
    """
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=days)
    market = rng.normal(0, 0.012, days)
    theme = rng.normal(0, 0.012, days)
    cols = {}
    for i in range(n_theme):
        r = market_strength * market + theme_strength * theme + rng.normal(0, 0.012, days)
        cols[f"TW:{2000+i}"] = 100 * np.exp(np.cumsum(r))
    for j in range(n_other):
        r = market_strength * market + rng.normal(0, 0.012, days)
        cols[f"TW:{3000+j}"] = 100 * np.exp(np.cumsum(r))
    prices = pd.DataFrame(cols, index=idx)
    mkt = pd.Series(100 * np.exp(np.cumsum(market)), index=idx)
    return prices, mkt, [f"TW:{2000+i}" for i in range(n_theme)]


def test_market_residuals_removes_common_factor():
    """剝掉市場因子後，只受市場驅動的股票之間應該幾乎不相關。"""
    prices, mkt, _ = _theme_prices(theme_strength=0.0, market_strength=2.0)
    rets = prices.pct_change(fill_method=None)
    mret = mkt.pct_change(fill_method=None)
    assert rets.corr().values[np.triu_indices(len(prices.columns), 1)].mean() > 0.5
    res = uni.market_residuals(rets, mret).dropna()
    assert abs(res.corr().values[np.triu_indices(len(res.columns), 1)].mean()) < 0.15


def test_validate_theme_detects_real_theme():
    prices, mkt, members = _theme_prices(theme_strength=1.5)
    v = uni.validate_theme(prices, members, mkt, "測試主題")
    assert v.residual_pairwise_corr > 0.3
    assert v.z_score > 4
    assert "✅" in v.verdict


def test_validate_theme_rejects_market_only_group():
    """共同性全部來自市場 → 剝掉之後就沒了，不是主題。"""
    prices, mkt, members = _theme_prices(theme_strength=0.0, market_strength=2.0)
    v = uni.validate_theme(prices, members, mkt, "假主題")
    assert v.z_score < 2
    assert "❌" in v.verdict or "⚠" in v.verdict


def test_raw_correlation_alone_would_mislead():
    """關鍵回歸測試：原始相關很高，但那是市場造成的，殘差才看得出真相。"""
    prices, mkt, members = _theme_prices(theme_strength=0.0, market_strength=2.5)
    v = uni.validate_theme(prices, members, mkt, "假主題")
    assert v.raw_pairwise_corr > 0.55          # 看起來很像主題
    assert v.residual_pairwise_corr < 0.15     # 其實不是


def test_validate_theme_flags_homogeneous_group():
    prices, mkt, members = _theme_prices(theme_strength=6.0, market_strength=0.5)
    v = uni.validate_theme(prices, members, mkt)
    assert v.first_pc_explained > 0.65
    assert "同質" in v.verdict


def test_validate_theme_finds_odd_member():
    prices, mkt, members = _theme_prices(theme_strength=2.0, n_theme=3)
    rng = np.random.default_rng(99)
    prices["TW:9999"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(prices))))
    v = uni.validate_theme(prices, members + ["TW:9999"], mkt)
    assert v.weakest_member == "TW:9999"


def test_validate_theme_needs_two_members():
    prices, mkt, members = _theme_prices()
    with pytest.raises(ValueError, match="至少要 2 檔"):
        uni.validate_theme(prices, members[:1], mkt)


def test_themes_dict_has_memory_group():
    assert "記憶體" in uni.THEMES
    assert set(uni.THEMES["記憶體"]) == {"2408", "2344", "2337"}


def test_to_wide_pivots_correctly():
    df = _universe_frame(n_symbols=3, days=50)
    wide = uni.to_wide(df)
    assert wide.shape[1] == 3
    assert wide.index.is_monotonic_increasing


# ------------------------------------------------------------------ 回測引擎

from research.backtest.engine import buy_and_hold, run_backtest  # noqa: E402
from research.backtest.strategies import STRATEGIES, ma_cross, ma_trend, momentum  # noqa: E402


def _bars(closes, opens=None):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    opens = opens if opens is not None else closes
    return pd.DataFrame({"date": idx, "open": opens, "high": [c * 1.01 for c in closes],
                         "low": [c * 0.99 for c in closes], "close": closes,
                         "volume": [1e6] * len(closes)})


def test_signal_executes_next_day_not_same_day():
    """T 日訊號、T+1 開盤成交。這是最重要的前視偏誤防線。"""
    closes = [100.0] * 5 + [200.0] + [200.0] * 5
    df = _bars(closes)
    sig = pd.Series(0.0, index=df["date"])
    sig.iloc[5] = 1.0          # 在暴漲當天才發出訊號
    res = run_backtest(df, sig, cost_per_side=0, sell_tax=0, check_limits=False)
    # 若有前視偏誤，會在第 5 天以 100 買到而賺 100%；正確行為是第 6 天以 200 買
    assert res.total_return == pytest.approx(0.0, abs=1e-9)


def test_buy_and_hold_also_obeys_next_day_execution():
    """基準線也走 T+1 成交，才跟策略同一個標準。

    3 根 K：訊號在第 0 根發出 → 第 1 根開盤買入 → 只吃到 110→121。
    如果這裡回傳 1.21，代表基準線偷跑，比較就不公平。
    """
    df = _bars([100.0, 110.0, 121.0])
    res = buy_and_hold(df, cost_per_side=0)
    assert res.equity.iloc[-1] == pytest.approx(1.10, rel=1e-6)


def test_benchmark_and_strategy_use_same_execution_rule():
    """全持有的策略訊號，結果必須等於 buy_and_hold。"""
    rng = np.random.default_rng(5)
    closes = list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 200))))
    df = _bars(closes)
    always = pd.Series(1.0, index=df["date"])
    a = run_backtest(df, always, cost_per_side=0, sell_tax=0, check_limits=False)
    b = buy_and_hold(df, cost_per_side=0)
    assert a.equity.iloc[-1] == pytest.approx(b.equity.iloc[-1], rel=1e-9)


def test_costs_reduce_return():
    df = _bars([100.0] * 10)
    sig = pd.Series([0, 1, 1, 1, 0, 0, 0, 0, 0, 0], index=df["date"], dtype=float)
    free = run_backtest(df, sig, cost_per_side=0, sell_tax=0, check_limits=False)
    paid = run_backtest(df, sig, cost_per_side=0.001395, sell_tax=0.003, check_limits=False)
    assert paid.total_return < free.total_return


def test_limit_up_blocks_entry():
    """隔日開盤漲停時買不到。"""
    closes = [100.0, 100.0, 115.0, 115.0]
    opens = [100.0, 100.0, 115.0, 115.0]      # 第 2 日開盤較前收 +15% → 漲停
    df = _bars(closes, opens)
    sig = pd.Series([0.0, 1.0, 1.0, 1.0], index=df["date"])
    res = run_backtest(df, sig, cost_per_side=0, sell_tax=0, check_limits=True)
    assert res.blocked >= 1


def test_trade_records_are_created():
    df = _bars([100.0] * 3 + [120.0] * 3 + [120.0] * 4)
    sig = pd.Series([0, 1, 1, 1, 1, 0, 0, 0, 0, 0], index=df["date"], dtype=float)
    res = run_backtest(df, sig, cost_per_side=0, sell_tax=0, check_limits=False)
    assert res.n_trades == 1
    assert res.trades[0].exit_date is not None


def test_open_trade_at_end_is_recorded():
    df = _bars([100.0] * 5)
    sig = pd.Series([0, 1, 1, 1, 1], index=df["date"], dtype=float)
    res = run_backtest(df, sig, cost_per_side=0, sell_tax=0, check_limits=False)
    assert res.n_trades == 1 and res.trades[0].exit_date is None


def test_max_drawdown_is_negative_or_zero():
    rng = np.random.default_rng(0)
    closes = list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))))
    df = _bars(closes)
    res = buy_and_hold(df, cost_per_side=0)
    assert res.max_drawdown <= 0


def test_flat_strategy_has_zero_return():
    df = _bars([100.0, 150.0, 80.0, 120.0])
    sig = pd.Series(0.0, index=df["date"])
    res = run_backtest(df, sig, check_limits=False)
    assert res.total_return == pytest.approx(0.0, abs=1e-12)
    assert res.time_in_market == 0.0


# --- 策略訊號本身 ---

def test_ma_trend_holds_in_uptrend_and_exits_in_downtrend():
    up = list(np.linspace(100, 200, 150))
    down = list(np.linspace(200, 80, 150))
    df = _bars(up + down)
    sig = ma_trend(df, window=50, buffer=0.0)
    assert sig.iloc[140] == 1.0
    assert sig.iloc[-1] == 0.0


def test_ma_trend_buffer_reduces_trades():
    rng = np.random.default_rng(3)
    closes = list(100 + np.cumsum(rng.normal(0, 1.0, 800)))
    df = _bars(closes)
    no_buf = ma_trend(df, 100, 0.0).diff().abs().sum()
    with_buf = ma_trend(df, 100, 0.05).diff().abs().sum()
    assert with_buf <= no_buf


def test_ma_cross_is_binary():
    df = _bars(list(np.linspace(100, 200, 300)))
    assert set(ma_cross(df, 10, 30).unique()) <= {0.0, 1.0}


def test_momentum_skips_recent_month():
    base = list(np.linspace(100, 200, 300))
    df = _bars(base)
    assert momentum(df, lookback=252, skip=21).iloc[-1] == 1.0


def test_all_strategies_produce_valid_signals():
    """每個策略都要回傳 0/1、長度正確、沒有 NaN。"""
    rng = np.random.default_rng(7)
    closes = list(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, 1200))))
    df = _bars(closes)
    for key, spec in STRATEGIES.items():
        sig = spec.fn(df)
        assert len(sig) == len(df), key
        assert sig.notna().all(), key
        assert set(np.unique(sig.to_numpy())) <= {0.0, 1.0}, key


def test_strategies_do_not_use_future_data():
    """把最後 100 天的資料改掉，前面的訊號不能變。"""
    rng = np.random.default_rng(11)
    closes = list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 800))))
    df1 = _bars(closes)
    tampered = closes[:700] + [c * 3 for c in closes[700:]]
    df2 = _bars(tampered)
    for key, spec in STRATEGIES.items():
        s1, s2 = spec.fn(df1), spec.fn(df2)
        assert (s1.iloc[:700].to_numpy() == s2.iloc[:700].to_numpy()).all(), key
