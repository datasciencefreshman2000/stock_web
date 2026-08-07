from functools import lru_cache

from fastapi import HTTPException
from supabase import Client, create_client

from config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_ready:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.",
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)


# PostgREST（Supabase 的 API 層）預設一次最多回 1000 列，而且**不會報錯**，
# 就是安靜地少給你資料。這造成過一個很難察覺的 bug：
#
#   交易累積到 1000 筆之後，list_trades() 只拿得到前 1000 筆。
#   查詢是 .order("date") 由舊到新，所以被截掉的正是**最新的交易**。
#   「紀錄」頁有帳戶與日期篩選、列數少，看得到新交易；
#   「持倉」與「總覽」讀全表，新交易直接消失 —— 兩邊對不起來。
#
# 任何「可能會成長」的表都要用這個函式分頁讀完。
PAGE_SIZE = 1000


def fetch_all(build_query, page_size: int = PAGE_SIZE) -> list[dict]:
    """分頁把查詢結果全部讀回來。

    build_query 是一個 callable，每次呼叫都要回傳一個「還沒 execute」的查詢，
    因為 PostgREST 的 query builder 不能重複使用。

        rows = fetch_all(lambda: get_supabase().table("trades").select("*").order("date"))
    """
    rows: list[dict] = []
    offset = 0
    while True:
        page = build_query().range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size
