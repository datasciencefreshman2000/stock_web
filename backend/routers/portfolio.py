from datetime import datetime

from fastapi import APIRouter, Query

from config import get_settings
from repositories.manual import list_cash_accounts, list_manual_values
from repositories.trades import list_trades
from services.accounts import cash_summary, enrich_account_summary, invested_key
from services.calculator import build_holdings, summarize_account
from services.constants import TW_ACCOUNTS
from services.prices import fetch_fugle_company_names_batch, fetch_prices_batch, fetch_usd_rate, get_price_status

router = APIRouter()


@router.get("/{account}")
async def get_portfolio(account: str, refresh_prices: bool = Query(default=False)) -> dict:
    trades = list_trades(account)
    base_holdings = await build_holdings(account, trades, {})
    tickers = [holding["ticker"] for holding in base_holdings]
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
    holdings = await build_holdings(account, trades, prices, company_names)
    dashboard = summarize_account(account, trades, holdings)
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
