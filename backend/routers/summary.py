import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Query

from config import get_settings
from repositories.manual import list_cash_accounts, list_manual_values
from repositories.manual import list_manual_investments
from repositories.price_cache import list_price_cache
from repositories.summary_cache import get_summary_cache, upsert_summary_cache
from repositories.trades import list_trades
from services.accounts import ACCOUNTS, EXTERNAL_ACCOUNTS, OWN_ACCOUNTS, cash_summary, enrich_account_summary, invested_key
from services.calculator import (
    active_tickers,
    analyze_account_trades,
    build_holdings_from_results,
    summarize_account_from_results,
)
from services.constants import MANUAL_COSTS, TW_ACCOUNTS
from services.prices import fetch_prices_batch, fetch_usd_rate, get_price_status, reset_price_status

router = APIRouter()
SUMMARY_REFRESH_LOCK = asyncio.Lock()
SUMMARY_REFRESH_STATE = {
    "in_progress": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_error": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_summary_refresh_status() -> dict:
    return dict(SUMMARY_REFRESH_STATE)


def with_summary_refresh_status(payload: dict | None, queued: bool = False) -> dict:
    result = dict(payload or {})
    if isinstance(result.get("accounts"), dict):
        result["accounts"] = {
            account: row
            for account, row in result["accounts"].items()
            if account in ACCOUNTS
        }
    if isinstance(result.get("invested"), dict):
        result["invested"] = {
            account: row
            for account, row in result["invested"].items()
            if account in ACCOUNTS
        }
    if isinstance(result.get("cash"), dict) and isinstance(result["cash"].get("by_account"), dict):
        result["cash"] = {
            **result["cash"],
            "by_account": {
                account: row
                for account, row in result["cash"]["by_account"].items()
                if account in ACCOUNTS
            },
        }
    result["refresh_queued"] = queued
    result["summary_refresh"] = get_summary_refresh_status()
    return result


def investment_amount_twd(row: dict, key: str, usd_rate: float) -> float:
    amount = float(row.get(key) or 0)
    currency = row.get("currency") or "TWD"
    return amount * usd_rate if currency == "USD" else amount


def enrich_manual_investment(row: dict, usd_rate: float) -> dict:
    currency = row.get("currency") or "TWD"
    cost_twd = investment_amount_twd(row, "cost", usd_rate)
    value_twd = investment_amount_twd(row, "value", usd_rate)
    cash_amount_twd = investment_amount_twd(row, "cash_amount", usd_rate)
    total_value_twd = value_twd + cash_amount_twd
    return {
        **row,
        "currency": currency,
        "cost_twd": cost_twd,
        "value_twd": value_twd,
        "cash_amount_twd": cash_amount_twd,
        "total_value_twd": total_value_twd,
        "pnl_twd": total_value_twd - cost_twd,
    }


async def calculate_summary(refresh_prices: bool) -> dict:
    settings = get_settings()
    reset_price_status()
    usd_rate = await fetch_usd_rate(refresh=refresh_prices)

    manual_rows = {row["key"]: float(row["value"]) for row in list_manual_values()}
    accounts = {}
    own_account_total = 0.0
    external_account_total = 0.0
    request_price_cache: dict[str, float | None] = {}
    all_trades = list_trades()
    trades_by_account = {account: [] for account in ACCOUNTS}
    for trade in all_trades:
        account = trade.get("account")
        if account in trades_by_account:
            trades_by_account[account].append(trade)

    fifo_by_account = {}
    tickers_by_account = {}
    all_price_symbols = []
    for account in ACCOUNTS:
        fifo_results = analyze_account_trades(account, trades_by_account[account])
        fifo_by_account[account] = fifo_results
        tickers = active_tickers(fifo_results)
        tickers_by_account[account] = tickers
        for ticker in tickers:
            all_price_symbols.append(f"TW:{ticker}" if account in TW_ACCOUNTS else ticker)
    db_price_cache = list_price_cache(sorted(set(all_price_symbols)))

    for account in ACCOUNTS:
        trades = trades_by_account[account]
        tickers = tickers_by_account[account]
        price_provider_ready = settings.fugle_ready if account in TW_ACCOUNTS else settings.finnhub_ready
        prices = (
            await fetch_prices_batch(
                tickers,
                account,
                settings.finnhub_key,
                refresh=refresh_prices,
                reset_state=False,
                fugle_key=settings.fugle_api_key,
                request_cache=request_price_cache,
                db_cache=db_price_cache,
            )
            if price_provider_ready
            else {}
        )
        holdings = build_holdings_from_results(fifo_by_account[account], prices)
        summary = summarize_account_from_results(fifo_by_account[account], holdings)
        enrich_account_summary(summary, account, usd_rate, manual_rows.get(invested_key(account)))
        accounts[account] = summary
        if account in OWN_ACCOUNTS:
            own_account_total += summary["account_total_twd"]
        if account in EXTERNAL_ACCOUNTS:
            external_account_total += summary["account_total_twd"]

    manual = {
        "morgan_cost": manual_rows.get("morgan_cost", MANUAL_COSTS["morgan"]),
        "morgan_value": manual_rows.get("morgan_value", 0),
        "nomura_cost": manual_rows.get("nomura_cost", MANUAL_COSTS["nomura"]),
        "nomura_value": manual_rows.get("nomura_value", 0),
        "crypto_cost": manual_rows.get("crypto_cost", MANUAL_COSTS["crypto"]),
        "crypto_value": manual_rows.get("crypto_value", 0),
    }
    invested = {account: manual_rows.get(invested_key(account), 0) for account in ACCOUNTS}
    investments = [enrich_manual_investment(row, usd_rate) for row in list_manual_investments()]
    investment_total = sum(row["value_twd"] for row in investments)
    manual_investment_cash_total = sum(row["cash_amount_twd"] for row in investments)

    cash_rows = list_cash_accounts()
    cash_by_account = {account: cash_summary(cash_rows, usd_rate, account) for account in ACCOUNTS}
    cash = cash_summary(cash_rows, usd_rate)
    cash["by_account"] = cash_by_account
    own_cash_rows = [row for row in cash_rows if not row.get("account") or row.get("account") in OWN_ACCOUNTS]
    own_cash_total = cash_summary(own_cash_rows, usd_rate)["twd_equivalent"]
    external_cash_total = sum(cash_by_account[account]["twd_equivalent"] for account in EXTERNAL_ACCOUNTS)

    return {
        "usd_rate": usd_rate,
        "accounts": accounts,
        "manual": manual,
        "investments": investments,
        "investment_total": investment_total,
        "manual_investment_cash_total": manual_investment_cash_total,
        "invested": invested,
        "cash": cash,
        "total_assets": own_account_total + investment_total + manual_investment_cash_total + own_cash_total,
        "own_total_assets": own_account_total + investment_total + manual_investment_cash_total + own_cash_total,
        "external_total_assets": external_account_total + external_cash_total,
        "price_status": get_price_status(),
    }


async def refresh_summary_cache(skip_if_running: bool = False) -> dict | None:
    if skip_if_running and SUMMARY_REFRESH_LOCK.locked():
        return get_summary_cache()

    async with SUMMARY_REFRESH_LOCK:
        SUMMARY_REFRESH_STATE.update(
            {
                "in_progress": True,
                "last_started_at": _now_iso(),
                "last_finished_at": None,
                "last_error": None,
            }
        )
        try:
            summary = await calculate_summary(refresh_prices=True)
            cached = upsert_summary_cache(summary)
            SUMMARY_REFRESH_STATE["last_finished_at"] = _now_iso()
            return cached
        except Exception as exc:
            SUMMARY_REFRESH_STATE["last_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            SUMMARY_REFRESH_STATE["in_progress"] = False


@router.get("/summary")
async def get_summary(
    background_tasks: BackgroundTasks,
    refresh_prices: bool = Query(default=False),
) -> dict:
    cached = get_summary_cache()
    if refresh_prices and cached:
        queued = False
        if not SUMMARY_REFRESH_LOCK.locked():
            background_tasks.add_task(refresh_summary_cache, True)
            queued = True
        return with_summary_refresh_status(cached, queued=queued)

    if cached and not refresh_prices:
        return with_summary_refresh_status(cached)

    summary = await calculate_summary(refresh_prices)
    return with_summary_refresh_status(upsert_summary_cache(summary))
