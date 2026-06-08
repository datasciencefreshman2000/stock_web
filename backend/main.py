from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import jobs, manual, portfolio, summary, trades
from services.prices import get_price_status

settings = get_settings()
app = FastAPI(title="stock_web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(summary.router, prefix="/api", tags=["summary"])
app.include_router(manual.router, prefix="/api/manual", tags=["manual"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "supabase_configured": settings.supabase_ready,
        "finnhub_configured": settings.finnhub_ready,
        "fugle_configured": settings.fugle_ready,
        "cron_configured": bool(settings.cron_secret),
    }


@app.get("/api/prices/status")
def price_status() -> dict:
    return get_price_status()
