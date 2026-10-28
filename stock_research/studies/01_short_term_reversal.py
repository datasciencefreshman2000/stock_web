"""研究 01：台股短期反轉效應存不存在？

假設：連續下跌後的個股，未來 20 日有均值回歸傾向。
機制：短期賣壓造成流動性折價，提供流動性的人獲得補償。
可否證：扣除 0.471% 來回成本後，平均超額報酬 ≤ 0 則假設被推翻。

執行順序刻意設計成「越簡單的先做」：

  第 1 階段  分組統計          ← 連模型都不用。看不到效果就該停手
  第 2 階段  扣成本
  第 3 階段  Triple-barrier    ← 考慮路徑，比較貼近真實交易
  第 4 階段  多重測試檢定       ← 你試了幾個變體？運氣能做到多好？
  第 5 階段  樣本外驗證         ← 只能跑一次

用法：
    python studies/01_short_term_reversal.py             # 第 1–4 階段
    python studies/01_short_term_reversal.py --final     # 加跑第 5 階段（只能一次！）
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.core.console import setup as _setup  # noqa: E402

_setup()

from research.core import costs, labeling, stats  # noqa: E402
from research.core.cv import effective_sample_size  # noqa: E402
from research.core.data import load_prices  # noqa: E402
from research.core.journal import ResearchLog  # noqa: E402

IN_SAMPLE_END = "2022-01-01"      # ← 一旦決定就不能改
HOLDING_DAYS = 20
N_BUCKETS = 5


def build_features(df: pd.DataFrame, lookback: int, horizon: int) -> pd.DataFrame:
    """每個 (股票, 日期) 算出：過去 N 日報酬、未來 H 日報酬。"""
    out = []
    for symbol, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        close = g["close"]
        g["past_return"] = close / close.shift(lookback) - 1.0
        g["fwd_return"] = labeling.forward_return(close, horizon)
        g["vol20"] = labeling.realized_volatility(close, 20)
        out.append(g)
    res = pd.concat(out, ignore_index=True)
    return res.dropna(subset=["past_return", "fwd_return"])


def bucket_stats(data: pd.DataFrame, n_buckets: int = N_BUCKETS) -> pd.DataFrame:
    """第 1 階段：把過去報酬分組，看各組未來報酬。

    這一步就能回答核心問題，而且完全沒有可調參數可以讓你過擬合。
    """
    d = data.copy()
    d["bucket"] = d.groupby("date")["past_return"].transform(
        lambda s: pd.qcut(s, n_buckets, labels=False, duplicates="drop")
        if s.notna().sum() >= n_buckets else np.nan
    )
    d = d.dropna(subset=["bucket"])

    g = d.groupby("bucket")["fwd_return"]
    table = pd.DataFrame({
        "樣本數": g.size(),
        "平均未來20日報酬": g.mean(),
        "中位數": g.median(),
        "勝率": g.apply(lambda s: (s > 0).mean()),
    })
    table.index = [f"第{int(i)+1}組（{'跌最多' if i == 0 else '漲最多' if i == table.shape[0]-1 else '中間'}）"
                   for i in table.index]
    return table


def long_short_returns(data: pd.DataFrame, n_buckets: int = N_BUCKETS) -> pd.Series:
    """做多「跌最多組」、做空「漲最多組」的每期報酬序列。"""
    d = data.copy()
    d["bucket"] = d.groupby("date")["past_return"].transform(
        lambda s: pd.qcut(s, n_buckets, labels=False, duplicates="drop")
        if s.notna().sum() >= n_buckets else np.nan
    )
    d = d.dropna(subset=["bucket"])
    per_day = d.groupby(["date", "bucket"])["fwd_return"].mean().unstack()
    if per_day.shape[1] < n_buckets:
        return pd.Series(dtype=float)
    return per_day[0] - per_day[per_day.columns[-1]]


def stage_1_and_2(data: pd.DataFrame, log: ResearchLog, lookback: int) -> float:
    print(f"\n{'='*70}")
    print(f"第 1 階段：分組統計（lookback={lookback} 日，持有 {HOLDING_DAYS} 日）")
    print("=" * 70)
    table = bucket_stats(data)
    with pd.option_context("display.float_format", lambda v: f"{v:,.4f}"):
        print(table.to_string())

    spread = table["平均未來20日報酬"].iloc[0] - table["平均未來20日報酬"].iloc[-1]
    print(f"\n  跌最多組 - 漲最多組 = {spread:+.4f}（{spread*100:+.2f}%）")

    print(f"\n{'='*70}")
    print("第 2 階段：扣掉交易成本")
    print("=" * 70)
    cost = costs.round_trip_cost(is_etf=False)
    net = spread - cost.total
    print(f"  毛報酬              {spread:+.4f}  ({spread*100:+.2f}%)")
    print(f"  台股來回成本        {-cost.total:+.4f}  ({-cost.total*100:+.2f}%)")
    print(f"  {'-'*40}")
    print(f"  淨報酬              {net:+.4f}  ({net*100:+.2f}%)")
    periods_per_year = 250 / HOLDING_DAYS
    print(f"\n  若每 {HOLDING_DAYS} 日換一次（一年約 {periods_per_year:.0f} 次）：")
    print(f"    年化成本拖累      {costs.annual_cost_drag(periods_per_year)*100:.1f}%")

    log.record({"lookback": lookback, "horizon": HOLDING_DAYS, "stage": "bucket"},
               "net_spread", net, n_obs=len(data))
    if net <= 0:
        print("\n  → 扣成本後沒有優勢。假設在這個參數下被推翻。")
    else:
        print("\n  → 扣成本後仍為正，繼續往下驗證（還不能高興）。")
    return net


def stage_3_triple_barrier(df: pd.DataFrame, log: ResearchLog, lookback: int) -> None:
    print(f"\n{'='*70}")
    print("第 3 階段：Triple-barrier（考慮路徑，不只看第 20 天）")
    print("=" * 70)

    rows = []
    for symbol, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        close = g["close"]
        past = close / close.shift(lookback) - 1.0
        tb = labeling.triple_barrier(close, horizon=HOLDING_DAYS,
                                     upper_mult=2.0, lower_mult=2.0)
        rows.append(pd.DataFrame({
            "date": g["date"], "past_return": past,
            "label": tb.label, "ret": tb.ret,
            "holding_days": tb.holding_days, "exit_reason": tb.exit_reason,
        }))
    tbl = pd.concat(rows, ignore_index=True).dropna(subset=["past_return", "ret"])

    # 只看「跌最多的 20%」這一組
    cut = tbl["past_return"].quantile(0.2)
    sel = tbl[tbl["past_return"] <= cut]
    cost = costs.round_trip_cost(is_etf=False).total

    print(f"  進場條件：過去 {lookback} 日報酬在最低 20%（門檻 {cut:+.3f}）")
    print(f"  樣本數：{len(sel):,}")
    print(f"  平均持有天數：{sel['holding_days'].mean():.1f} 天（時間上限 {HOLDING_DAYS}）")
    print("\n  出場原因分布：")
    for reason, n in sel["exit_reason"].value_counts().items():
        label = {"take_profit": "觸及停利", "stop_loss": "觸及停損", "timeout": "時間到期"}[reason]
        print(f"    {label:<8} {n:>7,}  ({n/len(sel):.1%})")

    gross = sel["ret"].mean()
    baseline = tbl["ret"].mean()          # 對照組：不挑股票，全部一起買
    excess = gross - baseline
    net = excess - cost

    print(f"\n  平均毛報酬          {gross:+.4f}")
    print(f"  對照組（全部標的）  {baseline:+.4f}   ← 沒有這一行，上面那個數字沒有意義")
    print(f"  {'-'*40}")
    print(f"  超額報酬            {excess:+.4f}")
    print(f"  扣成本後            {net:+.4f}")
    print(f"  勝率                {(sel['ret'] > cost).mean():.1%}（以扣成本後為準）")

    if excess <= 0:
        print("\n  → 挑出來的股票並沒有比隨便買更好。這個訊號沒有選股能力。")

    log.record({"lookback": lookback, "stage": "triple_barrier",
                "upper_mult": 2.0, "lower_mult": 2.0},
               "net_excess_return", net, n_obs=len(sel))


def stage_4_significance(data: pd.DataFrame, log: ResearchLog) -> None:
    print(f"\n{'='*70}")
    print("第 4 階段：多重測試檢定 —— 你試了幾個變體？")
    print("=" * 70)

    ls = long_short_returns(data).dropna()
    if ls.empty:
        print("  樣本不足，略過。")
        return

    # 未來 20 日報酬每天都重疊，換算成不重疊的期數
    n_eff = effective_sample_size(len(ls), HOLDING_DAYS)
    per_period = ls.iloc[::HOLDING_DAYS]
    sr = stats.sharpe_ratio(per_period.to_numpy(), periods_per_year=250 // HOLDING_DAYS)

    print(f"  多空組合期數        {len(ls):,} 天 → 有效獨立樣本約 {n_eff:,} 期")
    print(f"  年化 Sharpe         {sr:.3f}")
    se = stats.sharpe_standard_error(len(per_period), sr, 250 // HOLDING_DAYS)
    print(f"  Sharpe 標準誤       {se:.3f}   → 95% 信賴區間約 [{sr-1.96*se:.2f}, {sr+1.96*se:.2f}]")

    print(f"\n  【null 分布檢定】試過的變體數 = {log.variants_tested}")
    result = stats.null_distribution_test(
        observed=sr, n_obs=len(per_period),
        variants_tested=max(log.variants_tested, 1),
        periods_per_year=250 // HOLDING_DAYS,
    )
    print(result.report())

    thr = stats.deflated_sharpe_threshold(len(per_period), max(log.variants_tested, 1),
                                          250 // HOLDING_DAYS)
    print(f"\n  解析近似門檻（交叉核對）：{thr:.3f}")


def stage_5_out_of_sample(df: pd.DataFrame, log: ResearchLog, lookback: int) -> None:
    print(f"\n{'='*70}")
    print("第 5 階段：樣本外驗證 —— 只能跑一次")
    print("=" * 70)
    log.mark_out_of_sample_used()

    oos = df[df["date"] >= IN_SAMPLE_END]
    data = build_features(oos, lookback, HOLDING_DAYS)
    table = bucket_stats(data)
    spread = table["平均未來20日報酬"].iloc[0] - table["平均未來20日報酬"].iloc[-1]
    net = spread - costs.round_trip_cost(is_etf=False).total

    print(f"  期間：{IN_SAMPLE_END} 之後，樣本數 {len(data):,}")
    print(f"  淨報酬（跌最多 - 漲最多）：{net:+.4f}  ({net*100:+.2f}%)")
    print("\n  → 這個數字才是你該相信的。樣本內再漂亮都不算數。")
    print("  → 如果不理想，不要回去調參數再跑一次。那會讓樣本外失效。")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true", help="跑樣本外驗證（只能一次）")
    parser.add_argument("--lookback", type=int, default=5, help="回看幾日報酬")
    parser.add_argument("--synthetic-edge", type=float, default=0.0,
                        help="合成資料植入的反轉強度，用來檢查程式找不找得到真訊號")
    args = parser.parse_args()

    df, source = load_prices(reversal_edge=args.synthetic_edge)
    print(f"資料來源：{source}")
    print(f"標的數 {df['symbol'].nunique()}｜期間 {df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d}｜共 {len(df):,} 列")

    log = ResearchLog(
        study="01_short_term_reversal",
        hypothesis="連續下跌後的個股，未來 20 日有均值回歸傾向",
        mechanism="短期賣壓造成流動性折價，提供流動性者獲得補償",
        falsification=f"扣除 {costs.STOCK_ROUND_TRIP:.3%} 來回成本後平均超額報酬 ≤ 0",
        in_sample_end=IN_SAMPLE_END,
    )

    in_sample = df[df["date"] < IN_SAMPLE_END]
    print(f"\n樣本內：{in_sample['date'].min():%Y-%m-%d} ~ {in_sample['date'].max():%Y-%m-%d}")
    print(f"樣本外：{IN_SAMPLE_END} 之後（第 5 階段才會碰）")

    data = build_features(in_sample, args.lookback, HOLDING_DAYS)
    stage_1_and_2(data, log, args.lookback)
    stage_3_triple_barrier(in_sample, log, args.lookback)
    stage_4_significance(data, log)

    if args.final:
        stage_5_out_of_sample(df, log, args.lookback)

    path = log.save()
    print(f"\n{'='*70}")
    print(log.summary())
    print(f"\n研究日誌已存到 {path}")


if __name__ == "__main__":
    main()
