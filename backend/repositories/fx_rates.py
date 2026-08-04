"""匯率落地到 DB，serverless 冷啟動後不會遺失。"""

from datetime import datetime, timezone

from database import get_supabase

USD_TWD = "USD/TWD"


def get_fx_rate(pair: str = USD_TWD) -> dict | None:
    response = (
        get_supabase()
        .table("fx_rates")
        .select("*")
        .eq("pair", pair)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def upsert_fx_rate(rate: float, source: str, pair: str = USD_TWD) -> dict:
    row = {
        "pair": pair,
        "rate": rate,
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    response = get_supabase().table("fx_rates").upsert(row, on_conflict="pair").execute()
    return response.data[0] if response.data else row
