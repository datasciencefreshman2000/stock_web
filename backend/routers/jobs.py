from datetime import datetime, timedelta, timezone
from secrets import compare_digest

from fastapi import APIRouter, Header, HTTPException

from config import get_settings
from repositories.snapshots import upsert_daily_snapshots
from repositories.summary_cache import upsert_summary_cache
from services.prices import get_price_status

router = APIRouter()
TAIPEI_TZ = timezone(timedelta(hours=8))


def require_cron_secret(x_cron_secret: str | None) -> None:
    settings = get_settings()
    if not settings.cron_secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured.")
    if not x_cron_secret or not compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret.")


async def refresh_summary() -> dict:
    from routers.summary import calculate_summary

    summary = await calculate_summary(refresh_prices=True)
    return upsert_summary_cache(summary)


@router.post("/refresh")
async def refresh_all(x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret")) -> dict:
    require_cron_secret(x_cron_secret)
    cached = await refresh_summary()
    return {
        "ok": True,
        "summary_cached_at": cached.get("summary_cached_at"),
        "price_status": get_price_status(),
    }


@router.post("/snapshot")
async def snapshot_all(x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret")) -> dict:
    require_cron_secret(x_cron_secret)
    cached = await refresh_summary()
    snapshot_date = datetime.now(TAIPEI_TZ).date()
    rows = upsert_daily_snapshots(cached, snapshot_date)
    return {
        "ok": True,
        "snapshot_date": snapshot_date.isoformat(),
        "rows": len(rows),
        "summary_cached_at": cached.get("summary_cached_at"),
        "price_status": get_price_status(),
    }
