"""tickers 主檔：公司名稱、市場別、是否 ETF。

取代原本存在記憶體的 COMPANY_NAME_CACHE（serverless 冷啟動後就消失）
以及硬編在程式裡的 ETF_LIST。
"""

from database import get_supabase


def list_tickers(symbols: list[str] | None = None) -> dict[str, dict]:
    query = get_supabase().table("tickers").select("*")
    if symbols is not None:
        if not symbols:
            return {}
        query = query.in_("symbol", symbols)
    response = query.execute()
    return {row["symbol"]: row for row in (response.data or [])}


def upsert_tickers(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    response = get_supabase().table("tickers").upsert(rows, on_conflict="symbol").execute()
    return response.data or rows


def etf_symbols() -> set[str]:
    response = get_supabase().table("tickers").select("symbol").eq("is_etf", True).execute()
    return {row["symbol"] for row in (response.data or [])}
