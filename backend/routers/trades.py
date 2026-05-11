from fastapi import APIRouter, Query

from models import TradeCreate
from repositories.trades import create_trade, delete_trade, list_trades
from services.constants import TW_ACCOUNTS
from services.fees import calc_tw_fee

router = APIRouter()


@router.get("/{account}")
def get_trades(
    account: str,
    ticker: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    return {"trades": list_trades(account, ticker, start_date, end_date)}


@router.post("")
def add_trade(trade: TradeCreate) -> dict:
    payload = trade.model_dump(mode="json")
    qty = payload.get("buy_qty") or payload.get("sell_qty") or 0
    if payload["account"] in TW_ACCOUNTS and not payload.get("fee"):
        payload["fee"] = calc_tw_fee(payload["price"], qty)
    payload["total"] = payload["price"] * qty + payload["fee"] if payload.get("buy_qty") else payload["price"] * qty - payload["fee"]
    created = create_trade(payload)
    return {"success": True, "trade": created}


@router.delete("/{trade_id}")
def remove_trade(trade_id: str) -> dict:
    delete_trade(trade_id)
    return {"success": True}
