from datetime import datetime, timezone
from secrets import compare_digest

from fastapi import APIRouter, Header, HTTPException

from config import get_settings
from repositories.snapshots import normalize_snapshot_time, upsert_snapshots
from repositories.summary_cache import upsert_summary_cache
from services.prices import get_price_status

router = APIRouter()


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
    snapshot_at = normalize_snapshot_time(datetime.now(timezone.utc))
    rows = upsert_snapshots(cached, snapshot_at)
    return {
        "ok": True,
        "snapshot_at": snapshot_at.isoformat(),
        "snapshot_date": snapshot_at.date().isoformat(),
        "snapshot_hour": snapshot_at.hour,
        "rows": len(rows),
        "summary_cached_at": cached.get("summary_cached_at"),
        "price_status": get_price_status(),
    }
