from fastapi import APIRouter, Query

from config import get_settings
from repositories.manual import list_cash_accounts, list_manual_values
from repositories.manual import list_manual_investments
from repositories.price_cache import list_price_cache
from repositories.trades import list_trades
from services.accounts import ACCOUNTS, EXTERNAL_ACCOUNTS, OWN_ACCOUNTS, cash_summary, enrich_account_summary, invested_key
from services.calculator import build_holdings, summarize_account
from services.constants import MANUAL_COSTS, TW_ACCOUNTS
from services.prices import fetch_prices_batch, fetch_usd_rate, get_price_status, reset_price_status

router = APIRouter()


@router.get("/summary")
async def get_summary(refresh_prices: bool = Query(default=False)) -> dict:
    settings = get_settings()
    reset_price_status()
    usd_rate = await fetch_usd_rate(settings.finnhub_key, refresh=refresh_prices) if settings.finnhub_ready else 31.316

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

    tickers_by_account = {}
    all_price_symbols = []
    for account in ACCOUNTS:
        base_holdings = await build_holdings(account, trades_by_account[account], {})
        tickers = [holding["ticker"] for holding in base_holdings]
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
        holdings = await build_holdings(account, trades, prices)
        summary = summarize_account(account, trades, holdings)
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
    investments = list_manual_investments()
    investment_total = sum(float(row.get("value") or 0) for row in investments)

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
        "invested": invested,
        "cash": cash,
        "total_assets": own_account_total + investment_total + own_cash_total,
        "own_total_assets": own_account_total + investment_total + own_cash_total,
        "external_total_assets": external_account_total + external_cash_total,
        "price_status": get_price_status(),
    }
