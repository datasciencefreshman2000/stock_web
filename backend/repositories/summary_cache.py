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
    return get_supabase().rpc("read_app_cache", {"p_key": cache_key}).execute().data


def upsert_summary_cache(payload: dict, cache_key: str = SUMMARY_CACHE_KEY) -> dict:
    stamp = upsert_summary_caches({cache_key: payload}, revision=payload["data_revision"])
    return {**payload, "summary_cached": False, "summary_cached_at": stamp}


def get_summary_caches(cache_keys: list[str]) -> dict[str, dict]:
    if not cache_keys:
        return {}
    return get_supabase().rpc("read_app_caches", {"p_keys": cache_keys}).execute().data or {}


def upsert_summary_caches(payloads: dict[str, dict], revision: int | None = None) -> str | None:
    """一次寫多把快取，回傳 updated_at。

    同上：四把快取分四次 upsert 是沒必要的，upsert 本來就吃陣列。
    """
    if not payloads:
        return None
    if revision is None:
        versions = {value.get("data_revision") for value in payloads.values()}
        if None in versions or len(versions) != 1:
            raise ValueError("快取缺少一致的資料版本，拒絕發布。")
        revision = versions.pop()
    stamp = get_supabase().rpc("publish_app_caches", {"p_revision": revision, "p_payloads": payloads}).execute().data
    if not stamp:
        raise CacheRevisionChanged("資料在重算期間更新，請重試。")
    return stamp


class CacheRevisionChanged(RuntimeError):
    pass


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
