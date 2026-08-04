"""排程執行紀錄。取代原本存在記憶體的狀態機（serverless 下不可靠）。"""

from datetime import datetime, timezone

from database import get_supabase


def get_job_run(job_name: str) -> dict | None:
    response = (
        get_supabase()
        .table("job_runs")
        .select("*")
        .eq("job_name", job_name)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def record_job_run(job_name: str, ok: bool, error: str | None = None, payload: dict | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "job_name": job_name,
        "last_run_at": now,
        "last_error": error,
        "payload": payload or {},
        "updated_at": now,
    }
    if ok:
        row["last_ok_at"] = now
    response = get_supabase().table("job_runs").upsert(row, on_conflict="job_name").execute()
    return response.data[0] if response.data else row
