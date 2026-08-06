"""總覽。

A3 修正：GET 端點一律只讀快取，不再用 BackgroundTasks 在回應後刷新
（serverless function 回傳後可能立刻凍結，背景任務會做到一半就死掉，
狀態機還會卡在 in_progress）。刷新責任全部交給 POST /api/jobs/refresh。
"""

from fastapi import APIRouter, Depends

from config import get_settings
from dependencies import require_auth
from repositories.fifo_checkpoints import list_latest_checkpoints_for_accounts
from repositories.manual import list_cash_accounts, list_manual_investments, list_manual_values
from repositories.summary_cache import get_summary_cache, upsert_summary_cache
from repositories.trades import list_trades
from services.accounts import (
    ACCOUNTS,
    EXTERNAL_ACCOUNTS,
    OWN_ACCOUNTS,
    cash_summary,
    enrich_account_summary,
    invested_key,
)
from services.calculator import active_tickers, build_holdings_from_results, summarize_account_from_results
from services.constants import MANUAL_COSTS
from services.prices import PriceContext, fetch_prices_batch, fetch_usd_rate, get_price_status
from services.settlement import (
    analyze_account,
    checkpoint_boundary,
    group_by_ticker,
    load_reference_data_for_symbols,
)
from services.symbols import is_tw_account, symbol_for

router = APIRouter()


def filter_known_accounts(payload: dict | None) -> dict:
    result = dict(payload or {})
    for key in ("accounts", "invested"):
        if isinstance(result.get(key), dict):
            result[key] = {a: row for a, row in result[key].items() if a in ACCOUNTS}
    if isinstance(result.get("cash"), dict) and isinstance(result["cash"].get("by_account"), dict):
        result["cash"] = {
            **result["cash"],
            "by_account": {a: row for a, row in result["cash"]["by_account"].items() if a in ACCOUNTS},
        }
    return result


def investment_amount_twd(row: dict, key: str, usd_rate: float) -> float:
    amount = float(row.get(key) or 0)
    return amount * usd_rate if (row.get("currency") or "TWD") == "USD" else amount


def enrich_manual_investment(row: dict, usd_rate: float) -> dict:
    cost_twd = investment_amount_twd(row, "cost", usd_rate)
    value_twd = investment_amount_twd(row, "value", usd_rate)
    cash_amount_twd = investment_amount_twd(row, "cash_amount", usd_rate)
    total_value_twd = value_twd + cash_amount_twd
    return {
        **row,
        "currency": row.get("currency") or "TWD",
        "cost_twd": cost_twd,
        "value_twd": value_twd,
        "cash_amount_twd": cash_amount_twd,
        "total_value_twd": total_value_twd,
        "pnl_twd": total_value_twd - cost_twd,
    }


async def calculate_summary(refresh_prices: bool = False, collect: dict | None = None) -> dict:
    """重算總覽。只有排程 / 手動刷新會用 refresh_prices=True 打外部 API。

    collect 傳入一個 dict 時，會把中途算好的東西留在裡面
    （每個帳戶的 FIFO 結果、報價、匯率、現金列、手動欄位）。

    為什麼要這樣：/jobs/refresh 先算 summary、再算三個 portfolio，
    但兩邊算的是**同一份 FIFO**。不共用的話等於每次排程都把
    全部交易跑兩遍，還多花 21 次 DB 往返。
    """
    settings = get_settings()
    context = PriceContext()
    usd_rate = await fetch_usd_rate(refresh=refresh_prices, context=context)

    manual_rows = {row["key"]: float(row["value"]) for row in list_manual_values()}

    # 一次讀完所有交易，在記憶體分組，避免每個帳戶各打一次 DB
    trades_by_account: dict[str, list[dict]] = {account: [] for account in ACCOUNTS}
    for trade in list_trades():
        if trade.get("account") in trades_by_account:
            trades_by_account[trade["account"]].append(trade)

    boundary = checkpoint_boundary()
    checkpoints_by_account = list_latest_checkpoints_for_accounts(ACCOUNTS, boundary)
    tickers_by_account_all = {
        account: sorted(group_by_ticker(trades_by_account[account]).keys())
        for account in ACCOUNTS
    }
    # 一次把全部帳戶的參考資料讀完（先前是每帳戶 2 次，共 6 次）
    actions_by_symbol, etf_symbols = load_reference_data_for_symbols(
        [symbol_for(a, t) for a, ts in tickers_by_account_all.items() for t in ts]
    )

    fifo_by_account: dict[str, dict] = {}
    tickers_by_account: dict[str, list[str]] = {}
    all_symbols: list[str] = []

    for account in ACCOUNTS:
        tickers = tickers_by_account_all[account]
        if tickers:
            results = analyze_account(
                account,
                trades_by_account[account],
                checkpoints=checkpoints_by_account.get(account),
                actions_by_symbol=actions_by_symbol,
                etf_symbols=etf_symbols,
            )
        else:
            results = {}
        fifo_by_account[account] = results
        active = active_tickers(results)
        tickers_by_account[account] = active
        all_symbols.extend(symbol_for(account, t) for t in active)

    context.preload(sorted(set(all_symbols)))

    accounts: dict[str, dict] = {}
    own_account_total = 0.0
    external_account_total = 0.0

    for account in ACCOUNTS:
        provider_ready = settings.fugle_ready if is_tw_account(account) else settings.finnhub_ready
        prices = (
            await fetch_prices_batch(
                tickers_by_account[account],
                account,
                settings.finnhub_key,
                refresh=refresh_prices,
                fugle_key=settings.fugle_api_key,
                context=context,
            )
            if provider_ready
            else {}
        )
        holdings = build_holdings_from_results(fifo_by_account[account], prices)
        summary = summarize_account_from_results(fifo_by_account[account], holdings)
        enrich_account_summary(summary, account, usd_rate, manual_rows.get(invested_key(account)))
        accounts[account] = summary
        if collect is not None:
            collect.setdefault("by_account", {})[account] = {
                "fifo": fifo_by_account[account],
                "prices": prices,
                "tickers": tickers_by_account[account],
            }
        if account in OWN_ACCOUNTS:
            own_account_total += summary["account_total_twd"]
        if account in EXTERNAL_ACCOUNTS:
            external_account_total += summary["account_total_twd"]

    manual = {
        "morgan_cost": manual_rows.get("morgan_cost", MANUAL_COSTS["morgan"]),
        "morgan_value": manual_rows.get("morgan_value", 0),
        "nomura_cost": manual_rows.get("nomura_cost", MANUAL_COSTS["nomura"]),
        "nomura_value": manual_rows.get("nomura_value", 0),
        "crypto_cost": manual_rows.get("crypto_cost", MANUAL_COSTS["crypto"]),
        "crypto_value": manual_rows.get("crypto_value", 0),
    }
    invested = {account: manual_rows.get(invested_key(account), 0) for account in ACCOUNTS}
    investments = [enrich_manual_investment(row, usd_rate) for row in list_manual_investments()]
    investment_total = sum(row["value_twd"] for row in investments)
    manual_investment_cash_total = sum(row["cash_amount_twd"] for row in investments)

    cash_rows = list_cash_accounts()
    cash = cash_summary(cash_rows, usd_rate)
    cash["by_account"] = {a: cash_summary(cash_rows, usd_rate, a) for a in ACCOUNTS}
    own_cash_rows = [r for r in cash_rows if not r.get("account") or r.get("account") in OWN_ACCOUNTS]
    own_cash_total = cash_summary(own_cash_rows, usd_rate)["twd_equivalent"]
    external_cash_total = sum(cash["by_account"][a]["twd_equivalent"] for a in EXTERNAL_ACCOUNTS)

    own_total = own_account_total + investment_total + manual_investment_cash_total + own_cash_total

    if collect is not None:
        collect.update({"usd_rate": usd_rate, "manual_rows": manual_rows,
                        "cash_rows": cash_rows, "context": context})

    return {
        "usd_rate": usd_rate,
        "accounts": accounts,
        "manual": manual,
        "investments": investments,
        "investment_total": investment_total,
        "manual_investment_cash_total": manual_investment_cash_total,
        "invested": invested,
        "cash": cash,
        "total_assets": own_total,
        "own_total_assets": own_total,
        "external_total_assets": external_account_total + external_cash_total,
        "price_status": get_price_status(context),
    }


async def refresh_summary_cache(refresh_prices: bool = True) -> dict:
    return upsert_summary_cache(await calculate_summary(refresh_prices=refresh_prices))


@router.get("/summary")
async def get_summary(_: dict = Depends(require_auth)) -> dict:
    """只讀快取。快取不存在時就地重算（不打外部報價 API）。

    重算時**連三個帳戶的持倉快取一起建好**。理由：
    交易異動會把四把快取一起清掉，接下來使用者不管切到哪一頁都會
    踩到空快取。各自重建的話同一份 FIFO 會被算好幾遍。
    """
    cached = get_summary_cache()
    if cached:
        return filter_known_accounts(cached)

    from routers.jobs import rebuild_all_caches

    result = await rebuild_all_caches(refresh_prices=False)
    return filter_known_accounts(result["summary"])
