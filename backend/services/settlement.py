"""FIFO 增量結算（A4）。

沒有 checkpoint 時：從第一筆交易算到現在。
有 checkpoint 時：從 checkpoint 的狀態接續，只套用 as_of_date 之後的交易。

安全機制有兩層：
1. 明確作廢：新增／修改／刪除交易時，刪掉 as_of_date >= 該交易日期的 checkpoint。
2. 交易筆數核對：checkpoint 記錄它涵蓋了幾筆交易，載入時重新數一次，
   對不上就丟棄 checkpoint 改為全量重算。即使第 1 層漏掉也不會算錯。
"""

from datetime import date as Date
from datetime import datetime, timedelta, timezone

from config import get_settings
from services.fifo import FifoState, apply_trades, summarize_state
from services.symbols import symbol_for

# repositories 會拉進 supabase client，這裡刻意延遲匯入：
# 計算核心（analyze_account / _resume_point 等）必須能在沒有資料庫的情況下測試。

# 沒有日期的早期交易一律視為最早，永遠落在 checkpoint 涵蓋範圍內
MIN_DATE = "0001-01-01"


def trade_date_key(trade: dict) -> str:
    return str(trade.get("date") or MIN_DATE)


def checkpoint_boundary(now: datetime | None = None) -> str:
    """checkpoint 只結算到「今天 - lag」，近期交易留在可隨時重算的熱區。"""
    settings = get_settings()
    current = (now or datetime.now(timezone.utc)).date()
    return (current - timedelta(days=settings.fifo_checkpoint_lag_days)).isoformat()


def group_by_ticker(trades: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for trade in trades:
        grouped.setdefault(trade["ticker"], []).append(trade)
    return grouped


def _checkpoint_to_state(row: dict) -> FifoState:
    payload = dict(row.get("lots_payload") or {})
    if not payload:
        payload = {
            "lots": row.get("lots") or [],
            "total_cost": row.get("total_cost"),
            "realized_pnl": row.get("realized_pnl"),
            "total_fee": row.get("total_fee"),
            "total_tax": row.get("total_tax"),
            "dividend_income": row.get("dividend_income"),
            "unmatched_sell_balance": row.get("unmatched_sell_balance"),
            "unmatched_sell_qty": row.get("unmatched_sell_qty"),
            "unmatched_sell_value": row.get("unmatched_sell_value"),
            "trade_count": row.get("trade_count"),
        }
    return FifoState.from_dict(payload)


def _state_to_checkpoint(account: str, ticker: str, as_of_date: str, state: FifoState) -> dict:
    return {
        "account": account,
        "ticker": ticker,
        "as_of_date": as_of_date,
        "lots": [{"qty": lot.qty, "cost_per_share": lot.cost_per_share} for lot in state.lots],
        "total_cost": state.total_cost,
        "realized_pnl": state.realized_pnl,
        "total_fee": state.total_fee,
        "total_tax": state.total_tax,
        "unmatched_sell_balance": state.unmatched_sell_balance,
        "unmatched_sell_qty": state.unmatched_sell_qty,
        "unmatched_sell_value": state.unmatched_sell_value,
        "trade_count": state.trade_count,
    }


def load_reference_data_for_symbols(symbols: list[str]) -> tuple[dict[str, list[dict]], set[str]]:
    """一次把「全部帳戶」的除權息事件與 ETF 標記讀進來。

    先前是每個帳戶各呼叫一次 load_reference_data()，3 個帳戶 = 6 次 DB 往返。
    合併之後固定 2 次。
    """
    from repositories.corporate_actions import list_corporate_actions
    from repositories.tickers import list_tickers

    symbols = sorted(set(symbols))
    if not symbols:
        return {}, set()
    actions_by_symbol = list_corporate_actions(symbols)
    ticker_rows = list_tickers(symbols)
    etf_symbols = {symbol for symbol, row in ticker_rows.items() if row.get("is_etf")}
    return actions_by_symbol, etf_symbols


def load_reference_data(account: str, tickers: list[str]) -> tuple[dict[str, list[dict]], set[str]]:
    """一次載入該帳戶所有標的的除權息事件與 ETF 標記。"""
    from repositories.corporate_actions import list_corporate_actions
    from repositories.tickers import list_tickers

    symbols = [symbol_for(account, ticker) for ticker in tickers]
    actions_by_symbol = list_corporate_actions(symbols)
    ticker_rows = list_tickers(symbols)
    etf_symbols = {symbol for symbol, row in ticker_rows.items() if row.get("is_etf")}
    return actions_by_symbol, etf_symbols


def analyze_account(
    account: str,
    trades: list[dict],
    checkpoints: dict[str, dict] | None = None,
    actions_by_symbol: dict[str, list[dict]] | None = None,
    etf_symbols: set[str] | None = None,
    up_to: str | None = None,
) -> dict[str, dict]:
    """計算該帳戶每個 ticker 的 FIFO 結果（優先從 checkpoint 續算）。"""
    by_ticker = group_by_ticker(trades)
    checkpoints = checkpoints or {}
    actions_by_symbol = actions_by_symbol or {}
    etf_symbols = etf_symbols or set()

    results: dict[str, dict] = {}
    for ticker, ticker_trades in by_ticker.items():
        symbol = symbol_for(account, ticker)
        actions = actions_by_symbol.get(symbol, [])
        is_etf = symbol in etf_symbols if etf_symbols else None

        if up_to:
            ticker_trades = [t for t in ticker_trades if trade_date_key(t) <= up_to]
            actions = [a for a in actions if str(a.get("ex_date") or "") <= up_to]

        state, pending_trades, pending_actions = _resume_point(
            account, ticker, ticker_trades, actions, checkpoints.get(ticker)
        )
        final_state = apply_trades(state, pending_trades, account, ticker, pending_actions, is_etf)
        results[ticker] = summarize_state(final_state)
        results[ticker]["_state"] = final_state
    return results


def _resume_point(
    account: str,
    ticker: str,
    ticker_trades: list[dict],
    actions: list[dict],
    checkpoint: dict | None,
) -> tuple[FifoState, list[dict], list[dict]]:
    """決定要從哪裡開始算。checkpoint 可疑時退回全量重算。"""
    if not checkpoint:
        return FifoState(), ticker_trades, actions

    as_of = str(checkpoint.get("as_of_date") or "")
    covered = [t for t in ticker_trades if trade_date_key(t) <= as_of]

    # 第二層防線：涵蓋筆數對不上代表有交易被改過，checkpoint 不可信
    if len(covered) != int(checkpoint.get("trade_count") or 0):
        return FifoState(), ticker_trades, actions

    state = _checkpoint_to_state(checkpoint)
    pending_trades = [t for t in ticker_trades if trade_date_key(t) > as_of]
    pending_actions = [a for a in actions if str(a.get("ex_date") or "") > as_of]
    return state, pending_trades, pending_actions


def settle_account(account: str, trades: list[dict], as_of_date: str) -> int:
    """把該帳戶結算到 as_of_date，寫入 checkpoint。回傳寫入筆數。"""
    from repositories.fifo_checkpoints import list_latest_checkpoints, prune_checkpoints, upsert_checkpoints

    tickers = sorted({trade["ticker"] for trade in trades})
    if not tickers:
        return 0

    actions_by_symbol, etf_symbols = load_reference_data(account, tickers)
    existing = list_latest_checkpoints(account, as_of_date)
    results = analyze_account(
        account,
        trades,
        checkpoints=existing,
        actions_by_symbol=actions_by_symbol,
        etf_symbols=etf_symbols,
        up_to=as_of_date,
    )

    rows = [
        _state_to_checkpoint(account, ticker, as_of_date, result["_state"])
        for ticker, result in results.items()
    ]
    upsert_checkpoints(rows)
    for ticker in results:
        prune_checkpoints(account, ticker)
    return len(rows)


def invalidate_for_trade(trade: dict | None) -> None:
    """交易新增／修改／刪除後呼叫，作廢受影響的 checkpoint。"""
    from repositories.fifo_checkpoints import invalidate_from

    if not trade:
        return
    account = trade.get("account")
    ticker = trade.get("ticker")
    if not account or not ticker:
        return
    invalidate_from(account, str(ticker).strip().upper(), trade_date_key(trade))


def should_settle(last_run_at: str | None, latest_change_at: str | None, now: datetime | None = None) -> bool:
    """距離上次結算已滿間隔，且期間內確實有交易異動時才結算。"""
    settings = get_settings()
    current = now or datetime.now(timezone.utc)

    if not latest_change_at:
        return False

    last_run = _parse(last_run_at)
    if last_run is None:
        return True

    interval = timedelta(hours=settings.fifo_settle_interval_hours)
    if current - last_run < interval:
        return False

    changed_at = _parse(latest_change_at)
    return changed_at is None or changed_at > last_run


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def month_end(value: str) -> bool:
    parsed = Date.fromisoformat(value)
    return Date.fromordinal(parsed.toordinal() + 1).month != parsed.month
