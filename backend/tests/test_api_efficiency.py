import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import jobs, manual, portfolio, summary, trades  # noqa: E402
from services import prices  # noqa: E402


def test_month_bounds_handles_year_boundary():
    assert manual.month_bounds("2026-12") == ("2026-12-01", "2027-01-01")


def test_capital_movements_only_requests_selected_month(monkeypatch):
    captured = {}

    def fake_list(start_date, end_date):
        captured.update(start=start_date, end=end_date)
        return [{"id": "one", "movement_date": "2026-07-10"}]

    monkeypatch.setattr(manual, "list_capital_movements", fake_list)
    result = manual.get_capital_movements("2026-07")

    assert captured == {"start": "2026-07-01", "end": "2026-08-01"}
    assert result["month"] == "2026-07"
    assert len(result["movements"]) == 1


def test_bulk_investment_update_patches_cache_once(monkeypatch):
    calls = {"update": 0, "cache": 0}
    rows = [
        {
            "id": "one",
            "name": "基金",
            "asset_type": "基金",
            "cost": 100,
            "cash_amount": 0,
            "value": 120,
            "currency": "TWD",
        },
        {
            "id": "two",
            "name": "加密貨幣",
            "asset_type": "加密貨幣",
            "cost": 50,
            "cash_amount": 0,
            "value": 80,
            "currency": "USD",
        },
    ]

    def fake_update(payloads):
        calls["update"] += 1
        return payloads

    def fake_money_changed(scope):
        calls["cache"] += 1
        assert scope == "investment"

    monkeypatch.setattr(manual, "update_manual_investments", fake_update)
    monkeypatch.setattr(manual, "money_changed", fake_money_changed)
    payload = manual.ManualInvestmentBulkUpdate(investments=rows)

    result = manual.patch_investments(payload)

    assert len(result["investments"]) == 2
    assert calls == {"update": 1, "cache": 1}


def test_trade_tickers_endpoint_returns_lightweight_list(monkeypatch):
    monkeypatch.setattr(trades, "list_trade_tickers", lambda account: ["2330", "2454"])
    result = trades.get_trade_tickers("台股", _={})
    assert result == {"account": "台股", "tickers": ["2330", "2454"]}


def test_company_names_for_accounts_use_one_ticker_query(monkeypatch):
    calls = {"list": 0}

    def fake_list(symbols):
        calls["list"] += 1
        return {
            "TW:2330": {"name": "台積電"},
            "NVDA": {"name": "NVIDIA"},
        }

    monkeypatch.setattr(prices, "list_tickers", fake_list)
    result = asyncio.run(prices.resolve_company_names_batch({
        "台股": ["2330"],
        "美股": ["NVDA"],
        "爸媽美股": ["NVDA"],
    }))

    assert calls["list"] == 1
    assert result["台股"]["2330"] == "台積電"
    assert result["美股"]["NVDA"] == "NVIDIA"
    assert result["爸媽美股"]["NVDA"] == "NVIDIA"


def test_rebuild_writes_all_caches_in_one_batch(monkeypatch):
    captured = {"writes": 0, "keys": set()}

    async def fake_summary(refresh_prices, collect):
        collect["by_account"] = {
            account: {"tickers": [], "fifo": {}, "prices": {}}
            for account in jobs.ACCOUNTS
        }
        collect.update({"usd_rate": 30, "manual_rows": {}, "cash_rows": [], "context": None})
        return {"accounts": {}, "usd_rate": 30}

    async def fake_names(tickers_by_account, fugle_key):
        return {account: {} for account in tickers_by_account}

    async def fake_portfolio(account, working, company_names):
        return {"account": account, "holdings": [], "dashboard": {}}

    def fake_upsert(payloads):
        captured["writes"] += 1
        captured["keys"] = set(payloads)
        return "2026-08-06T00:00:00+00:00"

    monkeypatch.setattr(summary, "calculate_summary", fake_summary)
    monkeypatch.setattr(portfolio, "portfolio_from_working_set", fake_portfolio)
    monkeypatch.setattr(jobs, "resolve_company_names_batch", fake_names)
    monkeypatch.setattr(jobs, "upsert_summary_caches", fake_upsert)

    result = asyncio.run(jobs.rebuild_all_caches(refresh_prices=False))

    assert captured["writes"] == 1
    assert captured["keys"] == {
        "main", "portfolio:台股", "portfolio:美股", "portfolio:爸媽美股",
    }
    assert set(result["portfolios"]) == set(jobs.ACCOUNTS)
