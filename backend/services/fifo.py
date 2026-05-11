from dataclasses import dataclass

from services.constants import TW_ACCOUNTS
from services.fees import calc_tw_fee, calc_tw_tax

EPSILON = 1e-7


@dataclass
class BuyLot:
    qty: float
    cost_per_share: float


def calc_fifo(trades: list[dict], account: str, ticker: str) -> dict:
    buy_lots: list[BuyLot] = []
    current_qty = 0.0
    total_cost = 0.0
    realized_pnl = 0.0
    total_fee = 0.0
    total_tax = 0.0
    is_tw = account in TW_ACCOUNTS

    for trade in trades:
        buy_qty = trade.get("buy_qty") or 0
        sell_qty = trade.get("sell_qty") or 0
        price = float(trade["price"])

        if buy_qty > 0:
            fee = calc_tw_fee(price, buy_qty) if is_tw else float(trade.get("fee") or 0)
            cost = float(buy_qty) * price
            buy_lots.append(BuyLot(qty=float(buy_qty), cost_per_share=cost / float(buy_qty)))
            current_qty += float(buy_qty)
            total_cost += cost
            total_fee += fee

        if sell_qty > 0:
            fee = calc_tw_fee(price, sell_qty) if is_tw else float(trade.get("fee") or 0)
            tax = calc_tw_tax(price, sell_qty, ticker) if is_tw else 0
            revenue = price * float(sell_qty) - fee - tax
            remaining = float(sell_qty)
            cost_of_sold = 0.0

            while remaining > EPSILON and buy_lots:
                lot = buy_lots[0]
                qty = min(lot.qty, remaining)
                cost_of_sold += qty * lot.cost_per_share
                lot.qty -= qty
                remaining -= qty
                if lot.qty < EPSILON:
                    buy_lots.pop(0)

            current_qty -= float(sell_qty)
            total_cost -= cost_of_sold
            realized_pnl += revenue - cost_of_sold
            total_fee += fee
            total_tax += tax

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
    }
