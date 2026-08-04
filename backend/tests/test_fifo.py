"""FIFO 的錢邏輯測試。

這裡的每個案例都對應一種實際會出錯的情境，
包含 20260622 記錄的「均價太低」與 20260722 的「MUU 分割」。
"""

import pytest

from services.fifo import FifoState, apply_trades, calc_fifo

US = "美股"
TW = "台股"


def buy(date, qty, price, fee=0, trade_id=""):
    return {"date": date, "buy_qty": qty, "sell_qty": None, "price": price, "fee": fee, "id": trade_id}


def sell(date, qty, price, fee=0, trade_id=""):
    return {"date": date, "buy_qty": None, "sell_qty": qty, "price": price, "fee": fee, "id": trade_id}


# ---------------------------------------------------------------- 基本行為


def test_single_buy():
    result = calc_fifo([buy("2026-01-01", 10, 100)], US, "AAA")
    assert result["current_qty"] == 10
    assert result["total_cost"] == 1000
    assert result["avg_price"] == 100
    assert result["realized_pnl"] == 0


def test_fifo_uses_oldest_lot_first():
    trades = [
        buy("2026-01-01", 10, 100),
        buy("2026-02-01", 10, 200),
        sell("2026-03-01", 10, 300),
    ]
    result = calc_fifo(trades, US, "AAA")
    # 賣掉的是最早那批（成本 100），剩下的是 200 那批
    assert result["current_qty"] == 10
    assert result["avg_price"] == 200
    assert result["realized_pnl"] == pytest.approx(10 * 300 - 10 * 100)


def test_sell_across_multiple_lots():
    trades = [
        buy("2026-01-01", 10, 100),
        buy("2026-02-01", 10, 200),
        sell("2026-03-01", 15, 300),
    ]
    result = calc_fifo(trades, US, "AAA")
    assert result["current_qty"] == 5
    assert result["avg_price"] == 200
    cost_of_sold = 10 * 100 + 5 * 200
    assert result["realized_pnl"] == pytest.approx(15 * 300 - cost_of_sold)


def test_full_exit_resets_cost_and_qty():
    trades = [buy("2026-01-01", 10, 100), sell("2026-02-01", 10, 150)]
    result = calc_fifo(trades, US, "AAA")
    assert result["current_qty"] == 0
    assert result["total_cost"] == 0
    assert result["avg_price"] == 0


def test_buy_after_full_exit_starts_fresh():
    trades = [
        buy("2026-01-01", 10, 100),
        sell("2026-02-01", 10, 150),
        buy("2026-03-01", 5, 400),
    ]
    result = calc_fifo(trades, US, "AAA")
    assert result["current_qty"] == 5
    assert result["avg_price"] == 400


# ------------------------------------------------- 排序（同日買賣的先後）


def test_same_day_buy_is_processed_before_sell():
    """同一天同時有買和賣時，必須先買再賣，否則會誤判為無券可賣。"""
    trades = [
        sell("2026-01-01", 10, 150),
        buy("2026-01-01", 10, 100),
    ]
    result = calc_fifo(trades, US, "AAA")
    assert result["unmatched_sell_qty"] == 0
    assert result["current_qty"] == 0
    assert result["realized_pnl"] == pytest.approx(500)


# ---------------------------------------------- 賣超（找不到對應買單）


def test_unmatched_sell_is_tracked_not_silently_dropped():
    """紀錄缺漏導致「賣得比買的多」時，要標記出來而不是算出離譜的均價。"""
    trades = [buy("2026-01-01", 5, 100), sell("2026-02-01", 10, 150)]
    result = calc_fifo(trades, US, "AAA")
    assert result["current_qty"] == 0
    assert result["unmatched_sell_qty"] == 5
    assert result["unmatched_sell_value"] == pytest.approx(750)
    # 已實現損益只認有對應成本的那 5 股
    assert result["realized_pnl"] == pytest.approx(5 * 150 - 5 * 100)


def test_later_buy_offsets_unmatched_sell_instead_of_inflating_position():
    """這是 2455 均價異常的成因：賣超之後的買入若直接建倉，均價會被拉歪。"""
    trades = [
        buy("2026-01-01", 5, 100),
        sell("2026-02-01", 10, 150),
        buy("2026-03-01", 8, 200),
    ]
    result = calc_fifo(trades, US, "AAA")
    # 8 股中有 5 股用來補平賣超，只剩 3 股真正建倉
    assert result["current_qty"] == 3
    assert result["avg_price"] == 200


# ------------------------------------------------------------ 台股費用


def test_tw_sell_deducts_fee_and_tax_from_realized_pnl():
    trades = [buy("2026-01-01", 1000, 100), sell("2026-02-01", 1000, 110)]
    result = calc_fifo(trades, TW, "2330", is_etf=False)
    fee_buy = int(100 * 1000 * 0.001425 * 0.6)
    fee_sell = int(110 * 1000 * 0.001425 * 0.6)
    tax = int(110 * 1000 * 0.003)
    assert result["total_fee"] == fee_buy + fee_sell
    assert result["total_tax"] == tax
    assert result["realized_pnl"] == pytest.approx(110000 - fee_sell - tax - 100000)


def test_us_account_uses_recorded_fee():
    trades = [buy("2026-01-01", 10, 100, fee=1), sell("2026-02-01", 10, 150, fee=2)]
    result = calc_fifo(trades, US, "AAA")
    assert result["total_fee"] == 3
    assert result["total_tax"] == 0
    assert result["realized_pnl"] == pytest.approx(1500 - 2 - 1000)


# -------------------------------------------------------- 分割 / 除權息


def split(ex_date, ratio):
    return {"action_type": "split", "ex_date": ex_date, "ratio": ratio}


def test_split_preserves_total_cost_and_multiplies_quantity():
    """MUU 情境：分割前買進，分割後股數變 4 倍、均價變 1/4，總成本不變。"""
    trades = [buy("2026-01-01", 10, 400)]
    result = calc_fifo(trades, US, "MUU", actions=[split("2026-06-01", 4)])
    assert result["current_qty"] == 40
    assert result["avg_price"] == pytest.approx(100)
    assert result["total_cost"] == pytest.approx(4000)


def test_trades_after_split_are_treated_as_post_split_prices():
    trades = [
        buy("2026-01-01", 10, 400),   # 分割前：10 股 @400
        buy("2026-07-01", 40, 100),   # 分割後：40 股 @100
    ]
    result = calc_fifo(trades, US, "MUU", actions=[split("2026-06-01", 4)])
    assert result["current_qty"] == 80
    assert result["total_cost"] == pytest.approx(8000)
    assert result["avg_price"] == pytest.approx(100)


def test_sell_after_split_matches_adjusted_lots():
    trades = [
        buy("2026-01-01", 10, 400),
        sell("2026-07-01", 40, 150),
    ]
    result = calc_fifo(trades, US, "MUU", actions=[split("2026-06-01", 4)])
    assert result["current_qty"] == 0
    assert result["realized_pnl"] == pytest.approx(40 * 150 - 4000)


def test_split_on_same_day_as_trade_applies_before_the_trade():
    trades = [buy("2026-01-01", 10, 400), buy("2026-06-01", 40, 100)]
    result = calc_fifo(trades, US, "MUU", actions=[split("2026-06-01", 4)])
    assert result["current_qty"] == 80
    assert result["avg_price"] == pytest.approx(100)


def test_cash_dividend_accumulates_on_held_quantity():
    trades = [buy("2026-01-01", 100, 50)]
    actions = [{"action_type": "cash_dividend", "ex_date": "2026-06-01", "amount": 2}]
    result = calc_fifo(trades, US, "AAA", actions=actions)
    assert result["dividend_income"] == pytest.approx(200)
    # 配息不影響持股成本
    assert result["total_cost"] == pytest.approx(5000)


def test_dividend_after_selling_out_pays_nothing():
    trades = [buy("2026-01-01", 100, 50), sell("2026-03-01", 100, 60)]
    actions = [{"action_type": "cash_dividend", "ex_date": "2026-06-01", "amount": 2}]
    result = calc_fifo(trades, US, "AAA", actions=actions)
    assert result["dividend_income"] == 0


# ---------------------------------------------------- 空值與極端輸入


def test_trades_without_date_sort_first_and_do_not_crash():
    trades = [
        {"date": None, "buy_qty": 10, "sell_qty": None, "price": 100, "fee": 0, "id": "a"},
        buy("2026-01-01", 10, 200),
    ]
    result = calc_fifo(trades, US, "AAA")
    assert result["current_qty"] == 20
    assert result["total_cost"] == pytest.approx(3000)


def test_empty_trades_returns_zeros():
    result = calc_fifo([], US, "AAA")
    assert result["current_qty"] == 0
    assert result["total_cost"] == 0
    assert result["avg_price"] == 0


def test_fractional_shares_do_not_leave_dust():
    trades = [buy("2026-01-01", 0.3, 100), buy("2026-02-01", 0.7, 100), sell("2026-03-01", 1.0, 120)]
    result = calc_fifo(trades, US, "AAA")
    assert result["current_qty"] == 0
    assert result["total_cost"] == 0


# ------------------------------------------------------- 狀態序列化


def test_state_roundtrip_through_dict_is_lossless():
    trades = [buy("2026-01-01", 10, 100), buy("2026-02-01", 5, 200), sell("2026-03-01", 3, 150)]
    state = apply_trades(FifoState(), trades, US, "AAA")
    restored = FifoState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()
