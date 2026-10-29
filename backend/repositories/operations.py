"""All user writes use one atomic, idempotent database function."""
from uuid import uuid4
from fastapi import HTTPException
from database import get_supabase


def get_data_revision() -> int:
    result = get_supabase().rpc("app_data_revision", {}).execute().data
    return int(result)


def operation_exists(operation_id: str) -> bool:
    # Replay still goes through the RPC, which checks the original request body.
    return bool(get_supabase().table('app_operations').select('operation_id')
                .eq('operation_id', operation_id).limit(1).execute().data)


def atomic_write(action: str, payload: dict | None = None, *, record_id: str | None = None,
                 operation_id: str | None = None, revision: int | None = None,
                 effects: list[dict] | None = None) -> dict:
    data = dict(payload or {})
    op_id = operation_id or str(data.pop("operation_id", None) or uuid4())
    try:
        response = get_supabase().rpc("apply_app_operation", {
            "p_action": action, "p_payload": data, "p_record_id": record_id,
            "p_operation_id": op_id, "p_expected_revision": revision,
            "p_effects": effects or [],
        }).execute()
    except Exception as exc:
        code = str(getattr(exc, "code", ""))
        if code == "P0002":
            raise HTTPException(404, "資料不存在或已刪除，請重新整理。") from exc
        if code in {"40001", "23505"}:
            raise HTTPException(409, "資料已更新，請重新讀取後再試；相同操作重試不會重複入帳。") from exc
        if code in {"22023", "23514"}:
            raise HTTPException(400, getattr(exc, "message", "金額、幣別或帳戶不正確。")) from exc
        if code in {"PGRST202", "42P01", "42703"}:
            raise HTTPException(503, "資料庫尚未完成帳務升級，請先執行 README 的 migration 步驟。") from exc
        raise
    return response.data
