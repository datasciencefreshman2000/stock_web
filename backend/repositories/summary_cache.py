from datetime import datetime, timezone

from database import get_supabase


SUMMARY_CACHE_KEY = "main"
SUMMARY_CACHE_TABLE_MISSING_MESSAGES = (
    "summary_cache",
    "PGRST205",
    "PGRST204",
    "Could not find the table",
    "Could not find the 'summary_cache'",
    "schema cache",
)


def is_summary_cache_missing_error(exc: Exception) -> bool:
    message = str(exc)
    return "summary_cache" in message and any(marker in message for marker in SUMMARY_CACHE_TABLE_MISSING_MESSAGES)


def get_summary_cache(cache_key: str = SUMMARY_CACHE_KEY) -> dict | None:
    try:
        response = (
            get_supabase()
            .table("summary_cache")
            .select("payload,updated_at")
            .eq("cache_key", cache_key)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        if is_summary_cache_missing_error(exc):
            return None
        raise
    if not response.data:
        return None

    row = response.data[0]
    payload = row.get("payload") or {}
    if isinstance(payload, dict):
        payload["summary_cached"] = True
        payload["summary_cached_at"] = row.get("updated_at")
    return payload


def upsert_summary_cache(payload: dict, cache_key: str = SUMMARY_CACHE_KEY) -> dict:
    updated_at = datetime.now(timezone.utc).isoformat()
    clean_payload = {key: value for key, value in payload.items() if key not in {"summary_cached", "summary_cached_at"}}
    try:
        response = (
            get_supabase()
            .table("summary_cache")
            .upsert(
                {
                    "cache_key": cache_key,
                    "payload": clean_payload,
                    "updated_at": updated_at,
                },
                on_conflict="cache_key",
            )
            .execute()
        )
    except Exception as exc:
        if is_summary_cache_missing_error(exc):
            fallback = dict(clean_payload)
            fallback["summary_cached"] = False
            fallback["summary_cached_at"] = None
            return fallback
        raise
    row = response.data[0] if response.data else {"payload": clean_payload, "updated_at": updated_at}
    cached = row.get("payload") or clean_payload
    cached["summary_cached"] = False
    cached["summary_cached_at"] = row.get("updated_at", updated_at)
    return cached


def clear_summary_cache(cache_key: str = SUMMARY_CACHE_KEY) -> None:
    try:
        get_supabase().table("summary_cache").delete().eq("cache_key", cache_key).execute()
    except Exception as exc:
        if is_summary_cache_missing_error(exc):
            return
        raise
