from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import actions, auth, jobs, manual, portfolio, summary, trades

settings = get_settings()
app = FastAPI(title="stock_web API")

# CORS_ORIGINS 未設定時 allowed_origins 為空清單，等同只允許同源。
# 前後端部署在同一個 Vercel 專案，正常情況不需要放寬。
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(summary.router, prefix="/api", tags=["summary"])
app.include_router(manual.router, prefix="/api/manual", tags=["manual"])
app.include_router(actions.router, prefix="/api/actions", tags=["corporate-actions"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


@app.get("/api/health")
def health() -> dict:
    """不需要驗證，只回報設定是否齊全，不洩漏任何資料。"""
    return {
        "ok": True,
        "supabase_configured": settings.supabase_ready,
        "finnhub_configured": settings.finnhub_ready,
        "fugle_configured": settings.fugle_ready,
        "cron_configured": bool(settings.cron_secret),
        "auth_configured": settings.auth_ready,
        "auth_disabled": settings.auth_disabled,
    }
