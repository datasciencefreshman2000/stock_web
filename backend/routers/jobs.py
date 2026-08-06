"""排程與手動刷新。

A3：這裡是系統中唯一負責「抓價 + 重算 + 寫快取」的地方。
所有 GET 端點都只讀快取，不做任何刷新。

接受 X-Cron-Secret（Cloudflare Worker）或使用者 JWT（前端刷新按鈕）。
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from config import get_settings
from dependencies import require_auth_or_cron
from repositories.job_runs import get_job_run, record_job_run
from repositories.snapshots import normalize_snapshot_time, snapshot_taipei_parts, upsert_snapshots
from repositories.summary_cache import SUMMARY_CACHE_KEY, portfolio_cache_key, upsert_summary_caches
from repositories.trades import latest_trade_change_at, list_trades
from services.accounts import ACCOUNTS
from services.prices import resolve_company_names_batch
from services.settlement import checkpoint_boundary, settle_account, should_settle

router = APIRouter()

SETTLE_JOB = "fifo_settle"


async def rebuild_all_caches(refresh_prices: bool) -> dict:
    """把 summary 與三個帳戶的持倉快取一次全部重建。

    兩個重點：

    1. **只跑一次 FIFO。** 先前是 summary 算完 FIFO，三個 portfolio
       再各自把同一份 FIFO 重算一次 —— 整批交易被跑了兩遍。
       `working` 就是用來把中間結果傳下去的。

    2. **這個函式也給 GET 用。** 交易異動會清掉全部四把快取，
       如果每個 GET 各自重建自己那一把，使用者改一筆交易之後
       載入總覽 + 三個持倉頁要 41 次往返、FIFO 跑兩遍。
       改成「第一個發現快取不在的 GET 就把四把全部建好」，降到 17 次。

    回傳 {"summary": payload, "portfolios": {account: payload}}。
    """
    from routers.portfolio import portfolio_from_working_set
    from routers.summary import calculate_summary

    working: dict = {}
    summary = await calculate_summary(refresh_prices=refresh_prices, collect=working)
    company_names = await resolve_company_names_batch(
        {
            account: working["by_account"][account]["tickers"]
            for account in ACCOUNTS
        },
        get_settings().fugle_api_key,
    )
    portfolios = {
        account: await portfolio_from_working_set(
            account, working, company_names=company_names.get(account, {})
        )
        for account in ACCOUNTS
    }
    updated_at = upsert_summary_caches({
        SUMMARY_CACHE_KEY: summary,
        **{portfolio_cache_key(account): payload for account, payload in portfolios.items()},
    })
    for payload in [summary, *portfolios.values()]:
        payload["summary_cached"] = False
        payload["summary_cached_at"] = updated_at
    return {"summary": summary, "portfolios": portfolios}


async def _refresh_all(refresh_prices: bool) -> dict:
    result = await rebuild_all_caches(refresh_prices)
    return {
        "summary": result["summary"],
        "portfolios": [
            {"account": account, "summary_cached_at": (payload or {}).get("summary_cached_at")}
            for account, payload in result["portfolios"].items()
        ],
    }


@router.post("/refresh")
async def refresh_all(_: dict = Depends(require_auth_or_cron)) -> dict:
    try:
        result = await _refresh_all(refresh_prices=True)
    except Exception as exc:
        record_job_run("refresh", ok=False, error=f"{type(exc).__name__}: {exc}")
        raise

    record_job_run("refresh", ok=True)
    return {
        "ok": True,
        "summary_cached_at": result["summary"].get("summary_cached_at"),
        "portfolios": result["portfolios"],
    }


@router.post("/snapshot")
async def snapshot_all(_: dict = Depends(require_auth_or_cron)) -> dict:
    try:
        result = await _refresh_all(refresh_prices=True)
        summary = result["summary"]
        snapshot_at = normalize_snapshot_time(datetime.now(timezone.utc))
        snapshot_date_taipei, snapshot_hour_taipei = snapshot_taipei_parts(snapshot_at)
        rows = upsert_snapshots(summary, snapshot_at)
    except Exception as exc:
        record_job_run("snapshot", ok=False, error=f"{type(exc).__name__}: {exc}")
        raise

    record_job_run("snapshot", ok=True)
    return {
        "ok": True,
        "snapshot_at": snapshot_at.isoformat(),
        "snapshot_date": snapshot_at.date().isoformat(),
        "snapshot_hour": snapshot_at.hour,
        "snapshot_date_taipei": snapshot_date_taipei,
        "snapshot_hour_taipei": snapshot_hour_taipei,
        "rows": len(rows),
        "summary_cached_at": summary.get("summary_cached_at"),
    }


@router.post("/settle")
def settle_fifo(force: bool = False, _: dict = Depends(require_auth_or_cron)) -> dict:
    """A4：每 12 小時結算一次 FIFO，但只在這段期間有交易異動時才做。"""
    last_run = get_job_run(SETTLE_JOB)
    last_run_at = (last_run or {}).get("last_ok_at")
    latest_change = latest_trade_change_at()

    if not force and not should_settle(last_run_at, latest_change):
        return {
            "ok": True,
            "skipped": True,
            "reason": "距上次結算未滿間隔，或期間內無交易異動",
            "last_ok_at": last_run_at,
            "latest_trade_change_at": latest_change,
        }

    as_of_date = checkpoint_boundary()
    written: dict[str, int] = {}
    try:
        for account in ACCOUNTS:
            written[account] = settle_account(account, list_trades(account), as_of_date)
    except Exception as exc:
        record_job_run(SETTLE_JOB, ok=False, error=f"{type(exc).__name__}: {exc}")
        raise

    record_job_run(SETTLE_JOB, ok=True, payload={"as_of_date": as_of_date, "written": written})
    return {"ok": True, "skipped": False, "as_of_date": as_of_date, "written": written}


@router.get("/status")
def job_status(_: dict = Depends(require_auth_or_cron)) -> dict:
    return {
        "jobs": {name: get_job_run(name) for name in ("refresh", "snapshot", SETTLE_JOB)},
        "latest_trade_change_at": latest_trade_change_at(),
        "next_checkpoint_date": checkpoint_boundary(),
    }
