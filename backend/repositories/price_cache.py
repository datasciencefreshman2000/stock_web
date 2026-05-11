from database import get_supabase


def list_price_cache(symbols: list[str]) -> dict[str, dict]:
    if not symbols:
        return {}
    response = get_supabase().table("price_cache").select("*").in_("symbol", symbols).execute()
    rows = response.data or []
    return {row["symbol"]: row for row in rows}


def upsert_price_cache(row: dict) -> dict:
    response = get_supabase().table("price_cache").upsert(row, on_conflict="symbol").execute()
    return response.data[0] if response.data else row


def upsert_price_cache_rows(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    response = get_supabase().table("price_cache").upsert(rows, on_conflict="symbol").execute()
    return response.data or rows
