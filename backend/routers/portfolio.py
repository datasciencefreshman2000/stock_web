import asyncio
from datetime import datetime
from datetime import timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from config import get_settings
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
from services.constants import TW_ACCOUNTS
from services.prices import fetch_fugle_company_names_batch, fetch_prices_batch, fetch_usd_rate, get_price_status

router = APIRouter()
PORTFOLIO_REFRESH_LOCKS: dict[str, asyncio.Lock] = {}
PORTFOLIO_REFRESH_STATE: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def portfolio_refresh_lock(account: str) -> asyncio.Lock:
    if account not in PORTFOLIO_REFRESH_LOCKS:
        PORTFOLIO_REFRESH_LOCKS[account] = asyncio.Lock()
    return PORTFOLIO_REFRESH_LOCKS[account]


def portfolio_refresh_status(account: str) -> dict:
    return dict(
        PORTFOLIO_REFRESH_STATE.get(
            account,
            {
                "in_progress": False,
                "last_started_at": None,
                "last_finished_at": None,
                "last_error": None,
            },
        )
    )


def with_portfolio_refresh_status(account: str, payload: dict | None, queued: bool = False) -> dict:
    result = dict(payload or {})
    result["refresh_queued"] = queued
    result["portfolio_refresh"] = portfolio_refresh_status(account)
    return result


async def calculate_portfolio(account: str, refresh_prices: bool = False) -> dict:
    if account not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown account.")

    trades = list_trades(account)
    fifo_results = analyze_account_trades(account, trades)
    tickers = active_tickers(fifo_results)
    settings = get_settings()
    price_provider_ready = settings.fugle_ready if account in TW_ACCOUNTS else settings.finnhub_ready
    prices = (
        await fetch_prices_batch(
            tickers,
            account,
            settings.finnhub_key,
            refresh=refresh_prices,
            fugle_key=settings.fugle_api_key,
        )
        if price_provider_ready
        else {}
    )
    company_names = (
        await fetch_fugle_company_names_batch(tickers, settings.fugle_api_key)
        if account in TW_ACCOUNTS and settings.fugle_ready
        else {}
    )
    holdings = build_holdings_from_results(fifo_results, prices, company_names)
    dashboard = summarize_account_from_results(fifo_results, holdings)
    usd_rate = await fetch_usd_rate(refresh=False)
    manual_rows = {row["key"]: float(row["value"]) for row in list_manual_values()}
    cash_rows = list_cash_accounts()
    enrich_account_summary(dashboard, account, usd_rate, manual_rows.get(invested_key(account)))
    dashboard["cash"] = cash_summary(cash_rows, usd_rate, account)
    dashboard["updated_at"] = datetime.now().isoformat()
    return {
        "account": account,
        "holdings": holdings,
        "dashboard": dashboard,
        "price_status": get_price_status(),
    }


async def refresh_portfolio_cache(account: str, refresh_prices: bool = True, skip_if_running: bool = False) -> dict | None:
    lock = portfolio_refresh_lock(account)
    if skip_if_running and lock.locked():
        return get_summary_cache(portfolio_cache_key(account))

    async with lock:
        PORTFOLIO_REFRESH_STATE[account] = {
            "in_progress": True,
            "last_started_at": _now_iso(),
            "last_finished_at": None,
            "last_error": None,
        }
        try:
            portfolio = await calculate_portfolio(account, refresh_prices=refresh_prices)
            cached = upsert_summary_cache(portfolio, portfolio_cache_key(account))
            PORTFOLIO_REFRESH_STATE[account]["last_finished_at"] = _now_iso()
            return cached
        except Exception as exc:
            PORTFOLIO_REFRESH_STATE[account]["last_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            PORTFOLIO_REFRESH_STATE[account]["in_progress"] = False


@router.get("/{account}")
async def get_portfolio(
    account: str,
    background_tasks: BackgroundTasks,
    refresh_prices: bool = Query(default=False),
) -> dict:
    if account not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown account.")

    cache_key = portfolio_cache_key(account)
    cached = get_summary_cache(cache_key)
    if refresh_prices and cached:
        queued = False
        lock = portfolio_refresh_lock(account)
        if not lock.locked():
            background_tasks.add_task(refresh_portfolio_cache, account, True, True)
            queued = True
        return with_portfolio_refresh_status(account, cached, queued=queued)

    if cached and not refresh_prices:
        return with_portfolio_refresh_status(account, cached)

    portfolio = await calculate_portfolio(account, refresh_prices=refresh_prices)
    return with_portfolio_refresh_status(account, upsert_summary_cache(portfolio, cache_key))
