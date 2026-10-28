from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date as Date

from config import get_settings
from dependencies import require_auth
from models import TradeCreate, TradeUpdate
from repositories.operations import atomic_write
from repositories.summary_cache import clear_summary_cache
from repositories.tickers import list_tickers
from repositories.trades import (
    COMBINED_HISTORY_ACCOUNT,
    create_trade,
    delete_trade,
    get_trade,
    list_trade_tickers,
    list_trades,
    update_trade,
    list_trade_page,
)
from services.constants import TW_ACCOUNTS
from services.fees import calc_tw_fee, calc_tw_tax
from services.prices import resolve_company_names
from services.settlement import invalidate_for_trade
from services.symbols import symbol_for

router = APIRouter()


def prepare_trade_payload(payload: dict, is_etf: bool | None = None) -> dict:
    payload["fee"] = payload.get("fee") if payload.get("fee") is not None else (None if payload["account"] in TW_ACCOUNTS else 0)
    qty = payload.get("buy_qty") or payload.get("sell_qty") or 0
    is_tw = payload["account"] in TW_ACCOUNTS
    if is_tw and not payload.get("fee"):
        payload["fee"] = calc_tw_fee(payload["price"], qty)
    tax = calc_tw_tax(payload["price"], qty, payload["ticker"], is_etf=is_etf) if is_tw and payload.get("sell_qty") else 0
    payload["total"] = (
        payload["price"] * qty + payload["fee"]
        if payload.get("buy_qty")
        else payload["price"] * qty - payload["fee"] - tax
    )
    return payload


def after_trade_change(*trades: dict | None) -> None:
    """交易異動後：作廢受影響的 FIFO checkpoint，並清掉彙總快取。

    checkpoint 作廢一定要做，否則下次計算會從一個已經不正確的狀態續算。
    """
    for trade in trades:
        invalidate_for_trade(trade)
    clear_summary_cache()


@router.get("/{account}/ticker/{ticker}")
async def get_ticker_info(account: str, ticker: str, _: dict = Depends(require_auth)) -> dict:
    settings = get_settings()
    normalized = ticker.strip().upper()
    names = await resolve_company_names(account, [normalized], settings.fugle_api_key)
    return {"ticker": normalized, "company_name": names.get(normalized)}


@router.get("/{account}/tickers")
def get_trade_tickers(account: str, _: dict = Depends(require_auth)) -> dict:
    return {"account": account, "tickers": list_trade_tickers(account)}


@router.get("/{account}")
async def get_trades(
    account: str,
    ticker: str | None = Query(default=None),
    start_date: Date | None = Query(default=None),
    end_date: Date | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=1000),
    limit: int = Query(default=100, ge=1, le=200),
    _: dict = Depends(require_auth),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "起日不能晚於迄日。")
    trades, next_cursor = list_trade_page(account, ticker, start_date.isoformat() if start_date else None, end_date.isoformat() if end_date else None, cursor, limit)
    if not trades:
        return {"trades": [], "account": account, "next_cursor": None}

    # 公司名稱直接從 tickers 主檔讀，不再每次打 Fugle
    tw_symbols = sorted(
        {
            symbol_for(row["account"], str(row.get("ticker", "")))
            for row in trades
            if row.get("ticker") and row.get("account") in TW_ACCOUNTS
        }
    )
    known = list_tickers(tw_symbols) if tw_symbols else {}

    enriched = []
    for row in trades:
        name = row.get("company_name")
        if row.get("account") in TW_ACCOUNTS:
            symbol = symbol_for(row["account"], str(row.get("ticker", "")))
            name = (known.get(symbol) or {}).get("name") or name
        enriched.append({**row, "company_name": name})

    return {"trades": enriched, "account": account, "combined": account == COMBINED_HISTORY_ACCOUNT, "next_cursor": next_cursor}


@router.post("")
def add_trade(trade: TradeCreate, _: dict = Depends(require_auth)) -> dict:
    known = list_tickers([symbol_for(trade.account, trade.ticker)]) if trade.account in TW_ACCOUNTS else {}
    metadata = known.get(symbol_for(trade.account, trade.ticker)) or {}
    payload = prepare_trade_payload(trade.model_dump(mode="json"), metadata.get("is_etf"))
    created = atomic_write("trade.create", payload)
    return {"success": True, "trade": created}


@router.patch("/{trade_id}")
def patch_trade(trade_id: str, trade: TradeUpdate, _: dict = Depends(require_auth)) -> dict:
    known = list_tickers([symbol_for(trade.account, trade.ticker)]) if trade.account in TW_ACCOUNTS else {}
    payload = prepare_trade_payload(trade.model_dump(mode="json"), (known.get(symbol_for(trade.account, trade.ticker)) or {}).get("is_etf"))
    updated = atomic_write("trade.update", payload, record_id=trade_id)
    return {"success": True, "trade": updated}


@router.delete("/{trade_id}")
def remove_trade(trade_id: str, operation_id: str | None = None, _: dict = Depends(require_auth)) -> dict:
    atomic_write("trade.delete", record_id=trade_id, operation_id=operation_id)
    return {"success": True}
