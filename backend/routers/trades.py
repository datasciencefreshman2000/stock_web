from fastapi import APIRouter, Depends, HTTPException, Query

from config import get_settings
from dependencies import require_auth
from models import TradeCreate, TradeUpdate
from repositories.summary_cache import clear_summary_cache
from repositories.tickers import list_tickers
from repositories.trades import (
    COMBINED_HISTORY_ACCOUNT,
    create_trade,
    delete_trade,
    get_trade,
    list_trades,
    update_trade,
)
from services.constants import TW_ACCOUNTS
from services.fees import calc_tw_fee, calc_tw_tax
from services.prices import resolve_company_names
from services.settlement import invalidate_for_trade
from services.symbols import symbol_for

router = APIRouter()


def prepare_trade_payload(payload: dict) -> dict:
    qty = payload.get("buy_qty") or payload.get("sell_qty") or 0
    is_tw = payload["account"] in TW_ACCOUNTS
    if is_tw and not payload.get("fee"):
        payload["fee"] = calc_tw_fee(payload["price"], qty)
    tax = calc_tw_tax(payload["price"], qty, payload["ticker"]) if is_tw and payload.get("sell_qty") else 0
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


@router.get("/{account}")
async def get_trades(
    account: str,
    ticker: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    _: dict = Depends(require_auth),
) -> dict:
    trades = list_trades(account, ticker, start_date, end_date)
    if not trades:
        return {"trades": [], "account": account}

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

    return {"trades": enriched, "account": account, "combined": account == COMBINED_HISTORY_ACCOUNT}


@router.post("")
def add_trade(trade: TradeCreate, _: dict = Depends(require_auth)) -> dict:
    payload = prepare_trade_payload(trade.model_dump(mode="json"))
    created = create_trade(payload)
    after_trade_change(created)
    return {"success": True, "trade": created}


@router.patch("/{trade_id}")
def patch_trade(trade_id: str, trade: TradeUpdate, _: dict = Depends(require_auth)) -> dict:
    previous = get_trade(trade_id)
    payload = prepare_trade_payload(trade.model_dump(mode="json"))
    updated = update_trade(trade_id, payload)
    # 舊值與新值都要作廢：日期或代號可能被改掉
    after_trade_change(previous, updated)
    return {"success": True, "trade": updated}


@router.delete("/{trade_id}")
def remove_trade(trade_id: str, _: dict = Depends(require_auth)) -> dict:
    previous = get_trade(trade_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Trade not found.")
    delete_trade(trade_id)
    after_trade_change(previous)
    return {"success": True}
