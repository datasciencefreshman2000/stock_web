"""FIFO checkpoint：增量結算的儲存層。

每筆 checkpoint 代表「截至 as_of_date 收盤為止」的 FIFO 狀態。
之後只需要套用 date > as_of_date 的交易，不必每次重跑全部歷史。
"""

from database import get_supabase

# 保留策略：月底 checkpoint 永久保留，其餘只留最新幾筆
KEEP_RECENT = 2


def list_latest_checkpoints(account: str, on_or_before: str) -> dict[str, dict]:
    """取得該帳戶每個 ticker 在 on_or_before 之前最新的一筆 checkpoint。"""
    response = (
        get_supabase()
        .table("fifo_checkpoints")
        .select("*")
        .eq("account", account)
        .lte("as_of_date", on_or_before)
        .order("as_of_date", desc=True)
        .execute()
    )
    latest: dict[str, dict] = {}
    for row in response.data or []:
        # 已依 as_of_date 由新到舊排序，第一次看到的就是最新
        latest.setdefault(row["ticker"], row)
    return latest


def upsert_checkpoints(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    response = (
        get_supabase()
        .table("fifo_checkpoints")
        .upsert(rows, on_conflict="account,ticker,as_of_date")
        .execute()
    )
    return response.data or rows


def invalidate_from(account: str, ticker: str, from_date: str) -> None:
    """作廢受影響的 checkpoint。

    當某筆交易被新增／修改／刪除時，所有涵蓋該日期的 checkpoint 都不再正確，
    必須刪掉，讓下次計算自動退回更早的 checkpoint（或從頭算）。
    """
    (
        get_supabase()
        .table("fifo_checkpoints")
        .delete()
        .eq("account", account)
        .eq("ticker", ticker)
        .gte("as_of_date", from_date)
        .execute()
    )


def clear_checkpoints(account: str | None = None) -> None:
    query = get_supabase().table("fifo_checkpoints").delete()
    if account:
        query = query.eq("account", account)
    else:
        query = query.neq("account", "__never__")
    query.execute()


def prune_checkpoints(account: str, ticker: str) -> None:
    """控制 checkpoint 數量：月底的保留，其餘只留最新 KEEP_RECENT 筆。"""
    response = (
        get_supabase()
        .table("fifo_checkpoints")
        .select("as_of_date")
        .eq("account", account)
        .eq("ticker", ticker)
        .order("as_of_date", desc=True)
        .execute()
    )
    dates = [row["as_of_date"] for row in (response.data or [])]
    if len(dates) <= KEEP_RECENT:
        return

    from datetime import date as Date

    def is_month_end(value: str) -> bool:
        parsed = Date.fromisoformat(value)
        next_day = parsed.toordinal() + 1
        return Date.fromordinal(next_day).month != parsed.month

    droppable = [d for d in dates[KEEP_RECENT:] if not is_month_end(d)]
    if not droppable:
        return

    (
        get_supabase()
        .table("fifo_checkpoints")
        .delete()
        .eq("account", account)
        .eq("ticker", ticker)
        .in_("as_of_date", droppable)
        .execute()
    )
