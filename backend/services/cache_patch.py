"""快取的「就地更新」——避免因為改現金就整個重算。

背景：
    寫入時呼叫 clear_summary_cache() 會把快取刪掉，下一個 GET 必須完整重算，
    約 11 次 DB 往返。但**現金與手動投資的變動不會影響 FIFO**，
    沒有理由重跑那一整套。

作法：
    改現金 / 手動投資時，只重算「便宜的那一半」（現金彙總、投資彙總），
    把結果 patch 回既有的快取。FIFO 相關欄位原封不動沿用。

    真正會動到 FIFO 的只有交易紀錄與除權息事件 —— 那些仍然走刪除路徑。
"""

from repositories.manual import list_cash_accounts, list_manual_investments, list_manual_values
from repositories.summary_cache import (
    SUMMARY_CACHE_KEY,
    get_summary_caches,
    portfolio_cache_key,
    upsert_summary_caches,
)
from services.accounts import (
    ACCOUNTS,
    EXTERNAL_ACCOUNTS,
    OWN_ACCOUNTS,
    cash_summary,
    enrich_account_summary,
    invested_key,
)


def _investment_twd(row: dict, key: str, usd_rate: float) -> float:
    amount = float(row.get(key) or 0)
    return amount * usd_rate if (row.get("currency") or "TWD") == "USD" else amount


def _enrich_investment(row: dict, usd_rate: float) -> dict:
    cost = _investment_twd(row, "cost", usd_rate)
    value = _investment_twd(row, "value", usd_rate)
    cash = _investment_twd(row, "cash_amount", usd_rate)
    total = value + cash
    return {
        **row,
        "currency": row.get("currency") or "TWD",
        "cost_twd": cost,
        "value_twd": value,
        "cash_amount_twd": cash,
        "total_value_twd": total,
        "pnl_twd": total - cost,
    }


def refresh_cash_and_manual_in_cache(scope: str = "cash") -> bool:
    """重算現金／手動投資／已投入金額，patch 進既有快取。

    回傳 True 表示已就地更新；False 表示沒有快取可 patch
    （呼叫端應改為刪除快取，讓下次 GET 完整重算）。

    scope 讓每種寫入只讀真正有變的資料：
      cash       現金帳戶
      investment 手動投資
      invested   各股票帳戶已投入金額
      movement   現金 + 已投入金額
      manual     手動欄位 + 手動投資（相容舊資料）

    ⚠ 快取的讀寫務必保持「批次一次」。先前寫成每把快取各讀各寫，
      光快取就 12 次往返，反而比它要取代的完整重算還貴。
    """
    cash_changed = scope in {"cash", "movement", "all"}
    investments_changed = scope in {"investment", "manual", "all"}
    invested_changed = scope in {"invested", "movement", "manual", "all"}
    needs_portfolios = cash_changed or invested_changed
    keys = [SUMMARY_CACHE_KEY]
    if needs_portfolios:
        keys.extend(portfolio_cache_key(account) for account in ACCOUNTS)
    caches = get_summary_caches(keys)          # ← 一次讀完
    cached = caches.get(SUMMARY_CACHE_KEY)
    if not cached:
        return False

    usd_rate = float(cached.get("usd_rate") or 0) or 31.316

    cash = cached.get("cash") or {"rows": [], "by_account": {}, "twd_equivalent": 0}
    if cash_changed:
        cash_rows = list_cash_accounts()
        cash = cash_summary(cash_rows, usd_rate)
        cash["by_account"] = {a: cash_summary(cash_rows, usd_rate, a) for a in ACCOUNTS}

    cash_by_account = cash.get("by_account") or {}
    external_cash_total = sum(
        float((cash_by_account.get(a) or {}).get("twd_equivalent") or 0)
        for a in EXTERNAL_ACCOUNTS
    )
    own_cash_total = float(cash.get("twd_equivalent") or 0) - external_cash_total

    investments = cached.get("investments") or []
    if investments_changed:
        investments = [_enrich_investment(row, usd_rate) for row in list_manual_investments()]
        investment_total = sum(row["value_twd"] for row in investments)
        investment_cash_total = sum(row["cash_amount_twd"] for row in investments)
    else:
        investment_total = float(cached.get("investment_total") or 0)
        investment_cash_total = float(cached.get("manual_investment_cash_total") or 0)

    invested = dict(cached.get("invested") or {})
    if invested_changed:
        manual_rows = {row["key"]: float(row["value"]) for row in list_manual_values()}
        invested = {a: manual_rows.get(invested_key(a), 0) for a in ACCOUNTS}
        cached["manual"] = {
            key: manual_rows.get(key, value)
            for key, value in (cached.get("manual") or {}).items()
        }

    # FIFO 結果沿用；只有投入金額變更時重算依賴它的推估現金與帳戶總額。
    accounts = {account: dict(row) for account, row in (cached.get("accounts") or {}).items()}
    if invested_changed:
        for account, account_summary in accounts.items():
            if account in ACCOUNTS:
                enrich_account_summary(account_summary, account, usd_rate, invested.get(account))
    own_account_total = sum(
        float(accounts.get(a, {}).get("account_total_twd") or 0) for a in OWN_ACCOUNTS
    )
    external_account_total = sum(
        float(accounts.get(a, {}).get("account_total_twd") or 0) for a in EXTERNAL_ACCOUNTS
    )
    own_total = own_account_total + investment_total + investment_cash_total + own_cash_total

    cached.update({
        "accounts": accounts,
        "cash": cash,
        "investments": investments,
        "investment_total": investment_total,
        "manual_investment_cash_total": investment_cash_total,
        "invested": invested,
        "total_assets": own_total,
        "own_total_assets": own_total,
        "external_total_assets": external_account_total + external_cash_total,
    })
    to_write = {SUMMARY_CACHE_KEY: cached}

    # 各帳戶的持倉頁只有 dashboard.cash 會變
    for account in ACCOUNTS:
        cached_pf = caches.get(portfolio_cache_key(account))
        if cached_pf and isinstance(cached_pf.get("dashboard"), dict):
            dashboard = dict(cached_pf["dashboard"])
            if cash_changed:
                dashboard["cash"] = cash_by_account.get(account) or cash_summary([], usd_rate, account)
            if invested_changed:
                enrich_account_summary(dashboard, account, usd_rate, invested.get(account))
            cached_pf["dashboard"] = dashboard
            to_write[portfolio_cache_key(account)] = cached_pf

    upsert_summary_caches(to_write)            # ← 一次寫完
    return True
