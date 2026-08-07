from database import fetch_all, get_supabase
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
    def build():
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
        return query.order("date").order("created_at")

    # ⚠ 一定要走 fetch_all。PostgREST 預設只回 1000 列且不報錯，
    #   而排序是由舊到新，被截掉的會是最新的交易 —— FIFO 會少算。
    rows = fetch_all(build)
    for row in rows:
        if row.get("ticker"):
            row["ticker"] = row["ticker"].strip().upper()
        # 帳戶也要去空白。calculate_summary 是用
        #   `if trade.get("account") in trades_by_account` 分組，
        # 名稱多一個空白就對不上，那筆交易會被**靜默丟掉** ——
        # 在「紀錄」看得到，「持倉」與「總覽」卻完全不算它。
        if isinstance(row.get("account"), str):
            row["account"] = row["account"].strip()
    return rows


def list_trade_tickers(account: str) -> list[str]:
    """只讀取代號欄位，供新增交易的 datalist 使用。"""
    accounts = account_filter_values(account)

    def build():
        query = get_supabase().table("trades").select("ticker")
        return (query.in_("account", accounts) if len(accounts) > 1
                else query.eq("account", accounts[0])).order("ticker")

    rows = fetch_all(build)
    return sorted({str(row.get("ticker") or "").strip().upper() for row in rows if row.get("ticker")})


def get_trade(trade_id: str) -> dict | None:
    response = get_supabase().table("trades").select("*").eq("id", trade_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def latest_trade_change_at() -> str | None:
    """最近一次交易異動時間（新增或編輯）。用來決定要不要重新結算 FIFO。"""
    response = (
        get_supabase()
        .table("trades")
        .select("updated_at")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0].get("updated_at") if rows else None


def create_trade(payload: dict) -> dict:
    if payload.get("account"):
        payload["account"] = normalize_account(payload["account"])
    if payload.get("ticker"):
        payload["ticker"] = payload["ticker"].strip().upper()
    response = get_supabase().table("trades").insert(payload).execute()
    return response.data[0] if response.data else payload


def update_trade(trade_id: str, payload: dict) -> dict:
    if payload.get("account"):
        payload["account"] = normalize_account(payload["account"])
    if payload.get("ticker"):
        payload["ticker"] = payload["ticker"].strip().upper()
    response = get_supabase().table("trades").update(payload).eq("id", trade_id).execute()
    return response.data[0] if response.data else {"id": trade_id, **payload}


def delete_trade(trade_id: str) -> None:
    get_supabase().table("trades").delete().eq("id", trade_id).execute()
