from database import get_supabase
from services.accounts import ACCOUNTS

X_ACCOUNT_ALIASES = ["x", "X", "x配置(台股)", "X配置(台股)", "x台股", "X台股"]
COMBINED_HISTORY_ACCOUNT = "__combined__"
COMBINED_HISTORY_ACCOUNTS = ACCOUNTS[:3]


def normalize_account(account: str | None) -> str | None:
    if not account:
        return account
    trimmed = account.strip()
    return "x" if trimmed in X_ACCOUNT_ALIASES else trimmed


def account_filter_values(account: str) -> list[str]:
    normalized = normalize_account(account)
    if normalized == COMBINED_HISTORY_ACCOUNT:
        return COMBINED_HISTORY_ACCOUNTS
    return X_ACCOUNT_ALIASES if normalized == "x" else [normalized]


def list_trades(
    account: str | None = None,
    ticker: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = get_supabase().table("trades").select("*")
    if account:
        accounts = account_filter_values(account)
        query = query.in_("account", accounts) if len(accounts) > 1 else query.eq("account", accounts[0])
    if ticker:
        query = query.eq("ticker", ticker.upper())
    if start_date:
        query = query.gte("date", start_date)
    if end_date:
        query = query.lte("date", end_date)
    response = query.order("created_at").execute()
    rows = response.data or []
    for row in rows:
        if row.get("ticker"):
            row["ticker"] = row["ticker"].strip().upper()
    return rows


def create_trade(payload: dict) -> dict:
    if payload.get("account"):
        payload["account"] = normalize_account(payload["account"])
    if payload.get("ticker"):
        payload["ticker"] = payload["ticker"].strip().upper()
    response = get_supabase().table("trades").insert(payload).execute()
    return response.data[0] if response.data else payload


def delete_trade(trade_id: str) -> None:
    get_supabase().table("trades").delete().eq("id", trade_id).execute()
