"""日線 OHLCV。技術分析與回測的資料基礎。"""

from database import get_supabase

CHUNK_SIZE = 500


def list_price_history(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    query = get_supabase().table("price_history").select("*").eq("symbol", symbol)
    if start_date:
        query = query.gte("date", start_date)
    if end_date:
        query = query.lte("date", end_date)
    query = query.order("date")
    if limit:
        query = query.limit(limit)
    return query.execute().data or []


def latest_history_date(symbol: str) -> str | None:
    response = (
        get_supabase()
        .table("price_history")
        .select("date")
        .eq("symbol", symbol)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0]["date"] if rows else None


def upsert_price_history(rows: list[dict]) -> int:
    if not rows:
        return 0
    written = 0
    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        get_supabase().table("price_history").upsert(chunk, on_conflict="symbol,date").execute()
        written += len(chunk)
    return written
