"""就地更新快取的行為測試（不碰資料庫，全部用替身）。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import cache_patch  # noqa: E402


@pytest.fixture
def fake_db(monkeypatch):
    """記錄每次讀寫，用來數 DB 往返次數。"""
    store = {
        "main": {
            "usd_rate": 30.0,
            "accounts": {
                "台股": {"account_total_twd": 100000.0},
                "美股": {"account_total_twd": 50000.0},
                "爸媽美股": {"account_total_twd": 20000.0},
            },
            "cash": {"twd_equivalent": 999},          # 舊值，應被覆蓋
            "investments": [
                {
                    "name": "基金", "cost": 1000, "value": 1200,
                    "cash_amount": 0, "currency": "TWD", "cost_twd": 1000,
                    "value_twd": 1200, "cash_amount_twd": 0,
                }
            ],
            "investment_total": 1200,
            "manual_investment_cash_total": 0,
            "total_assets": 1,                        # 舊值
        },
    }
    calls = {"get": 0, "upsert": 0, "list": 0}

    def get_caches(keys):
        """批次讀。一次呼叫 = 一次 DB 往返，不論拿幾把 key。"""
        calls["get"] += 1
        return {k: dict(store[k]) for k in keys if k in store}

    def upsert_caches(payloads):
        calls["upsert"] += 1
        for key, payload in payloads.items():
            store[key] = dict(payload)
        return "2026-08-06T00:00:00Z"

    def cash_rows():
        calls["list"] += 1
        return [
            {"name": "國泰", "currency": "TWD", "amount": 10000, "account": "台股"},
            {"name": "身上", "currency": "USD", "amount": 100, "account": None},
        ]

    def investments():
        calls["list"] += 1
        return [{"name": "基金", "cost": 1000, "value": 1200, "cash_amount": 0, "currency": "TWD"}]

    def manual_values():
        calls["list"] += 1
        return [{"key": "invested_台股", "value": 5000}]

    monkeypatch.setattr(cache_patch, "get_summary_caches", get_caches)
    monkeypatch.setattr(cache_patch, "upsert_summary_caches", upsert_caches)
    monkeypatch.setattr(cache_patch, "list_cash_accounts", cash_rows)
    monkeypatch.setattr(cache_patch, "list_manual_investments", investments)
    monkeypatch.setattr(cache_patch, "list_manual_values", manual_values)
    return store, calls


def test_returns_false_when_no_cache(monkeypatch):
    """沒有快取可 patch 時要回 False，讓呼叫端退回刪除路徑。"""
    monkeypatch.setattr(cache_patch, "get_summary_caches", lambda keys: {})
    assert cache_patch.refresh_cash_and_manual_in_cache() is False


def test_updates_cash_section(fake_db):
    store, _ = fake_db
    assert cache_patch.refresh_cash_and_manual_in_cache() is True
    cash = store["main"]["cash"]
    # 10000 TWD + 100 USD × 30 = 13000
    assert cash["twd_equivalent"] == pytest.approx(13000)
    assert "by_account" in cash


def test_preserves_fifo_derived_fields(fake_db):
    """關鍵：帳戶（FIFO 結果）必須原封不動沿用，不能被重算或清掉。"""
    store, _ = fake_db
    before = dict(store["main"]["accounts"])
    cache_patch.refresh_cash_and_manual_in_cache()
    assert store["main"]["accounts"] == before


def test_recomputes_total_assets(fake_db):
    store, _ = fake_db
    cache_patch.refresh_cash_and_manual_in_cache()
    # 自有帳戶 100000+50000 + 投資 1200 + 投資現金 0 + 自有現金 13000
    assert store["main"]["total_assets"] == pytest.approx(164200)
    assert store["main"]["own_total_assets"] == store["main"]["total_assets"]


def test_external_account_excluded_from_own_total(fake_db):
    store, _ = fake_db
    cache_patch.refresh_cash_and_manual_in_cache()
    # 爸媽美股 20000 不能算進自有總資產
    assert store["main"]["total_assets"] < 164200 + 20000


def test_is_cheaper_than_full_recompute(fake_db):
    """成本檢查：patch 的讀取次數應遠低於完整重算（約 11 次）。"""
    _, calls = fake_db
    cache_patch.refresh_cash_and_manual_in_cache()
    reads = calls["list"] + calls["get"]
    assert reads <= 8, f"讀取 {reads} 次，太多了"


def test_cache_io_is_batched(fake_db):
    """回歸測試：快取的讀寫必須各只有一次。

    這條規則被違反過一次 —— 原本寫成「summary 讀一次、三個帳戶各讀一次，
    再各自 patch（patch 內部又讀一次）」，光快取就 12 次往返，
    比它要取代的完整重算還貴。
    """
    _, calls = fake_db
    cache_patch.refresh_cash_and_manual_in_cache()
    assert calls["get"] == 1, f"快取讀了 {calls['get']} 次，應該批次一次讀完"
    assert calls["upsert"] == 1, f"快取寫了 {calls['upsert']} 次，應該批次一次寫完"


def test_patches_portfolio_cash_too(fake_db):
    """各帳戶持倉頁的 dashboard.cash 也要跟著更新，其餘欄位不能動。"""
    store, _ = fake_db
    store["portfolio:台股"] = {
        "dashboard": {"cash": {"twd_equivalent": 0}, "market_value": 123456.0},
        "holdings": [{"ticker": "2330"}],
    }
    cache_patch.refresh_cash_and_manual_in_cache()
    dashboard = store["portfolio:台股"]["dashboard"]
    assert dashboard["cash"]["twd_equivalent"] == pytest.approx(10000)   # 國泰 10000 TWD
    assert dashboard["market_value"] == 123456.0                         # FIFO 來的欄位不動
    assert store["portfolio:台股"]["holdings"] == [{"ticker": "2330"}]


def test_investments_enriched_with_twd(fake_db):
    store, _ = fake_db
    cache_patch.refresh_cash_and_manual_in_cache("investment")
    inv = store["main"]["investments"][0]
    assert inv["value_twd"] == pytest.approx(1200)
    assert inv["pnl_twd"] == pytest.approx(200)


def test_usd_investment_converted(fake_db, monkeypatch):
    monkeypatch.setattr(cache_patch, "list_manual_investments",
                        lambda: [{"name": "美股基金", "cost": 100, "value": 200,
                                  "cash_amount": 0, "currency": "USD"}])
    store, _ = fake_db
    cache_patch.refresh_cash_and_manual_in_cache("investment")
    assert store["main"]["investments"][0]["value_twd"] == pytest.approx(6000)  # 200 × 30


def test_invested_scope_recomputes_account_totals(fake_db):
    store, _ = fake_db
    store["main"]["accounts"]["台股"] = {
        "cost": 3000,
        "market_value": 4000,
        "realized_pnl": 500,
        "account_total_twd": 999999,
    }

    cache_patch.refresh_cash_and_manual_in_cache("invested")

    account = store["main"]["accounts"]["台股"]
    assert account["invested"] == pytest.approx(5000)
    assert account["inferred_cash"] == pytest.approx(2500)
    assert account["account_total_twd"] == pytest.approx(6500)
