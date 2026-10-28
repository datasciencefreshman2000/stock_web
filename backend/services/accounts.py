ACCOUNT_CURRENCY = {
    "台股": "TWD",
    "美股": "USD",
    "爸媽美股": "USD",
}
from services.money import money_sum

ACCOUNTS = ["台股", "美股", "爸媽美股"]
OWN_ACCOUNTS = {"台股", "美股"}
EXTERNAL_ACCOUNTS = {"爸媽美股"}
CASH_ACCOUNT_NAMES = {
    "新光現金",
    "第一現金",
    "郵局現金",
    "國泰現金",
    "外面欠錢 (待收款)",
    "社團欠錢 (待收款)",
    "緊急現金",
    "公司欠錢 (待收款)",
    "信用卡欠錢",
    "身上現金",
    "外面欠錢 (待還款)",
}
BUCKET_ALIASES = {"社團欠錢": "社團欠錢 (待收款)", "公司欠錢": "公司欠錢 (待收款)"}


def account_currency(account: str) -> str:
    return ACCOUNT_CURRENCY.get(account, "TWD")


def to_twd(value: float | int | None, account: str, usd_rate: float) -> float:
    amount = float(value or 0)
    return amount * usd_rate if account_currency(account) == "USD" else amount


def invested_key(account: str) -> str:
    return f"invested_{account}"


def enrich_account_summary(summary: dict, account: str, usd_rate: float, invested: float | int | None = None) -> dict:
    cost = float(summary.get("cost") or 0)
    market_value = summary.get("market_value")
    realized_pnl = float(summary.get("realized_pnl") or 0)
    invested_amount = float(invested if invested is not None else 0)
    invested_twd = to_twd(invested_amount, account, usd_rate)

    summary["market_value_twd"] = to_twd(market_value, account, usd_rate) if market_value is not None else None
    summary["cost_twd"] = to_twd(cost, account, usd_rate)
    summary["unrealized_pnl_twd"] = to_twd(summary.get("unrealized_pnl"), account, usd_rate) if summary.get("unrealized_pnl") is not None else None
    summary["realized_pnl_twd"] = to_twd(realized_pnl, account, usd_rate)
    summary["invested"] = invested_amount
    summary["invested_twd"] = invested_twd
    summary["inferred_cash"] = money_sum([invested_amount, -cost, realized_pnl])
    summary["inferred_cash_twd"] = to_twd(summary["inferred_cash"], account, usd_rate)
    summary["account_total"] = money_sum([market_value, summary["inferred_cash"]]) if market_value is not None else None
    summary["account_total_twd"] = to_twd(summary["account_total"], account, usd_rate) if market_value is not None else None
    summary["cash_warning"] = "帳戶現金為負，請確認期初金額與交易紀錄。" if summary["inferred_cash"] < -0.000001 else None
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
        if currency not in {"TWD", "USD"}:
            raise ValueError(f"不支援的幣別：{currency}")
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
