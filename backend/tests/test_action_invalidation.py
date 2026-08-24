"""刪除除權息／分割事件之後，FIFO checkpoint 必須跟著作廢。

這條規則被違反過，而且後果是**永久性的錯誤資料**：

    routers/actions.remove_action 原本只呼叫 clear_summary_cache()。
    但那清的是彙總快取，不是 FIFO checkpoint。
    _resume_point 只用 trade_count 判斷 checkpoint 可不可信，
    而刪掉一筆事件並不會改變 trade_count ——
    於是「已經套用過分割」的狀態被一直沿用。

    實測：登記 2:1 分割 → 100 股變 200 股 → 刪掉事件後仍然是 200 股。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.settlement import _state_to_checkpoint, analyze_account  # noqa: E402

TRADES = [{
    "id": "1", "account": "美股", "ticker": "MUU", "date": "2024-01-02",
    "buy_qty": 100, "sell_qty": None, "price": 50.0, "fee": 0,
    "created_at": "2024-01-02T00:00:00Z",
}]
SPLIT = [{"symbol": "MUU", "ticker": "MUU", "ex_date": "2024-06-01",
          "action_type": "split", "ratio": 2.0}]


def qty(results):
    return results["MUU"]["current_qty"]


def test_split_applies_after_the_last_trade():
    """事件的 ex_date 在最後一筆交易之後也要生效。"""
    assert qty(analyze_account("美股", TRADES)) == 100
    assert qty(analyze_account("美股", TRADES, actions_by_symbol={"MUU": SPLIT})) == 200


def test_stale_checkpoint_keeps_the_split():
    """記錄問題本身：沒作廢 checkpoint 的話，分割清不掉。

    這條測試斷言的是**壞掉的行為**，用來說明為什麼 remove_action
    一定要作廢 checkpoint。若哪天 _resume_point 變聰明了，這條會失敗，
    那是好事，把它改掉即可。
    """
    with_split = analyze_account("美股", TRADES, actions_by_symbol={"MUU": SPLIT})["MUU"]
    checkpoint = _state_to_checkpoint("美股", "MUU", "2024-07-01", with_split["_state"])

    # 事件已刪除（actions 是空的），但 checkpoint 還在
    after = analyze_account("美股", TRADES, checkpoints={"MUU": checkpoint})
    assert qty(after) == 200, "沿用 checkpoint 時分割仍在——所以刪除事件必須作廢 checkpoint"


def test_invalidating_the_checkpoint_restores_the_truth():
    """作廢之後（checkpoints 傳空的）就會全量重算，回到正確的 100 股。"""
    assert qty(analyze_account("美股", TRADES, checkpoints={})) == 100


def test_remove_action_invalidates_checkpoints(monkeypatch):
    """路由層：DELETE /api/actions/{id} 必須呼叫 invalidate_from。"""
    from routers import actions

    calls: list[tuple] = []
    monkeypatch.setattr(actions, "get_corporate_action",
                        lambda _id: {"id": _id, "symbol": "MUU", "ticker": "MUU",
                                     "ex_date": "2024-06-01"})
    monkeypatch.setattr(actions, "delete_corporate_action", lambda _id: None)
    monkeypatch.setattr(actions, "invalidate_from",
                        lambda account, ticker, date: calls.append((account, ticker, date)))
    monkeypatch.setattr(actions, "clear_summary_cache", lambda *a, **k: None)
    monkeypatch.setattr(actions, "clear_checkpoints", lambda *a, **k: None)

    actions.remove_action("abc")

    assert calls, "刪除事件時沒有作廢任何 checkpoint"
    assert all(date == "2024-06-01" for _, _, date in calls)
    assert {ticker for _, ticker, _ in calls} == {"MUU"}


def test_falls_back_to_clearing_everything_when_action_is_gone(monkeypatch):
    """讀不到事件時（例如已被別處刪掉）要保守地全部清掉。"""
    from routers import actions

    cleared: list[str] = []
    monkeypatch.setattr(actions, "get_corporate_action", lambda _id: None)
    monkeypatch.setattr(actions, "delete_corporate_action", lambda _id: None)
    monkeypatch.setattr(actions, "clear_checkpoints",
                        lambda *a, **k: cleared.append("checkpoints"))
    monkeypatch.setattr(actions, "clear_summary_cache",
                        lambda *a, **k: cleared.append("summary"))

    actions.remove_action("unknown")
    assert cleared == ["checkpoints", "summary"]
