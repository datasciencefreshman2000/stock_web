"""FIFO 成本計算。

設計重點：
1. 狀態可序列化（FifoState），因此可以存成 checkpoint 後續算，
   不必每次都從第一筆交易重跑（見 services/settlement.py）。
2. 除權息與分割在「走訪時間軸」時即時套用，不改寫原始 trades。
   分割前的交易是分割前價格、分割後的交易是分割後價格，
   在 ex_date 邊界調整持倉，兩邊就自然對得起來。
"""

from dataclasses import dataclass, field

from services.constants import ETF_LIST, TW_ACCOUNTS
from services.fees import calc_tw_fee, calc_tw_tax

EPSILON = 1e-7
SPLIT_ACTIONS = {"split", "reverse_split", "stock_dividend"}


@dataclass
class BuyLot:
    qty: float
    cost_per_share: float


@dataclass
class FifoState:
    """可序列化的 FIFO 狀態，對應資料表 fifo_checkpoints。"""

    lots: list[BuyLot] = field(default_factory=list)
    total_cost: float = 0.0
    realized_pnl: float = 0.0
    total_fee: float = 0.0
    total_tax: float = 0.0
    dividend_income: float = 0.0
    unmatched_sell_balance: float = 0.0
    unmatched_sell_qty: float = 0.0
    unmatched_sell_value: float = 0.0
    trade_count: int = 0

    def to_dict(self) -> dict:
        return {
            "lots": [{"qty": lot.qty, "cost_per_share": lot.cost_per_share} for lot in self.lots],
            "total_cost": self.total_cost,
            "realized_pnl": self.realized_pnl,
            "total_fee": self.total_fee,
            "total_tax": self.total_tax,
            "dividend_income": self.dividend_income,
            "unmatched_sell_balance": self.unmatched_sell_balance,
            "unmatched_sell_qty": self.unmatched_sell_qty,
            "unmatched_sell_value": self.unmatched_sell_value,
            "trade_count": self.trade_count,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "FifoState":
        if not data:
            return cls()
        lots_raw = data.get("lots") or []
        return cls(
            lots=[
                BuyLot(qty=float(lot["qty"]), cost_per_share=float(lot["cost_per_share"]))
                for lot in lots_raw
            ],
            total_cost=float(data.get("total_cost") or 0),
            realized_pnl=float(data.get("realized_pnl") or 0),
            total_fee=float(data.get("total_fee") or 0),
            total_tax=float(data.get("total_tax") or 0),
            dividend_income=float(data.get("dividend_income") or 0),
            unmatched_sell_balance=float(data.get("unmatched_sell_balance") or 0),
            unmatched_sell_qty=float(data.get("unmatched_sell_qty") or 0),
            unmatched_sell_value=float(data.get("unmatched_sell_value") or 0),
            trade_count=int(data.get("trade_count") or 0),
        )

    def copy(self) -> "FifoState":
        return FifoState.from_dict(self.to_dict())

    @property
    def current_qty(self) -> float:
        return sum(lot.qty for lot in self.lots)


def trade_sort_key(trade: dict) -> tuple[str, int, str, str]:
    is_sell = float(trade.get("sell_qty") or 0) > 0
    return (
        str(trade.get("date") or ""),
        1 if is_sell else 0,
        str(trade.get("created_at") or ""),
        str(trade.get("id") or ""),
    )


def action_sort_key(action: dict) -> str:
    return str(action.get("ex_date") or "")


def _apply_split(state: FifoState, ratio: float) -> None:
    """1 股變 ratio 股。總成本不變，只重新分配到更多股上。"""
    if ratio <= 0:
        return
    for lot in state.lots:
        lot.qty *= ratio
        lot.cost_per_share /= ratio
    state.unmatched_sell_balance *= ratio


def _apply_corporate_action(state: FifoState, action: dict) -> None:
    action_type = action.get("action_type")
    if action_type in SPLIT_ACTIONS:
        ratio = action.get("ratio")
        if ratio:
            _apply_split(state, float(ratio))
    elif action_type == "cash_dividend":
        amount = float(action.get("amount") or 0)
        state.dividend_income += state.current_qty * amount


def apply_trades(
    state: FifoState,
    trades: list[dict],
    account: str,
    ticker: str,
    actions: list[dict] | None = None,
    is_etf: bool | None = None,
) -> FifoState:
    """把 trades 套用到既有 state 上，回傳新的 state（不修改傳入的 state）。"""
    state = state.copy()
    is_tw = account in TW_ACCOUNTS
    etf = (ticker in ETF_LIST) if is_etf is None else is_etf

    pending_actions = sorted(actions or [], key=action_sort_key)
    action_index = 0

    def flush_actions(until: str) -> None:
        nonlocal action_index
        while action_index < len(pending_actions):
            ex_date = str(pending_actions[action_index].get("ex_date") or "")
            if not ex_date or (until and ex_date > until):
                break
            _apply_corporate_action(state, pending_actions[action_index])
            action_index += 1

    for trade in sorted(trades, key=trade_sort_key):
        trade_date = str(trade.get("date") or "")
        # 先把 ex_date 落在這筆交易之前（含當天）的事件套用完
        if trade_date:
            flush_actions(trade_date)

        buy_qty = float(trade.get("buy_qty") or 0)
        sell_qty = float(trade.get("sell_qty") or 0)
        price = float(trade["price"])
        state.trade_count += 1

        if buy_qty > 0:
            fee = calc_tw_fee(price, buy_qty) if is_tw else float(trade.get("fee") or 0)
            state.total_fee += fee
            # 先沖銷「找不到對應買單的賣出」，剩下的才建立新的買入 lot
            matched_gap_qty = min(buy_qty, state.unmatched_sell_balance)
            state.unmatched_sell_balance -= matched_gap_qty
            long_qty = buy_qty - matched_gap_qty
            if long_qty > EPSILON:
                state.lots.append(BuyLot(qty=long_qty, cost_per_share=price))
                state.total_cost += long_qty * price

        if sell_qty > 0:
            fee = calc_tw_fee(price, sell_qty) if is_tw else float(trade.get("fee") or 0)
            tax = calc_tw_tax(price, sell_qty, ticker, is_etf=etf) if is_tw else 0
            remaining = sell_qty
            matched_qty = 0.0
            cost_of_sold = 0.0

            while remaining > EPSILON and state.lots:
                lot = state.lots[0]
                qty = min(lot.qty, remaining)
                cost_of_sold += qty * lot.cost_per_share
                lot.qty -= qty
                remaining -= qty
                matched_qty += qty
                if lot.qty < EPSILON:
                    state.lots.pop(0)

            state.total_cost -= cost_of_sold
            if matched_qty > EPSILON:
                matched_ratio = matched_qty / sell_qty
                revenue = price * matched_qty - fee * matched_ratio - tax * matched_ratio
                state.realized_pnl += revenue - cost_of_sold
            if remaining > EPSILON:
                state.unmatched_sell_balance += remaining
                state.unmatched_sell_qty += remaining
                state.unmatched_sell_value += remaining * price
            state.total_fee += fee
            state.total_tax += tax

    # 交易跑完後，剩下的事件（例如今天剛除權）也要套用
    flush_actions("9999-12-31")
    return state


def summarize_state(state: FifoState) -> dict:
    current_qty = state.current_qty
    total_cost = state.total_cost
    if abs(current_qty) < EPSILON:
        current_qty = 0
        total_cost = 0

    return {
        "current_qty": current_qty,
        "total_cost": total_cost,
        "avg_price": total_cost / current_qty if current_qty > 0 else 0,
        "realized_pnl": state.realized_pnl,
        "total_fee": state.total_fee,
        "total_tax": state.total_tax,
        "dividend_income": state.dividend_income,
        "unmatched_sell_qty": state.unmatched_sell_qty,
        "unmatched_sell_value": state.unmatched_sell_value,
    }


def calc_fifo(
    trades: list[dict],
    account: str,
    ticker: str,
    opening: FifoState | None = None,
    actions: list[dict] | None = None,
    is_etf: bool | None = None,
) -> dict:
    """從頭（或從 opening state）計算 FIFO，回傳彙總結果。"""
    state = apply_trades(opening or FifoState(), trades, account, ticker, actions, is_etf)
    return summarize_state(state)
