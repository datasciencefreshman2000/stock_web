from database import get_supabase


def list_trades(
    account: str | None = None,
    ticker: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = get_supabase().table("trades").select("*")
    if account:
        query = query.eq("account", account)
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
    if payload.get("ticker"):
        payload["ticker"] = payload["ticker"].strip().upper()
    response = get_supabase().table("trades").insert(payload).execute()
    return response.data[0] if response.data else payload


def delete_trade(trade_id: str) -> None:
    get_supabase().table("trades").delete().eq("id", trade_id).execute()
