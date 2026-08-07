"""帳戶名稱前後有空白時，交易不能被靜默丟掉。

背景：calculate_summary 用
    `if trade.get("account") in trades_by_account`
分組。ACCOUNTS 是 ["台股", "美股", "爸媽美股"]，
所以資料庫裡存成 "台股 " 的交易會直接落到 else，
在「紀錄」看得到、在「持倉」與「總覽」卻完全不存在。

靜默丟資料比報錯更糟，因為你不會發現。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from repositories import trades as trades_repo  # noqa: E402
from services.accounts import ACCOUNTS  # noqa: E402


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._start, self._stop = 0, len(rows)

    def select(self, *a, **k):
        return self

    def range(self, start, stop):
        # list_trades 現在會分頁讀（見 test_pagination.py）
        self._start, self._stop = start, stop
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": self._rows[self._start:self._stop + 1]})()


def fake_supabase(rows):
    return type("S", (), {"table": lambda self, name: FakeQuery(rows)})()


def test_account_whitespace_is_stripped(monkeypatch):
    rows = [{"account": "台股 ", "ticker": " 2330 ", "date": "2024-01-02"}]
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_supabase(rows))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_supabase(rows))

    result = trades_repo.list_trades()
    assert result[0]["account"] == "台股"
    assert result[0]["ticker"] == "2330"


def test_stripped_account_survives_summary_grouping(monkeypatch):
    """真正在意的是這個：去空白之後才進得了 summary 的分組。"""
    rows = [
        {"account": "台股 ", "ticker": "2330", "date": "2024-01-02"},
        {"account": " 美股", "ticker": "AAPL", "date": "2024-01-03"},
    ]
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_supabase(rows))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_supabase(rows))

    grouped = {account: [] for account in ACCOUNTS}
    for trade in trades_repo.list_trades():
        if trade.get("account") in grouped:
            grouped[trade["account"]].append(trade)

    assert len(grouped["台股"]) == 1, "有空白的帳戶被丟掉了"
    assert len(grouped["美股"]) == 1


def test_non_string_account_does_not_crash(monkeypatch):
    rows = [{"account": None, "ticker": "2330", "date": "2024-01-02"}]
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_supabase(rows))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_supabase(rows))
    assert trades_repo.list_trades()[0]["account"] is None
