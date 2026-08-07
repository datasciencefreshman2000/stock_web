"""新買進的標的必須馬上有價格，不能等排程。

這條規則被違反過：fetch_prices_batch 在 refresh=False 時，
對「完全沒有快取列」的標的直接回 None。結果是新增一筆從未持有過的
股票之後，持倉頁沒有現價、市值算成 0、首頁現金條的股票／現金比例跟著錯，
帳戶總額憑空少掉那筆的市值——要等下一次 cron 才會恢復。

「快取有點舊」可以忍，「根本沒有價格」不行。
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import prices  # noqa: E402


@pytest.fixture
def fake_provider(monkeypatch):
    """price_cache 裡只有 2330；2454 是新買的，還沒抓過。"""
    cache = {
        "TW:2330": {"symbol": "TW:2330", "price": 1100.0,
                    "fetched_at": "2000-01-01T00:00:00+00:00"},   # 刻意設成很舊
    }
    fetched: list[str] = []

    monkeypatch.setattr(prices, "list_price_cache",
                        lambda symbols: {s: cache[s] for s in symbols if s in cache})
    monkeypatch.setattr(prices, "upsert_price_cache_rows", lambda rows: rows)

    def fake_fugle(ticker, api_key):
        fetched.append(ticker)
        return {"2330": 1150.0, "2454": 1500.0}.get(ticker)

    monkeypatch.setattr(prices, "_fugle_price_sync", fake_fugle)
    return fetched


def run(**kwargs):
    return asyncio.run(
        prices.fetch_prices_batch(["2330", "2454"], "台股", "", fugle_key="x", **kwargs)
    )


def test_missing_price_is_fetched_even_without_refresh(fake_provider):
    """關鍵行為：refresh=False 也要把沒抓過的標的補起來。"""
    result = run(refresh=False, fetch_missing=True)
    assert result["2454"] == 1500.0, "新標的沒有價格，持倉頁與現金條都會算錯"
    assert fake_provider == ["2454"], "只該補抓缺的那一檔"


def test_stale_price_is_not_refetched(fake_provider):
    """對照組：既有的價格再舊也不重抓——那才是快取該做的事。"""
    result = run(refresh=False, fetch_missing=True)
    assert result["2330"] == 1100.0
    assert "2330" not in fake_provider


def test_without_the_flag_price_is_none(fake_provider):
    """沒開 fetch_missing 時維持原行為（純讀快取的呼叫端仍然安全）。"""
    result = run(refresh=False, fetch_missing=False)
    assert result["2454"] is None
    assert fake_provider == []


def test_refresh_true_updates_everything(fake_provider):
    """refresh=True 是排程用的：舊的也要更新。"""
    result = run(refresh=True)
    assert result["2330"] == 1150.0
    assert result["2454"] == 1500.0
    assert sorted(fake_provider) == ["2330", "2454"]


def test_market_value_would_be_wrong_without_price():
    """把「沒有價格 → 市值算成 0」這件事釘住，說明為什麼上面那條重要。"""
    from services.calculator import build_holdings_from_results, summarize_account_from_results

    fifo = {
        "2454": {"current_qty": 1000, "total_cost": 1500000.0, "avg_price": 1500.0,
                 "realized_pnl": 0.0, "total_fee": 0.0, "total_tax": 0.0},
    }
    without = build_holdings_from_results(fifo, {"2454": None})
    with_price = build_holdings_from_results(fifo, {"2454": 1500.0})

    assert summarize_account_from_results(fifo, without)["market_value"] == 0
    assert summarize_account_from_results(fifo, with_price)["market_value"] == 1500000.0


def test_failed_lookup_is_not_retried_every_time(monkeypatch):
    """抓不到的標的（下市、代號打錯）不能每次重建都再打一次外部 API。

    失敗時會寫一列 price=null 當退避標記，下次就跳過。
    """
    store: dict[str, dict] = {}
    attempts: list[str] = []

    monkeypatch.setattr(prices, "list_price_cache",
                        lambda symbols: {s: store[s] for s in symbols if s in store})

    def remember(rows):
        for row in rows:
            store[row["symbol"]] = row
        return rows

    monkeypatch.setattr(prices, "upsert_price_cache_rows", remember)

    def always_fails(ticker, api_key):
        attempts.append(ticker)
        return None

    monkeypatch.setattr(prices, "_fugle_price_sync", always_fails)

    for _ in range(3):
        asyncio.run(prices.fetch_prices_batch(["9999"], "台股", "", fugle_key="x",
                                              refresh=False, fetch_missing=True))

    assert attempts == ["9999"], f"重試了 {len(attempts)} 次，應該只試一次"
    assert store["TW:9999"]["price"] is None
