from database import get_supabase


MANUAL_INVESTMENTS_MISSING = "manual_investments table is missing. Run backend/sql/migrations/20260511_manual_investments.sql in Supabase SQL Editor."


def is_missing_manual_investments_error(exc: Exception) -> bool:
    message = str(exc)
    return "manual_investments" in message and ("PGRST205" in message or "Could not find the table" in message)


def list_manual_values() -> list[dict]:
    response = get_supabase().table("manual_values").select("*").execute()
    return response.data or []


def upsert_manual_value(key: str, value: float) -> dict:
    response = (
        get_supabase()
        .table("manual_values")
        .upsert({"key": key, "value": value}, on_conflict="key")
        .execute()
    )
    return response.data[0] if response.data else {"key": key, "value": value}


def list_cash_accounts() -> list[dict]:
    response = get_supabase().table("cash_accounts").select("*").order("name").execute()
    return response.data or []


def update_cash(cash_id: str, amount: float, currency: str | None = None) -> dict:
    payload = {"amount": amount}
    if currency:
        payload["currency"] = currency
    response = (
        get_supabase()
        .table("cash_accounts")
        .update(payload)
        .eq("id", cash_id)
        .execute()
    )
    return response.data[0] if response.data else {"id": cash_id, **payload}


def create_cash(payload: dict) -> dict:
    attempted_payload = dict(payload)
    optional_columns = ["account", "category"]

    for _ in range(len(optional_columns) + 1):
        try:
            response = get_supabase().table("cash_accounts").insert(attempted_payload).execute()
            return response.data[0] if response.data else attempted_payload
        except Exception as exc:
            message = str(exc)
            removed = False
            for column in optional_columns:
                if column in attempted_payload and f"'{column}' column" in message:
                    attempted_payload.pop(column)
                    removed = True
                    break
            if not removed:
                raise

    response = get_supabase().table("cash_accounts").insert(attempted_payload).execute()
    return response.data[0] if response.data else attempted_payload


def adjust_cash_balance(name: str, currency: str, delta: float) -> dict:
    response = (
        get_supabase()
        .table("cash_accounts")
        .select("*")
        .eq("name", name)
        .eq("currency", currency)
        .limit(1)
        .execute()
    )
    row = response.data[0] if response.data else None
    if row:
        amount = float(row.get("amount") or 0) + delta
        return update_cash(row["id"], amount, currency)

    if delta <= 0:
        return {"name": name, "currency": currency, "amount": 0}
    return create_cash({"name": name, "account": "", "category": "現金", "currency": currency, "amount": delta})


def list_manual_investments() -> list[dict]:
    try:
        response = get_supabase().table("manual_investments").select("*").order("name").execute()
        return response.data or []
    except Exception:
        values = {row["key"]: float(row["value"]) for row in list_manual_values()}
        return [
            {
                "id": "legacy-morgan",
                "name": "摩根新興科技",
                "asset_type": "其他",
                "cost": values.get("morgan_cost", 74000),
                "value": values.get("morgan_value", 0),
                "currency": "TWD",
            },
            {
                "id": "legacy-nomura",
                "name": "野村高科技",
                "asset_type": "其他",
                "cost": values.get("nomura_cost", 47500),
                "value": values.get("nomura_value", 0),
                "currency": "TWD",
            },
            {
                "id": "legacy-crypto",
                "name": "加密貨幣",
                "asset_type": "其他",
                "cost": values.get("crypto_cost", 68785),
                "value": values.get("crypto_value", 0),
                "currency": "TWD",
            },
        ]


def create_manual_investment(payload: dict) -> dict:
    try:
        response = get_supabase().table("manual_investments").insert(payload).execute()
    except Exception as exc:
        if is_missing_manual_investments_error(exc):
            raise RuntimeError(MANUAL_INVESTMENTS_MISSING) from exc
        raise
    return response.data[0] if response.data else payload


def update_manual_investment(investment_id: str, payload: dict) -> dict:
    clean = {key: value for key, value in payload.items() if value is not None}
    try:
        response = (
            get_supabase()
            .table("manual_investments")
            .update(clean)
            .eq("id", investment_id)
            .execute()
        )
    except Exception as exc:
        if is_missing_manual_investments_error(exc):
            raise RuntimeError(MANUAL_INVESTMENTS_MISSING) from exc
        raise
    return response.data[0] if response.data else {"id": investment_id, **clean}


def delete_manual_investment(investment_id: str) -> None:
    try:
        get_supabase().table("manual_investments").delete().eq("id", investment_id).execute()
    except Exception as exc:
        if is_missing_manual_investments_error(exc):
            raise RuntimeError(MANUAL_INVESTMENTS_MISSING) from exc
        raise


def list_capital_movements() -> list[dict]:
    try:
        response = get_supabase().table("capital_movements").select("*").order("movement_date", desc=True).execute()
        return response.data or []
    except Exception:
        return []


def create_capital_movement(payload: dict) -> dict:
    response = get_supabase().table("capital_movements").insert(payload).execute()
    return response.data[0] if response.data else payload


def list_capital_movement_options(category: str) -> list[dict]:
    try:
        response = (
            get_supabase()
            .table("capital_movement_options")
            .select("*")
            .eq("category", category)
            .order("label")
            .execute()
        )
        return response.data or []
    except Exception:
        return []


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
