from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from dependencies import require_auth
from models import LoginRequest
from services.auth import create_token, verify_password

router = APIRouter()


@router.post("/login")
def login(payload: LoginRequest) -> dict:
    settings = get_settings()
    if not settings.auth_ready:
        raise HTTPException(
            status_code=503,
            detail="Auth is not configured. Set APP_PASSWORD_HASH and JWT_SECRET.",
        )

    # pbkdf2 本身約 100ms，足以作為暴力破解的節流
    if not verify_password(payload.password, settings.app_password_hash):
        raise HTTPException(status_code=401, detail="密碼錯誤")

    token, expires_at = create_token()
    return {"token": token, "expires_at": expires_at.isoformat()}


@router.get("/me")
def me(claims: dict = Depends(require_auth)) -> dict:
    return {"ok": True, "sub": claims.get("sub"), "exp": claims.get("exp")}
