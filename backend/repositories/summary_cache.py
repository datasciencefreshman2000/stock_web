from datetime import datetime, timezone

from database import get_supabase


SUMMARY_CACHE_KEY = "main"


def get_summary_cache(cache_key: str = SUMMARY_CACHE_KEY) -> dict | None:
    response = (
        get_supabase()
        .table("summary_cache")
        .select("payload,updated_at")
        .eq("cache_key", cache_key)
        .limit(1)
        .execute()
    )
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
    row = response.data[0] if response.data else {"payload": clean_payload, "updated_at": updated_at}
    cached = row.get("payload") or clean_payload
    cached["summary_cached"] = False
    cached["summary_cached_at"] = row.get("updated_at", updated_at)
    return cached


def clear_summary_cache(cache_key: str = SUMMARY_CACHE_KEY) -> None:
    get_supabase().table("summary_cache").delete().eq("cache_key", cache_key).execute()
