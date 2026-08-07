"""PostgREST 一次只回 1000 列，而且不報錯。

這個預設值造成過一個很難察覺的 bug：

    交易累積到 1000 筆之後，list_trades() 只拿得到前 1000 筆。
    查詢是 .order("date") 由舊到新，所以被截掉的正是**最新的交易**。

    「紀錄」頁有帳戶與日期篩選、列數少，看得到新交易；
    「持倉」與「總覽」讀全表，新交易直接消失。
    症狀就是「剛記的賣出沒有反映在持倉上」，而且只發生在近期的交易。

沒有錯誤訊息、沒有例外，資料就是少了。所以一定要有測試守著。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from repositories import trades as trades_repo  # noqa: E402

MAX_ROWS = 1000        # PostgREST 的預設上限


class FakePostgrest:
    """模擬 PostgREST：不管你要多少，一次最多給 MAX_ROWS 列。"""

    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls
        self._start = 0
        self._stop = MAX_ROWS - 1

    def select(self, *a, **k):
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

    def range(self, start, stop):
        self._start, self._stop = start, stop
        return self

    def execute(self):
        window = self._rows[self._start:self._stop + 1][:MAX_ROWS]
        self._calls.append((self._start, len(window)))
        return type("R", (), {"data": window})()


def fake_db(rows, calls):
    return type("S", (), {"table": lambda self, name: FakePostgrest(rows, calls)})()


def make_trades(n):
    return [
        {"id": str(i), "account": "台股", "ticker": "2455",
         "date": "2020-01-01", "buy_qty": 1, "sell_qty": None, "price": 100.0}
        for i in range(n)
    ]


def test_reads_past_the_1000_row_limit(monkeypatch):
    rows = make_trades(2350)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_db(rows, calls))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_db(rows, calls))

    result = trades_repo.list_trades()

    assert len(result) == 2350, f"只讀到 {len(result)} 筆，最新的交易被截掉了"
    assert [n for _, n in calls] == [1000, 1000, 350], f"分頁不對：{calls}"


def test_last_trade_is_not_lost(monkeypatch):
    """最重要的一條：排序由舊到新，被截掉的就是最新那筆。"""
    rows = make_trades(1000)
    rows.append({"id": "newest", "account": "台股", "ticker": "2455",
                 "date": "2026-08-07", "buy_qty": None, "sell_qty": 28, "price": 378.0})
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_db(rows, []))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_db(rows, []))

    result = trades_repo.list_trades()
    assert result[-1]["id"] == "newest", "第 1001 筆（最新的賣出）不見了"


def test_exact_multiple_of_page_size(monkeypatch):
    """剛好 1000 筆時不能無限迴圈，也不能少讀。"""
    rows = make_trades(1000)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_db(rows, calls))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_db(rows, calls))

    assert len(trades_repo.list_trades()) == 1000
    assert [n for _, n in calls] == [1000, 0], "整除時要再問一次才知道沒有下一頁"


def test_empty_table(monkeypatch):
    monkeypatch.setattr(trades_repo, "get_supabase", lambda: fake_db([], []))
    monkeypatch.setattr(database, "get_supabase", lambda: fake_db([], []))
    assert trades_repo.list_trades() == []


def test_old_single_query_would_have_lost_data():
    """對照組：說明修正前為什麼會出事。"""
    rows = make_trades(2350)
    truncated = rows[:MAX_ROWS]          # 修正前 PostgREST 就是這樣回你
    assert len(truncated) == 1000
    assert truncated[-1]["id"] == "999"
    assert rows[-1]["id"] == "2349", "第 1000 筆之後的交易全部看不到"
