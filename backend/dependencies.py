"""FastAPI 相依性：API 驗證。

預設 fail closed —— 若 APP_PASSWORD_HASH / JWT_SECRET 未設定，API 直接回 503，
而不是放行。本機開發可設 AUTH_DISABLED=true 關閉。
"""

from secrets import compare_digest

import jwt
from fastapi import Header, HTTPException

from config import get_settings
from services.auth import decode_token


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def require_auth(authorization: str | None = Header(default=None)) -> dict:
    """一般 API 使用：需要有效的使用者 JWT。"""
    settings = get_settings()
    if settings.auth_disabled:
        return {"sub": "dev", "auth": "disabled"}

    if not settings.auth_ready:
        raise HTTPException(
            status_code=503,
            detail="Auth is not configured. Set APP_PASSWORD_HASH and JWT_SECRET.",
        )

    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    try:
        return decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.") from None
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token.") from None


def require_auth_or_cron(
    authorization: str | None = Header(default=None),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict:
    """排程端點使用：接受 cron secret 或使用者 JWT。"""
    settings = get_settings()

    if x_cron_secret:
        if not settings.cron_secret:
            raise HTTPException(status_code=503, detail="CRON_SECRET is not configured.")
        if not compare_digest(x_cron_secret, settings.cron_secret):
            raise HTTPException(status_code=403, detail="Invalid cron secret.")
        return {"sub": "cron", "auth": "cron"}

    return require_auth(authorization)
