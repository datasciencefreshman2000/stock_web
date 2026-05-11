ACCOUNT_CURRENCY = {
    "台股": "TWD",
    "美股": "USD",
    "爸媽美股": "USD",
    "x": "TWD",
}

ACCOUNTS = ["台股", "美股", "爸媽美股", "x"]
OWN_ACCOUNTS = {"台股", "美股"}
EXTERNAL_ACCOUNTS = {"爸媽美股", "x"}


def account_currency(account: str) -> str:
    return ACCOUNT_CURRENCY.get(account, "TWD")


def to_twd(value: float | int | None, account: str, usd_rate: float) -> float:
    amount = float(value or 0)
    return amount * usd_rate if account_currency(account) == "USD" else amount


def invested_key(account: str) -> str:
    return f"invested_{account}"


def enrich_account_summary(summary: dict, account: str, usd_rate: float, invested: float | int | None = None) -> dict:
    cost = float(summary.get("cost") or 0)
    market_value = float(summary.get("market_value") or 0)
    realized_pnl = float(summary.get("realized_pnl") or 0)
    invested_amount = float(invested if invested is not None else cost)
    if invested_amount <= 0 and cost > 0:
        invested_amount = cost
    invested_twd = to_twd(invested_amount, account, usd_rate)

    summary["market_value_twd"] = to_twd(market_value, account, usd_rate)
    summary["cost_twd"] = to_twd(cost, account, usd_rate)
    summary["unrealized_pnl_twd"] = to_twd(summary.get("unrealized_pnl"), account, usd_rate)
    summary["realized_pnl_twd"] = to_twd(realized_pnl, account, usd_rate)
    summary["invested"] = invested_amount
    summary["invested_twd"] = invested_twd
    summary["inferred_cash"] = invested_amount - cost + realized_pnl
    summary["inferred_cash_twd"] = invested_twd - summary["cost_twd"] + summary["realized_pnl_twd"]
    summary["account_total"] = market_value + summary["inferred_cash"]
    summary["account_total_twd"] = summary["market_value_twd"] + summary["inferred_cash_twd"]
    return summary


def cash_summary(rows: list[dict], usd_rate: float, account: str | None = None) -> dict:
    selected = [row for row in rows if account is None or row.get("account") == account]
    twd_total = 0.0
    foreign_total_twd = 0.0
    by_currency: dict[str, float] = {}
    total_twd = 0.0

    for row in selected:
        currency = row.get("currency") or "TWD"
        amount = float(row.get("amount") or 0)
        by_currency[currency] = by_currency.get(currency, 0.0) + amount
        twd_value = amount if currency == "TWD" else amount * usd_rate
        total_twd += twd_value
        if currency == "TWD":
            twd_total += amount
        else:
            foreign_total_twd += twd_value

    return {
        "rows": selected,
        "twd_total": twd_total,
        "foreign_total_twd": foreign_total_twd,
        "twd_equivalent": total_twd,
        "by_currency": by_currency,
    }
