from database import fetch_all, get_supabase


def list_manual_values() -> list[dict]:
    response = get_supabase().table("manual_values").select("*").execute()
    return response.data or []


def list_balance_adjustments(start: str, end: str) -> list[dict]:
    rows = fetch_all(lambda: get_supabase().table("balance_adjustments").select("*")
        .gte("created_at", start + "T00:00:00+08:00").lt("created_at", end + "T00:00:00+08:00")
        .order("created_at", desc=True).order("id", desc=True))
    cash = {row["id"]: row for row in list_cash_accounts()}
    for row in rows:
        source = cash.get(row["record_key"], {})
        row["name"] = source.get("name") or row["record_key"].removeprefix("invested_")
        row["currency"] = source.get("currency") or ("USD" if row["name"] in {"美股", "爸媽美股"} else "TWD")
    return rows


def list_cash_accounts() -> list[dict]:
    response = get_supabase().table("cash_accounts").select("*").is_("archived_at", "null").order("name").execute()
    return response.data or []


def list_manual_investments() -> list[dict]:
    response = get_supabase().table("manual_investments").select("*").order("name").execute()
    return response.data or []


def list_capital_movements(start_date: str, end_date: str) -> list[dict]:
    def build():
        return (
            get_supabase()
            .table("capital_movements")
            .select("*")
            .gte("movement_date", start_date)
            .lt("movement_date", end_date)
            .order("movement_date", desc=True)
            .order("created_at", desc=True)
        )

    return fetch_all(build)


def get_capital_movement(movement_id: str) -> dict | None:
    response = (
        get_supabase()
        .table("capital_movements")
        .select("*")
        .eq("id", movement_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def list_capital_movement_options(category: str) -> list[dict]:
    return get_supabase().table("capital_movement_options").select("*").eq("category", category).order("label").execute().data or []


def create_capital_movement_option(payload: dict) -> dict:
    response = (
        get_supabase()
        .table("capital_movement_options")
        .upsert(payload, on_conflict="category,label")
        .execute()
    )
    return response.data[0] if response.data else payload


def delete_capital_movement_option(option_id: str) -> None:
    get_supabase().table("capital_movement_options").delete().eq("id", option_id).execute()
