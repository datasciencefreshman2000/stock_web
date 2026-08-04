"""買入明細（每筆買單被賣掉多少）的測試。

關鍵不變式：明細加總必須和 calc_fifo 的總數對得起來。
兩份實作若哪天飄開，這裡會先炸。
"""

import pytest

from services.fifo import calc_fifo
from services.lots import build_buy_lot_details

US = "美股"
TW = "台股"


def buy(date, qty, price, fee=0, trade_id=""):
    return {"date": date, "buy_qty": qty, "sell_qty": None, "price": price, "fee": fee, "id": trade_id}


def sell(date, qty, price, fee=0, trade_id=""):
    return {"date": date, "buy_qty": None, "sell_qty": qty, "price": price, "fee": fee, "id": trade_id}


def split(ex_date, ratio):
    return {"action_type": "split", "ex_date": ex_date, "ratio": ratio}


def test_untouched_buy_has_no_sales():
    rows = build_buy_lot_details([buy("2026-01-01", 10, 100, trade_id="a")], US, "AAA")
    assert len(rows) == 1
    assert rows[0]["sold_qty"] == 0
    assert rows[0]["remaining_qty"] == 10
    assert rows[0]["sell_avg_price"] is None
    assert rows[0]["realized_pnl"] == 0


def test_one_buy_split_across_two_sells():
    """一筆買單被拆成多個賣出單 —— 這正是你之前不確定怎麼呈現的情況。"""
    trades = [
        buy("2026-01-01", 10, 100, trade_id="b1"),
        sell("2026-02-01", 4, 150, trade_id="s1"),
        sell("2026-03-01", 3, 200, trade_id="s2"),
    ]
    rows = build_buy_lot_details(trades, US, "AAA")
    assert len(rows) == 1
    row = rows[0]
    assert row["sold_qty"] == 7
    assert row["remaining_qty"] == 3
    # 賣出均價是加權平均：(4*150 + 3*200) / 7
    assert row["sell_avg_price"] == pytest.approx((4 * 150 + 3 * 200) / 7)
    assert row["realized_pnl"] == pytest.approx(4 * 150 + 3 * 200 - 7 * 100)


def test_one_sell_consumes_two_buys_oldest_first():
    trades = [
        buy("2026-01-01", 10, 100, trade_id="b1"),
        buy("2026-02-01", 10, 200, trade_id="b2"),
        sell("2026-03-01", 15, 300, trade_id="s1"),
    ]
    rows = build_buy_lot_details(trades, US, "AAA")
    first, second = rows
    assert (first["sold_qty"], first["remaining_qty"]) == (10, 0)
    assert (second["sold_qty"], second["remaining_qty"]) == (5, 5)
    assert first["sell_avg_price"] == pytest.approx(300)
    assert second["sell_avg_price"] == pytest.approx(300)


def test_totals_match_calc_fifo():
    trades = [
        buy("2026-01-01", 10, 100, trade_id="b1"),
        buy("2026-02-01", 20, 120, trade_id="b2"),
        sell("2026-03-01", 15, 180, trade_id="s1"),
        buy("2026-05-05", 5, 150, trade_id="b3"),
        sell("2026-07-01", 10, 200, trade_id="s2"),
    ]
    rows = build_buy_lot_details(trades, US, "AAA")
    summary = calc_fifo(trades, US, "AAA")

    assert sum(r["remaining_qty"] for r in rows) == pytest.approx(summary["current_qty"])
    assert sum(r["remaining_qty"] * r["price"] for r in rows) == pytest.approx(summary["total_cost"])
    assert sum(r["realized_pnl"] for r in rows) == pytest.approx(summary["realized_pnl"])


def test_totals_match_calc_fifo_for_tw_account_with_fees():
    trades = [
        buy("2026-01-01", 1000, 100, trade_id="b1"),
        sell("2026-02-01", 600, 130, trade_id="s1"),
    ]
    rows = build_buy_lot_details(trades, TW, "2330", is_etf=False)
    summary = calc_fifo(trades, TW, "2330", is_etf=False)

    assert sum(r["remaining_qty"] for r in rows) == pytest.approx(summary["current_qty"])
    # 扣掉手續費與稅之後，逐筆淨損益要等於總已實現損益
    assert sum(r["realized_pnl_net"] for r in rows) == pytest.approx(summary["realized_pnl"])


def test_unmatched_sell_is_offset_by_later_buy():
    trades = [
        buy("2026-01-01", 5, 100, trade_id="b1"),
        sell("2026-02-01", 10, 150, trade_id="s1"),
        buy("2026-03-01", 8, 200, trade_id="b2"),
    ]
    rows = build_buy_lot_details(trades, US, "AAA")
    summary = calc_fifo(trades, US, "AAA")
    # 第二筆買單有 5 股用來補平賣超，只留下 3 股
    assert rows[1]["fifo_qty"] == 3
    assert sum(r["remaining_qty"] for r in rows) == pytest.approx(summary["current_qty"])


# ------------------------------------------------------------ 分割


def test_split_rescales_open_lot_to_current_share_units():
    """這是前端 JS 版本算不出來的：分割後股數與均價要換算。"""
    trades = [buy("2026-01-01", 10, 400, trade_id="b1")]
    rows = build_buy_lot_details(trades, US, "MUU", actions=[split("2026-06-01", 4)])
    row = rows[0]
    assert row["remaining_qty"] == pytest.approx(40)
    assert row["price"] == pytest.approx(100)
    assert row["original_qty"] == pytest.approx(40)
    assert row["split_adjusted"] is True


def test_sell_after_split_matches_adjusted_lot():
    trades = [
        buy("2026-01-01", 10, 400, trade_id="b1"),
        sell("2026-07-01", 40, 150, trade_id="s1"),
    ]
    rows = build_buy_lot_details(trades, US, "MUU", actions=[split("2026-06-01", 4)])
    summary = calc_fifo(trades, US, "MUU", actions=[split("2026-06-01", 4)])

    row = rows[0]
    assert row["sold_qty"] == pytest.approx(40)
    assert row["remaining_qty"] == 0
    assert row["sell_avg_price"] == pytest.approx(150)
    assert row["realized_pnl"] == pytest.approx(summary["realized_pnl"])


def test_split_totals_still_match_calc_fifo():
    actions = [split("2026-04-01", 4)]
    trades = [
        buy("2026-01-01", 10, 400, trade_id="b1"),
        sell("2026-05-01", 20, 120, trade_id="s1"),
        buy("2026-06-01", 10, 130, trade_id="b2"),
    ]
    rows = build_buy_lot_details(trades, US, "MUU", actions=actions)
    summary = calc_fifo(trades, US, "MUU", actions=actions)

    assert sum(r["remaining_qty"] for r in rows) == pytest.approx(summary["current_qty"])
    assert sum(r["remaining_qty"] * r["price"] for r in rows) == pytest.approx(summary["total_cost"])
    assert sum(r["realized_pnl"] for r in rows) == pytest.approx(summary["realized_pnl"])


def test_buy_after_split_is_not_rescaled_again():
    actions = [split("2026-04-01", 4)]
    trades = [
        buy("2026-01-01", 10, 400, trade_id="b1"),
        buy("2026-06-01", 40, 100, trade_id="b2"),
    ]
    rows = build_buy_lot_details(trades, US, "MUU", actions=actions)
    assert rows[0]["remaining_qty"] == pytest.approx(40)
    assert rows[1]["remaining_qty"] == pytest.approx(40)
    assert rows[1]["split_adjusted"] is False


def test_rows_are_in_chronological_order():
    trades = [
        buy("2026-03-01", 1, 10, trade_id="b3"),
        buy("2026-01-01", 1, 10, trade_id="b1"),
        buy("2026-02-01", 1, 10, trade_id="b2"),
    ]
    rows = build_buy_lot_details(trades, US, "AAA")
    assert [r["id"] for r in rows] == ["b1", "b2", "b3"]


def test_sell_only_history_produces_no_rows():
    rows = build_buy_lot_details([sell("2026-01-01", 5, 100, trade_id="s1")], US, "AAA")
    assert rows == []
