from datetime import datetime, timezone

from database import get_supabase


SUMMARY_CACHE_KEY = "main"
PORTFOLIO_CACHE_PREFIX = "portfolio:"
SUMMARY_CACHE_TABLE_MISSING_MESSAGES = (
    "summary_cache",
    "PGRST205",
    "PGRST204",
    "Could not find the table",
    "Could not find the 'summary_cache'",
    "schema cache",
)


def portfolio_cache_key(account: str) -> str:
    return f"{PORTFOLIO_CACHE_PREFIX}{account}"


def app_cache_keys() -> list[str]:
    from services.accounts import ACCOUNTS

    return [SUMMARY_CACHE_KEY, *[portfolio_cache_key(account) for account in [*ACCOUNTS, "x"]]]


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


def get_summary_caches(cache_keys: list[str]) -> dict[str, dict]:
    """一次讀多把快取。

    先前 cache_patch 是「summary 讀一次、三個帳戶各讀一次」，
    再加上 patch_summary_cache 內部又各讀一次，光是快取的讀取就 8 次往返。
    Supabase 一次 in_() 就能全部拿回來。
    """
    if not cache_keys:
        return {}
    try:
        response = (
            get_supabase()
            .table("summary_cache")
            .select("cache_key,payload,updated_at")
            .in_("cache_key", cache_keys)
            .execute()
        )
    except Exception as exc:
        if is_summary_cache_missing_error(exc):
            return {}
        raise

    result: dict[str, dict] = {}
    for row in response.data or []:
        payload = row.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        payload["summary_cached"] = True
        payload["summary_cached_at"] = row.get("updated_at")
        result[row["cache_key"]] = payload
    return result


def upsert_summary_caches(payloads: dict[str, dict]) -> str | None:
    """一次寫多把快取，回傳 updated_at。

    同上：四把快取分四次 upsert 是沒必要的，upsert 本來就吃陣列。
    """
    if not payloads:
        return None
    updated_at = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "cache_key": cache_key,
            "payload": {k: v for k, v in payload.items() if k not in {"summary_cached", "summary_cached_at"}},
            "updated_at": updated_at,
        }
        for cache_key, payload in payloads.items()
    ]
    try:
        get_supabase().table("summary_cache").upsert(rows, on_conflict="cache_key").execute()
    except Exception as exc:
        if is_summary_cache_missing_error(exc):
            return None
        raise
    return updated_at


def patch_summary_cache(patch: dict, cache_key: str = SUMMARY_CACHE_KEY) -> dict | None:
    """就地更新單一把快取。

    ⚠ 這個函式一次呼叫 = 2 次 DB 往返（內部先 get 再 upsert）。
      要動好幾把快取時**不要**在迴圈裡呼叫它 ——
      改用 get_summary_caches() / upsert_summary_caches() 批次處理。
      這個教訓來自 services/cache_patch.py，見 docs/performance_audit.md 第八節。

    只在快取已存在時作用；沒有快取就回傳 None，由呼叫端決定要不要重算。
    """
    cached = get_summary_cache(cache_key)
    if not cached:
        return None
    cached.update(patch)
    return upsert_summary_cache(cached, cache_key)


def clear_summary_cache(cache_key: str | None = None) -> None:
    try:
        query = get_supabase().table("summary_cache").delete()
        if cache_key:
            query = query.eq("cache_key", cache_key)
        else:
            query = query.in_("cache_key", app_cache_keys())
        query.execute()
    except Exception as exc:
        if is_summary_cache_missing_error(exc):
            return
        raise
