from fastapi import APIRouter, Query

from config import get_settings
from models import TradeCreate, TradeUpdate
from repositories.summary_cache import clear_summary_cache
from repositories.trades import COMBINED_HISTORY_ACCOUNT, create_trade, delete_trade, list_trades, update_trade
from services.constants import TW_ACCOUNTS
from services.fees import calc_tw_fee
from services.prices import fetch_fugle_company_names_batch

router = APIRouter()


def prepare_trade_payload(payload: dict) -> dict:
    qty = payload.get("buy_qty") or payload.get("sell_qty") or 0
    if payload["account"] in TW_ACCOUNTS and not payload.get("fee"):
        payload["fee"] = calc_tw_fee(payload["price"], qty)
    payload["total"] = (
        payload["price"] * qty + payload["fee"]
        if payload.get("buy_qty")
        else payload["price"] * qty - payload["fee"]
    )
    return payload


@router.get("/{account}/ticker/{ticker}")
async def get_ticker_info(account: str, ticker: str) -> dict:
    settings = get_settings()
    normalized = ticker.strip().upper()
    company_name = None
    if account in TW_ACCOUNTS and settings.fugle_ready:
        names = await fetch_fugle_company_names_batch([normalized], settings.fugle_api_key)
        company_name = names.get(normalized)
    return {"ticker": normalized, "company_name": company_name}


@router.get("/{account}")
async def get_trades(
    account: str,
    ticker: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    trades = list_trades(account, ticker, start_date, end_date)
    settings = get_settings()
    if settings.fugle_ready and (account in TW_ACCOUNTS or account == COMBINED_HISTORY_ACCOUNT):
        tickers = sorted(
            {
                str(row.get("ticker", "")).upper()
                for row in trades
                if row.get("ticker") and (account in TW_ACCOUNTS or row.get("account") in TW_ACCOUNTS)
            }
        )
        names = await fetch_fugle_company_names_batch(tickers, settings.fugle_api_key)
        trades = [
            {
                **row,
                "company_name": names.get(str(row.get("ticker", "")).upper())
                if account in TW_ACCOUNTS or row.get("account") in TW_ACCOUNTS
                else row.get("company_name"),
            }
            for row in trades
        ]
    return {"trades": trades}


@router.post("")
def add_trade(trade: TradeCreate) -> dict:
    payload = prepare_trade_payload(trade.model_dump(mode="json"))
    created = create_trade(payload)
    clear_summary_cache()
    return {"success": True, "trade": created}


@router.patch("/{trade_id}")
def patch_trade(trade_id: str, trade: TradeUpdate) -> dict:
    payload = prepare_trade_payload(trade.model_dump(mode="json"))
    updated = update_trade(trade_id, payload)
    clear_summary_cache()
    return {"success": True, "trade": updated}


@router.delete("/{trade_id}")
def remove_trade(trade_id: str) -> dict:
    delete_trade(trade_id)
    clear_summary_cache()
    return {"success": True}
