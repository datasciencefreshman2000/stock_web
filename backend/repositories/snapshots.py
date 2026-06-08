from datetime import date as Date

from database import get_supabase
from services.accounts import ACCOUNT_CURRENCY, ACCOUNTS


def number_value(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_daily_snapshot_rows(summary: dict, snapshot_date: Date | None = None) -> list[dict]:
    date_value = (snapshot_date or Date.today()).isoformat()
    accounts = summary.get("accounts") or {}
    cash_by_account = (summary.get("cash") or {}).get("by_account") or {}
    rows = []

    for account in ACCOUNTS:
        account_summary = accounts.get(account) or {}
        cash_summary = cash_by_account.get(account) or {}
        market_value_twd = number_value(account_summary.get("market_value_twd"))
        cash_twd = number_value(cash_summary.get("twd_equivalent"))
        account_total_twd = number_value(account_summary.get("account_total_twd"))

        rows.append(
            {
                "snapshot_date": date_value,
                "account": account,
                "currency": ACCOUNT_CURRENCY.get(account, "TWD"),
                "account_total": number_value(account_summary.get("account_total")),
                "account_total_twd": account_total_twd,
                "market_value": number_value(account_summary.get("market_value")),
                "market_value_twd": market_value_twd,
                "cash": number_value(account_summary.get("inferred_cash")),
                "cash_twd": number_value(account_summary.get("inferred_cash_twd")),
                "invested": number_value(account_summary.get("invested")),
                "invested_twd": number_value(account_summary.get("invested_twd")),
                "realized_pnl": number_value(account_summary.get("realized_pnl")),
                "realized_pnl_twd": number_value(account_summary.get("realized_pnl_twd")),
                "unrealized_pnl": number_value(account_summary.get("unrealized_pnl")),
                "unrealized_pnl_twd": number_value(account_summary.get("unrealized_pnl_twd")),
                "allocation": {
                    "stocks_twd": market_value_twd,
                    "cash_twd": cash_twd,
                    "stock_weight": market_value_twd / account_total_twd if account_total_twd > 0 else None,
                    "cash_weight": cash_twd / account_total_twd if account_total_twd > 0 else None,
                    "cash_by_currency": cash_summary.get("by_currency") or {},
                },
                "payload": account_summary,
            }
        )

    total_invested = sum(number_value(value) for value in (summary.get("invested") or {}).values())
    cash_total = number_value((summary.get("cash") or {}).get("twd_equivalent"))
    rows.append(
        {
            "snapshot_date": date_value,
            "account": "__overall__",
            "currency": "TWD",
            "account_total": number_value(summary.get("total_assets")),
            "account_total_twd": number_value(summary.get("total_assets")),
            "market_value": number_value(summary.get("own_total_assets")),
            "market_value_twd": number_value(summary.get("own_total_assets")),
            "cash": cash_total,
            "cash_twd": cash_total,
            "invested": total_invested,
            "invested_twd": total_invested,
            "realized_pnl": 0,
            "realized_pnl_twd": 0,
            "unrealized_pnl": 0,
            "unrealized_pnl_twd": 0,
            "allocation": {
                "total_assets": number_value(summary.get("total_assets")),
                "own_total_assets": number_value(summary.get("own_total_assets")),
                "external_total_assets": number_value(summary.get("external_total_assets")),
                "investment_total": number_value(summary.get("investment_total")),
                "manual_investment_cash_total": number_value(summary.get("manual_investment_cash_total")),
                "cash_total_twd": cash_total,
                "usd_rate": number_value(summary.get("usd_rate")),
            },
            "payload": summary,
        }
    )
    return rows


def upsert_daily_snapshots(summary: dict, snapshot_date: Date | None = None) -> list[dict]:
    rows = build_daily_snapshot_rows(summary, snapshot_date)
    response = (
        get_supabase()
        .table("account_daily_snapshots")
        .upsert(rows, on_conflict="snapshot_date,account")
        .execute()
    )
    return response.data or rows
