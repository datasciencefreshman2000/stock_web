from dataclasses import dataclass

from services.constants import TW_ACCOUNTS
from services.fees import calc_tw_fee, calc_tw_tax

EPSILON = 1e-7


@dataclass
class BuyLot:
    qty: float
    cost_per_share: float


def trade_sort_key(trade: dict) -> tuple[str, int, str, str]:
    is_sell = float(trade.get("sell_qty") or 0) > 0
    return (
        str(trade.get("date") or ""),
        1 if is_sell else 0,
        str(trade.get("created_at") or ""),
        str(trade.get("id") or ""),
    )


def calc_fifo(trades: list[dict], account: str, ticker: str) -> dict:
    buy_lots: list[BuyLot] = []
    unmatched_sell_balance = 0.0
    unmatched_sell_qty = 0.0
    unmatched_sell_value = 0.0
    total_cost = 0.0
    realized_pnl = 0.0
    total_fee = 0.0
    total_tax = 0.0
    is_tw = account in TW_ACCOUNTS

    for trade in sorted(trades, key=trade_sort_key):
        buy_qty = float(trade.get("buy_qty") or 0)
        sell_qty = float(trade.get("sell_qty") or 0)
        price = float(trade["price"])

        if buy_qty > 0:
            fee = calc_tw_fee(price, buy_qty) if is_tw else float(trade.get("fee") or 0)
            total_fee += fee
            matched_gap_qty = min(buy_qty, unmatched_sell_balance)
            unmatched_sell_balance -= matched_gap_qty
            long_qty = buy_qty - matched_gap_qty
            if long_qty > EPSILON:
                cost = long_qty * price
                buy_lots.append(BuyLot(qty=long_qty, cost_per_share=price))
                total_cost += cost

        if sell_qty > 0:
            fee = calc_tw_fee(price, sell_qty) if is_tw else float(trade.get("fee") or 0)
            tax = calc_tw_tax(price, sell_qty, ticker) if is_tw else 0
            remaining = sell_qty
            matched_qty = 0.0
            cost_of_sold = 0.0

            while remaining > EPSILON and buy_lots:
                lot = buy_lots[0]
                qty = min(lot.qty, remaining)
                cost_of_sold += qty * lot.cost_per_share
                lot.qty -= qty
                remaining -= qty
                matched_qty += qty
                if lot.qty < EPSILON:
                    buy_lots.pop(0)

            total_cost -= cost_of_sold
            if matched_qty > EPSILON:
                matched_ratio = matched_qty / sell_qty
                revenue = price * matched_qty - fee * matched_ratio - tax * matched_ratio
                realized_pnl += revenue - cost_of_sold
            if remaining > EPSILON:
                unmatched_sell_balance += remaining
                unmatched_sell_qty += remaining
                unmatched_sell_value += remaining * price
            total_fee += fee
            total_tax += tax

    current_qty = sum(lot.qty for lot in buy_lots)
    if abs(current_qty) < EPSILON:
        current_qty = 0
        total_cost = 0

    avg_price = total_cost / current_qty if current_qty > 0 else 0
    return {
        "current_qty": current_qty,
        "total_cost": total_cost,
        "avg_price": avg_price,
        "realized_pnl": realized_pnl,
        "total_fee": total_fee,
        "total_tax": total_tax,
        "unmatched_sell_qty": unmatched_sell_qty,
        "unmatched_sell_value": unmatched_sell_value,
    }
