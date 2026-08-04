"""Checkpoint 增量結算的正確性。

最重要的一條規則：從 checkpoint 續算出來的結果，
必須和從第一筆交易全量重算「完全一致」。
只要這條守得住，checkpoint 就只是效能優化，不會影響正確性。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.fifo import FifoState, apply_trades, summarize_state
from services.settlement import (
    _resume_point,
    _state_to_checkpoint,
    analyze_account,
    group_by_ticker,
    should_settle,
    trade_date_key,
)

US = "美股"


def buy(date, qty, price, fee=0, trade_id=""):
    return {
        "account": US,
        "ticker": "AAA",
        "date": date,
        "buy_qty": qty,
        "sell_qty": None,
        "price": price,
        "fee": fee,
        "id": trade_id,
    }


def sell(date, qty, price, fee=0, trade_id=""):
    return {
        "account": US,
        "ticker": "AAA",
        "date": date,
        "buy_qty": None,
        "sell_qty": qty,
        "price": price,
        "fee": fee,
        "id": trade_id,
    }


TRADES = [
    buy("2026-01-10", 10, 100, trade_id="1"),
    buy("2026-02-15", 20, 120, trade_id="2"),
    sell("2026-03-20", 15, 180, trade_id="3"),
    buy("2026-05-05", 5, 150, trade_id="4"),
    sell("2026-07-01", 10, 200, trade_id="5"),
]


def make_checkpoint(trades, as_of_date, account=US, ticker="AAA", actions=None):
    covered = [t for t in trades if trade_date_key(t) <= as_of_date]
    covered_actions = [a for a in (actions or []) if str(a["ex_date"]) <= as_of_date]
    state = apply_trades(FifoState(), covered, account, ticker, covered_actions)
    row = _state_to_checkpoint(account, ticker, as_of_date, state)
    # 模擬從資料庫讀回來的樣子
    return {ticker: row}


@pytest.mark.parametrize("as_of", ["2026-01-31", "2026-02-28", "2026-03-31", "2026-06-30"])
def test_incremental_matches_full_recompute(as_of):
    full = analyze_account(US, TRADES)
    incremental = analyze_account(US, TRADES, checkpoints=make_checkpoint(TRADES, as_of))

    for key in ("current_qty", "total_cost", "avg_price", "realized_pnl", "total_fee", "total_tax"):
        assert incremental["AAA"][key] == pytest.approx(full["AAA"][key]), key


def test_incremental_matches_full_recompute_with_split():
    actions_by_symbol = {"MUU": [{"action_type": "split", "ex_date": "2026-04-01", "ratio": 4}]}
    trades = [dict(t, ticker="MUU") for t in TRADES]

    full = analyze_account(US, trades, actions_by_symbol=actions_by_symbol)
    checkpoints = make_checkpoint(
        trades, "2026-04-30", ticker="MUU", actions=actions_by_symbol["MUU"]
    )
    incremental = analyze_account(
        US, trades, checkpoints=checkpoints, actions_by_symbol=actions_by_symbol
    )

    assert incremental["MUU"]["current_qty"] == pytest.approx(full["MUU"]["current_qty"])
    assert incremental["MUU"]["avg_price"] == pytest.approx(full["MUU"]["avg_price"])
    assert incremental["MUU"]["realized_pnl"] == pytest.approx(full["MUU"]["realized_pnl"])


def test_checkpoint_covering_all_trades_needs_no_replay():
    checkpoints = make_checkpoint(TRADES, "2026-12-31")
    result = analyze_account(US, TRADES, checkpoints=checkpoints)
    full = analyze_account(US, TRADES)
    assert result["AAA"]["current_qty"] == pytest.approx(full["AAA"]["current_qty"])
    assert result["AAA"]["realized_pnl"] == pytest.approx(full["AAA"]["realized_pnl"])


def test_stale_checkpoint_is_discarded_when_trade_count_mismatches():
    """第二層防線：即使作廢機制漏掉，筆數對不上就必須整段重算。"""
    checkpoints = make_checkpoint(TRADES, "2026-03-31")
    # 模擬使用者事後補了一筆早期交易，但 checkpoint 沒被作廢
    extra = buy("2026-02-01", 100, 50, trade_id="x")
    trades = [*TRADES, extra]

    state, pending, _ = _resume_point(US, "AAA", trades, [], checkpoints["AAA"])
    assert state.to_dict() == FifoState().to_dict()  # 退回空狀態
    assert len(pending) == len(trades)  # 全部重算

    incremental = analyze_account(US, trades, checkpoints=checkpoints)
    full = analyze_account(US, trades)
    assert incremental["AAA"]["current_qty"] == pytest.approx(full["AAA"]["current_qty"])
    assert incremental["AAA"]["avg_price"] == pytest.approx(full["AAA"]["avg_price"])


def test_undated_trades_are_always_covered_by_checkpoint():
    trades = [
        {**buy("2026-01-10", 10, 100, trade_id="1"), "date": None},
        buy("2026-05-05", 5, 150, trade_id="2"),
    ]
    checkpoints = make_checkpoint(trades, "2026-02-28")
    assert checkpoints["AAA"]["trade_count"] == 1  # 無日期那筆算在 checkpoint 內

    incremental = analyze_account(US, trades, checkpoints=checkpoints)
    full = analyze_account(US, trades)
    assert incremental["AAA"]["current_qty"] == pytest.approx(full["AAA"]["current_qty"])
    assert incremental["AAA"]["total_cost"] == pytest.approx(full["AAA"]["total_cost"])


def test_up_to_truncates_trades():
    result = analyze_account(US, TRADES, up_to="2026-02-28")
    assert result["AAA"]["current_qty"] == 30  # 只到第二筆買入


def test_group_by_ticker_splits_correctly():
    trades = [buy("2026-01-01", 1, 10), dict(buy("2026-01-01", 2, 20), ticker="BBB")]
    grouped = group_by_ticker(trades)
    assert set(grouped) == {"AAA", "BBB"}


def test_summarize_state_zeroes_out_dust():
    state = apply_trades(FifoState(), [buy("2026-01-01", 1, 100), sell("2026-02-01", 1, 100)], US, "AAA")
    assert summarize_state(state)["current_qty"] == 0


# ------------------------------------------------------- 結算觸發條件

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


def iso(delta_hours):
    return (NOW - timedelta(hours=delta_hours)).isoformat()


def test_no_trade_change_means_no_settlement():
    assert should_settle(iso(48), None, now=NOW) is False


def test_first_run_settles_when_trades_exist():
    assert should_settle(None, iso(1), now=NOW) is True


def test_within_interval_is_skipped():
    assert should_settle(iso(3), iso(1), now=NOW) is False


def test_interval_elapsed_but_no_change_since_last_run_is_skipped():
    # 上次結算 13 小時前，最後異動是 20 小時前 → 那次異動已經結算過了
    assert should_settle(iso(13), iso(20), now=NOW) is False


def test_interval_elapsed_with_change_since_last_run_settles():
    assert should_settle(iso(13), iso(5), now=NOW) is True
