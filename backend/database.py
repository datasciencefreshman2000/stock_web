from functools import lru_cache

from fastapi import HTTPException
from supabase import Client, create_client

from config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_ready:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.",
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)
