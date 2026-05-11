from collections import defaultdict

from services.fifo import calc_fifo


async def build_holdings(account: str, trades: list[dict], prices: dict[str, float | None]) -> list[dict]:
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        by_ticker[trade["ticker"]].append(trade)

    holdings = []
    total_market_value = 0.0

    for ticker, ticker_trades in by_ticker.items():
        result = calc_fifo(ticker_trades, account, ticker)
        if result["current_qty"] <= 0:
            continue

        price = prices.get(ticker)
        market_value = price * result["current_qty"] if price else None
        if market_value:
            total_market_value += market_value

        pnl = market_value - result["total_cost"] if market_value is not None else None
        pnl_pct = pnl / result["total_cost"] if pnl is not None and result["total_cost"] > 0 else None

        holdings.append(
            {
                "ticker": ticker,
                "qty": result["current_qty"],
                "avg_price": result["avg_price"],
                "current_price": price,
                "cost": result["total_cost"],
                "market_value": market_value,
                "realized_pnl": result["realized_pnl"],
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "weight": None,
            }
        )

    for holding in holdings:
        market_value = holding.get("market_value")
        holding["weight"] = market_value / total_market_value if market_value and total_market_value > 0 else None

    holdings.sort(key=lambda item: item.get("market_value") or 0, reverse=True)
    return holdings


def summarize_account(account: str, trades: list[dict], holdings: list[dict]) -> dict:
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        by_ticker[trade["ticker"]].append(trade)

    realized_pnl = 0.0
    total_fee = 0.0
    total_tax = 0.0
    for ticker, ticker_trades in by_ticker.items():
        result = calc_fifo(ticker_trades, account, ticker)
        realized_pnl += result["realized_pnl"]
        total_fee += result["total_fee"]
        total_tax += result["total_tax"]

    cost = sum(item.get("cost") or 0 for item in holdings)
    market_value = sum(item.get("market_value") or 0 for item in holdings)
    return {
        "cost": cost,
        "market_value": market_value,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": market_value - cost,
        "total_fee": total_fee,
        "total_tax": total_tax,
    }
