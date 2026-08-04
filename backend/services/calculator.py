from repositories.fifo_checkpoints import list_latest_checkpoints
from services.settlement import analyze_account, checkpoint_boundary, group_by_ticker, load_reference_data
from services.symbols import symbol_for


def analyze_account_trades(
    account: str,
    trades: list[dict],
    use_checkpoints: bool = True,
) -> dict[str, dict]:
    """該帳戶每個 ticker 的 FIFO 結果。

    use_checkpoints=False 時強制全量重算（測試與對帳用）。
    """
    tickers = sorted(group_by_ticker(trades).keys())
    if not tickers:
        return {}

    if not use_checkpoints:
        return analyze_account(account, trades)

    actions_by_symbol, etf_symbols = load_reference_data(account, tickers)
    checkpoints = list_latest_checkpoints(account, checkpoint_boundary())
    return analyze_account(
        account,
        trades,
        checkpoints=checkpoints,
        actions_by_symbol=actions_by_symbol,
        etf_symbols=etf_symbols,
    )


def active_tickers(fifo_results: dict[str, dict]) -> list[str]:
    return [ticker for ticker, result in fifo_results.items() if result["current_qty"] > 0]


def build_holdings_from_results(
    fifo_results: dict[str, dict],
    prices: dict[str, float | None],
    company_names: dict[str, str | None] | None = None,
) -> list[dict]:
    holdings = []
    total_market_value = 0.0

    for ticker, result in fifo_results.items():
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
                "company_name": (company_names or {}).get(ticker),
                "qty": result["current_qty"],
                "avg_price": result["avg_price"],
                "current_price": price,
                "cost": result["total_cost"],
                "market_value": market_value,
                "realized_pnl": result["realized_pnl"],
                "dividend_income": result.get("dividend_income", 0),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "weight": None,
                "unmatched_sell_qty": result.get("unmatched_sell_qty", 0),
                "unmatched_sell_value": result.get("unmatched_sell_value", 0),
            }
        )

    for holding in holdings:
        market_value = holding.get("market_value")
        holding["weight"] = market_value / total_market_value if market_value and total_market_value > 0 else None

    holdings.sort(key=lambda item: item.get("market_value") or 0, reverse=True)
    return holdings


async def build_holdings(
    account: str,
    trades: list[dict],
    prices: dict[str, float | None],
    company_names: dict[str, str | None] | None = None,
) -> list[dict]:
    return build_holdings_from_results(
        analyze_account_trades(account, trades),
        prices,
        company_names,
    )


def summarize_account_from_results(fifo_results: dict[str, dict], holdings: list[dict]) -> dict:
    realized_pnl = 0.0
    total_fee = 0.0
    total_tax = 0.0
    dividend_income = 0.0
    for result in fifo_results.values():
        realized_pnl += result["realized_pnl"]
        total_fee += result["total_fee"]
        total_tax += result["total_tax"]
        dividend_income += result.get("dividend_income", 0)

    cost = sum(item.get("cost") or 0 for item in holdings)
    market_value = sum(item.get("market_value") or 0 for item in holdings)
    return {
        "cost": cost,
        "market_value": market_value,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": market_value - cost,
        "total_fee": total_fee,
        "total_tax": total_tax,
        "dividend_income": dividend_income,
    }


def summarize_account(account: str, trades: list[dict], holdings: list[dict]) -> dict:
    return summarize_account_from_results(analyze_account_trades(account, trades), holdings)


def portfolio_symbols(account: str, tickers: list[str]) -> list[str]:
    return [symbol_for(account, ticker) for ticker in tickers]
