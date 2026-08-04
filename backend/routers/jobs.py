"""排程與手動刷新。

A3：這裡是系統中唯一負責「抓價 + 重算 + 寫快取」的地方。
所有 GET 端點都只讀快取，不做任何刷新。

接受 X-Cron-Secret（Cloudflare Worker）或使用者 JWT（前端刷新按鈕）。
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from dependencies import require_auth_or_cron
from repositories.job_runs import get_job_run, record_job_run
from repositories.snapshots import normalize_snapshot_time, snapshot_taipei_parts, upsert_snapshots
from repositories.trades import latest_trade_change_at, list_trades
from services.accounts import ACCOUNTS
from services.settlement import checkpoint_boundary, settle_account, should_settle

router = APIRouter()

SETTLE_JOB = "fifo_settle"


async def _refresh_all(refresh_prices: bool) -> dict:
    from routers.portfolio import refresh_portfolio_cache
    from routers.summary import refresh_summary_cache

    summary = await refresh_summary_cache(refresh_prices=refresh_prices)
    portfolios = []
    for account in ACCOUNTS:
        # summary 已經把最新報價寫進 price_cache，各帳戶不必再打一次外部 API
        cached = await refresh_portfolio_cache(account, refresh_prices=False)
        portfolios.append(
            {"account": account, "summary_cached_at": (cached or {}).get("summary_cached_at")}
        )
    return {"summary": summary, "portfolios": portfolios}


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
