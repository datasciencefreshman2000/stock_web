"""除權息與股票分割維護。

用途：像 MUU 這種發生分割但紀錄沒更新的情況，
在這裡登記一筆 split 事件即可，不需要（也不應該）去改寫原始交易紀錄。
"""

from fastapi import APIRouter, Depends, Query

from dependencies import require_auth
from models import CorporateActionCreate
from repositories.corporate_actions import (
    create_corporate_action,
    delete_corporate_action,
    list_corporate_actions,
)
from repositories.fifo_checkpoints import invalidate_from
from repositories.summary_cache import clear_summary_cache
from repositories.trades import list_trades
from services.accounts import ACCOUNTS
from services.symbols import symbol_for, ticker_from_symbol

router = APIRouter(dependencies=[Depends(require_auth)])


def _invalidate_for_symbol(symbol: str, ex_date: str) -> None:
    """分割事件會改變該標的的所有後續成本，相關 checkpoint 全部作廢。"""
    ticker = ticker_from_symbol(symbol)
    for account in ACCOUNTS:
        if symbol_for(account, ticker) == symbol:
            invalidate_from(account, ticker, ex_date)
    clear_summary_cache()


@router.get("")
def get_actions(symbol: str | None = Query(default=None)) -> dict:
    grouped = list_corporate_actions([symbol] if symbol else None)
    return {"actions": grouped}


@router.post("")
def add_action(payload: CorporateActionCreate) -> dict:
    data = payload.model_dump(mode="json")
    data["symbol"] = symbol_for(payload.account, payload.ticker)
    data["ticker"] = payload.ticker.strip().upper()
    data.pop("account", None)

    action = create_corporate_action(data)
    _invalidate_for_symbol(data["symbol"], data["ex_date"])
    return {"success": True, "action": action}


@router.delete("/{action_id}")
def remove_action(action_id: str) -> dict:
    delete_corporate_action(action_id)
    # 不知道被刪的是哪個標的，保守起見清掉彙總快取；
    # checkpoint 由下一次結算重建。
    clear_summary_cache()
    return {"success": True}


@router.get("/suggest/{account}/{ticker}")
def suggest_split_window(account: str, ticker: str) -> dict:
    """列出該標的的交易紀錄，方便判斷分割發生在哪個區間。

    典型徵兆：某個日期前後的成交價出現數倍落差。
    """
    trades = list_trades(account, ticker)
    rows = [
        {
            "date": t.get("date"),
            "side": "buy" if (t.get("buy_qty") or 0) > 0 else "sell",
            "qty": t.get("buy_qty") or t.get("sell_qty"),
            "price": t.get("price"),
        }
        for t in trades
    ]
    prices = [r["price"] for r in rows if r["price"]]
    return {
        "account": account,
        "ticker": ticker.strip().upper(),
        "symbol": symbol_for(account, ticker),
        "trades": rows,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "hint": "若 price_max / price_min 接近 2、3、4 等整數倍，很可能是分割",
    }
