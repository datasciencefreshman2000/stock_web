"""單一帳戶持倉。GET 只讀快取，刷新交給 /api/jobs/refresh（見 A3）。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from dependencies import require_auth
from repositories.manual import list_cash_accounts, list_manual_values
from repositories.summary_cache import get_summary_cache, portfolio_cache_key, upsert_summary_cache
from repositories.trades import list_trades
from services.accounts import ACCOUNTS, cash_summary, enrich_account_summary, invested_key
from services.calculator import (
    active_tickers,
    analyze_account_trades,
    build_holdings_from_results,
    summarize_account_from_results,
)
from services.lots import build_buy_lot_details
from services.prices import (
    PriceContext,
    fetch_prices_batch,
    fetch_usd_rate,
    get_price_status,
    resolve_company_names,
)
from services.settlement import load_reference_data
from services.symbols import is_tw_account, symbol_for

router = APIRouter()


async def calculate_portfolio(account: str, refresh_prices: bool = False) -> dict:
    if account not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown account.")

    settings = get_settings()
    context = PriceContext()

    trades = list_trades(account)
    fifo_results = analyze_account_trades(account, trades)
    tickers = active_tickers(fifo_results)

    provider_ready = settings.fugle_ready if is_tw_account(account) else settings.finnhub_ready
    prices = (
        await fetch_prices_batch(
            tickers,
            account,
            settings.finnhub_key,
            refresh=refresh_prices,
            fugle_key=settings.fugle_api_key,
            context=context,
        )
        if provider_ready
        else {}
    )
    company_names = await resolve_company_names(account, tickers, settings.fugle_api_key)

    holdings = build_holdings_from_results(fifo_results, prices, company_names)
    dashboard = summarize_account_from_results(fifo_results, holdings)

    usd_rate = await fetch_usd_rate(refresh=False, context=context)
    manual_rows = {row["key"]: float(row["value"]) for row in list_manual_values()}
    enrich_account_summary(dashboard, account, usd_rate, manual_rows.get(invested_key(account)))
    dashboard["cash"] = cash_summary(list_cash_accounts(), usd_rate, account)
    dashboard["updated_at"] = datetime.now(timezone.utc).isoformat()

    return {
        "account": account,
        "holdings": holdings,
        "dashboard": dashboard,
        "price_status": get_price_status(context),
    }


async def portfolio_from_working_set(
    account: str, working: dict, company_names: dict[str, str | None] | None = None
) -> dict:
    """用 calculate_summary 已經算好的東西組出持倉頁，不再重跑 FIFO。

    summary 與 portfolio 對同一個帳戶算的是同一份 FIFO 結果，
    差別只在 portfolio 多了公司名稱、少了跨帳戶彙總。
    """
    settings = get_settings()
    part = working["by_account"][account]
    usd_rate = working["usd_rate"]

    if company_names is None:
        company_names = await resolve_company_names(account, part["tickers"], settings.fugle_api_key)
    holdings = build_holdings_from_results(part["fifo"], part["prices"], company_names)
    dashboard = summarize_account_from_results(part["fifo"], holdings)
    enrich_account_summary(
        dashboard, account, usd_rate, working["manual_rows"].get(invested_key(account))
    )
    dashboard["cash"] = cash_summary(working["cash_rows"], usd_rate, account)
    dashboard["updated_at"] = datetime.now(timezone.utc).isoformat()

    return {
        "account": account,
        "holdings": holdings,
        "dashboard": dashboard,
        "price_status": get_price_status(working.get("context")),
    }


async def refresh_portfolio_cache(
    account: str, refresh_prices: bool = True, working: dict | None = None
) -> dict:
    portfolio = (
        await portfolio_from_working_set(account, working)
        if working and account in working.get("by_account", {})
        else await calculate_portfolio(account, refresh_prices=refresh_prices)
    )
    return upsert_summary_cache(portfolio, portfolio_cache_key(account))


@router.get("/{account}/lots/{ticker}")
def get_buy_lots(account: str, ticker: str, _: dict = Depends(require_auth)) -> dict:
    """單一標的的買入明細：每筆買單被賣掉多少、剩多少、賣出均價。

    這份計算以前在前端用 JS 重寫一份，會和後端的 FIFO 不同步，
    也不知道股票分割的存在。現在統一由後端算。
    """
    if account not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown account.")

    normalized = ticker.strip().upper()
    trades = list_trades(account, normalized)
    actions_by_symbol, etf_symbols = load_reference_data(account, [normalized])
    symbol = symbol_for(account, normalized)

    rows = build_buy_lot_details(
        trades,
        account,
        normalized,
        actions=actions_by_symbol.get(symbol, []),
        is_etf=symbol in etf_symbols if etf_symbols else None,
    )
    return {
        "account": account,
        "ticker": normalized,
        "symbol": symbol,
        "trades": rows,
        "corporate_actions": actions_by_symbol.get(symbol, []),
    }


@router.get("/{account}")
async def get_portfolio(account: str, _: dict = Depends(require_auth)) -> dict:
    if account not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown account.")

    cached = get_summary_cache(portfolio_cache_key(account))
    if cached:
        return cached

    # 同 get_summary：快取空了就把四把一起建好，不要每頁各算一次 FIFO
    from routers.jobs import rebuild_all_caches

    result = await rebuild_all_caches(refresh_prices=False)
    return result["portfolios"].get(account) or await refresh_portfolio_cache(
        account, refresh_prices=False
    )
