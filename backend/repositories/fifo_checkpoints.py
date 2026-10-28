"""FIFO checkpoint：增量結算的儲存層。

每筆 checkpoint 代表「截至 as_of_date 收盤為止」的 FIFO 狀態。
之後只需要套用 date > as_of_date 的交易，不必每次重跑全部歷史。
"""

from database import fetch_all, get_supabase

# 保留策略：月底 checkpoint 永久保留，其餘只留最新幾筆
KEEP_RECENT = 2


def list_latest_checkpoints(account: str, on_or_before: str) -> dict[str, dict]:
    """取得該帳戶每個 ticker 在 on_or_before 之前最新的一筆 checkpoint。

    要分頁：月底 checkpoint 是永久保留的，
    120 個標的 × 每年 12 個月底，一年就一千多列。
    被截斷的話某些標的會拿不到 checkpoint，退回全量重算——
    結果仍然正確，但增量結算就形同失效了。
    """
    def build():
        return (
            get_supabase()
            .table("fifo_checkpoints")
            .select("*")
            .eq("account", account)
            .lte("as_of_date", on_or_before)
            .order("as_of_date", desc=True)
        )

    latest: dict[str, dict] = {}
    for row in fetch_all(build):
        # 已依 as_of_date 由新到舊排序，第一次看到的就是最新
        latest.setdefault(row["ticker"], row)
    return latest


def list_latest_checkpoints_for_accounts(
    accounts: list[str], on_or_before: str
) -> dict[str, dict[str, dict]]:
    """一次取得多個帳戶的最新 checkpoint，避免逐帳戶查詢。"""
    if not accounts:
        return {}

    def build():
        return (
            get_supabase()
            .table("fifo_checkpoints")
            .select("*")
            .in_("account", accounts)
            .lte("as_of_date", on_or_before)
            .order("as_of_date", desc=True)
        )

    latest: dict[str, dict[str, dict]] = {account: {} for account in accounts}
    for row in fetch_all(build):        # 同上，這裡是三個帳戶合計，更容易破千
        account = row.get("account")
        ticker = row.get("ticker")
        if account in latest and ticker:
            latest[account].setdefault(ticker, row)
    return latest


def upsert_checkpoints(rows: list[dict], revision: int) -> list[dict]:
    if not rows:
        return []
    from repositories.summary_cache import CacheRevisionChanged
    if not get_supabase().rpc("write_fifo_checkpoints", {"p_revision": revision, "p_rows": rows}).execute().data:
        raise CacheRevisionChanged("交易在結算期間已更新，稍後重新結算。")
    return rows


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
