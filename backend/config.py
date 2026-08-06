from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_key: str = ""
    finnhub_key: str = ""
    fugle_api_key: str = ""
    cors_origins: str = ""
    cron_secret: str = ""

    # --- A1 認證 ---
    app_password_hash: str = ""
    jwt_secret: str = ""
    jwt_expire_days: int = 30
    # 只在本機開發時設為 true，會完全關閉 API 驗證
    auth_disabled: bool = False

    # --- 報價快取 ---
    # 刷新時，價格快取若比這個秒數還新就直接沿用，不打外部 API。
    # ⚠ 這個值是「實際更新頻率」的下限：
    #    cron 設每 5 分鐘、但 TTL 是 600 秒的話，實際上仍然 10 分鐘才更新一次。
    #    要更即時就把兩者一起調小。
    price_refresh_ttl_seconds: int = 600
    rate_refresh_ttl_seconds: int = 3600

    # --- A4 FIFO checkpoint ---
    # 結算間隔（小時）；只在這段期間內有交易異動時才重新結算
    fifo_settle_interval_hours: int = 12
    # checkpoint 只結算到「今天 - N 天」，讓近期交易留在可隨時重算的熱區
    fifo_checkpoint_lag_days: int = 1

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def finnhub_ready(self) -> bool:
        return bool(self.finnhub_key)

    @property
    def fugle_ready(self) -> bool:
        return bool(self.fugle_api_key)

    @property
    def auth_ready(self) -> bool:
        # JWT_SECRET 太短會讓 HS256 簽章強度不足，直接視為未設定
        return bool(self.app_password_hash) and len(self.jwt_secret) >= 32

    @property
    def allowed_origins(self) -> list[str]:
        """未設定時回傳空清單（等同只允許同源），避免不小心留下 '*'。"""
        raw = self.cors_origins.strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
