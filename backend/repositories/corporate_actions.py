"""除權息與股票分割。

重要原則：永遠不改寫 trades 的原始紀錄。
交易紀錄是「當時券商對帳單上的事實」，分割調整是衍生計算，
在 FIFO 走訪時間軸時即時套用。這樣才對得回對帳單。
"""

from database import get_supabase


def list_corporate_actions(symbols: list[str] | None = None) -> dict[str, list[dict]]:
    query = get_supabase().table("corporate_actions").select("*")
    if symbols is not None:
        if not symbols:
            return {}
        query = query.in_("symbol", symbols)
    response = query.order("ex_date").execute()

    grouped: dict[str, list[dict]] = {}
    for row in response.data or []:
        grouped.setdefault(row["symbol"], []).append(row)
    return grouped


def create_corporate_action(payload: dict) -> dict:
    response = (
        get_supabase()
        .table("corporate_actions")
        .upsert(payload, on_conflict="symbol,action_type,ex_date")
        .execute()
    )
    return response.data[0] if response.data else payload


def delete_corporate_action(action_id: str) -> None:
    get_supabase().table("corporate_actions").delete().eq("id", action_id).execute()
