"""每筆買單的 FIFO 明細。

原本這段邏輯是在前端 HoldingsTable.jsx 用 JS 重寫一份（buildBuyLotDetails），
和後端的 Python FIFO 各寫各的，而且完全不知道股票分割的存在。
搬到後端之後只有一份實作，分割也能正確處理。

回傳的欄位刻意對齊前端原本的用法（original_qty / sold_qty / remaining_qty /
sell_value），畫面不需要跟著改。
"""

from services.fifo import EPSILON, SPLIT_ACTIONS, action_sort_key, trade_sort_key
from services.constants import ETF_LIST, TW_ACCOUNTS
from services.fees import calc_tw_fee, calc_tw_tax


def _new_row(trade: dict, qty: float, price: float) -> dict:
    return {
        "id": trade.get("id"),
        "date": trade.get("date"),
        "note": trade.get("note") or "",
        "price": price,
        "original_qty": float(trade.get("buy_qty") or 0),
        "fifo_qty": qty,
        "sold_qty": 0.0,
        "remaining_qty": qty,
        "sell_value": 0.0,
        "sell_fee": 0.0,
        "sell_tax": 0.0,
        "split_adjusted": False,
    }


def build_buy_lot_details(
    trades: list[dict],
    account: str,
    ticker: str,
    actions: list[dict] | None = None,
    is_etf: bool | None = None,
) -> list[dict]:
    """走訪時間軸，記錄每筆買單被哪些賣單消化掉。

    分割發生時，未賣完的部位股數會等比放大、成本等比縮小，
    已賣出的金額（sell_value）是錢，不受分割影響。
    """
    is_tw = account in TW_ACCOUNTS
    etf = (ticker in ETF_LIST) if is_etf is None else is_etf

    rows: list[dict] = []
    lots: list[dict] = []  # [{row, remaining_qty}]
    unmatched_sell_balance = 0.0

    pending_actions = sorted(actions or [], key=action_sort_key)
    action_index = 0

    def apply_split(ratio: float) -> None:
        nonlocal unmatched_sell_balance
        if ratio <= 0:
            return
        for lot in lots:
            lot["remaining_qty"] *= ratio
        # 已開立的買單列：換算成分割後的股數單位
        for row in rows:
            if row["remaining_qty"] > EPSILON or row["sold_qty"] > EPSILON:
                row["split_adjusted"] = True
            row["fifo_qty"] *= ratio
            row["remaining_qty"] *= ratio
            row["sold_qty"] *= ratio
            row["original_qty"] *= ratio
            row["price"] /= ratio
        unmatched_sell_balance *= ratio

    def flush_actions(until: str) -> None:
        nonlocal action_index
        while action_index < len(pending_actions):
            action = pending_actions[action_index]
            ex_date = str(action.get("ex_date") or "")
            if not ex_date or (until and ex_date > until):
                break
            if action.get("action_type") in SPLIT_ACTIONS and action.get("ratio"):
                apply_split(float(action["ratio"]))
            action_index += 1

    for trade in sorted(trades, key=trade_sort_key):
        trade_date = str(trade.get("date") or "")
        if trade_date:
            flush_actions(trade_date)

        buy_qty = float(trade.get("buy_qty") or 0)
        sell_qty = float(trade.get("sell_qty") or 0)
        price = float(trade["price"])

        if buy_qty > 0:
            matched_gap_qty = min(buy_qty, unmatched_sell_balance)
            unmatched_sell_balance -= matched_gap_qty
            long_qty = buy_qty - matched_gap_qty
            row = _new_row(trade, long_qty, price)
            rows.append(row)
            if long_qty > EPSILON:
                lots.append({"row": row, "remaining_qty": long_qty})

        if sell_qty > 0:
            fee = calc_tw_fee(price, sell_qty) if is_tw else float(trade.get("fee") or 0)
            tax = calc_tw_tax(price, sell_qty, ticker, is_etf=etf) if is_tw else 0.0

            remaining = sell_qty
            while remaining > EPSILON and lots:
                lot = lots[0]
                qty = min(lot["remaining_qty"], remaining)
                share = qty / sell_qty
                row = lot["row"]
                row["sold_qty"] += qty
                row["remaining_qty"] -= qty
                row["sell_value"] += qty * price
                row["sell_fee"] += fee * share
                row["sell_tax"] += tax * share
                lot["remaining_qty"] -= qty
                remaining -= qty
                if lot["remaining_qty"] <= EPSILON:
                    lots.pop(0)

            if remaining > EPSILON:
                unmatched_sell_balance += remaining

    flush_actions("9999-12-31")

    for row in rows:
        sold = row["sold_qty"]
        row["sell_avg_price"] = row["sell_value"] / sold if sold > EPSILON else None
        row["realized_pnl"] = (row["sell_value"] - sold * row["price"]) if sold > EPSILON else 0.0
        # 扣掉手續費與稅之後的淨已實現損益（前端目前顯示的是未扣費版本）
        row["realized_pnl_net"] = row["realized_pnl"] - row["sell_fee"] - row["sell_tax"]
        if row["remaining_qty"] < EPSILON:
            row["remaining_qty"] = 0.0

    return rows
