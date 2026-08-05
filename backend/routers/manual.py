from fastapi import APIRouter, Depends, HTTPException

from dependencies import require_auth
from models import CapitalMovementCreate, CapitalMovementOptionCreate, CapitalMovementUpdate, CashCreate, CashUpdate, ManualInvestmentCreate, ManualInvestmentUpdate, ManualValueUpdate
from repositories.manual import (
    list_cash_accounts,
    create_cash,
    create_capital_movement,
    create_capital_movement_option,
    create_manual_investment,
    delete_capital_movement,
    delete_capital_movement_option,
    delete_manual_investment,
    get_capital_movement,
    list_capital_movements,
    list_capital_movement_options,
    list_manual_values,
    list_manual_investments,
    update_capital_movement,
    update_manual_investment,
    update_cash,
    upsert_manual_value,
)
from repositories.summary_cache import clear_summary_cache
from services.accounts import ACCOUNTS, CASH_ACCOUNT_NAMES, invested_key

# 整個 router 都需要登入
router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("")
def get_manual() -> dict:
    return {"values": list_manual_values(), "cash": list_cash_accounts(), "investments": list_manual_investments()}


@router.patch("/value")
def patch_manual_value(update: ManualValueUpdate) -> dict:
    value = upsert_manual_value(update.key, update.value)
    clear_summary_cache()
    return {"success": True, "value": value}


@router.patch("/cash/{cash_id}")
def patch_cash(cash_id: str, update: CashUpdate) -> dict:
    cash = update_cash(cash_id, update.amount, update.currency)
    clear_summary_cache()
    return {"success": True, "cash": cash}


@router.post("/cash")
def add_cash(payload: CashCreate) -> dict:
    cash = create_cash(payload.model_dump())
    clear_summary_cache()
    return {"success": True, "cash": cash}


@router.post("/investment")
def add_investment(payload: ManualInvestmentCreate) -> dict:
    try:
        investment = create_manual_investment(payload.model_dump())
        clear_summary_cache()
        return {"success": True, "investment": investment}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/investment/{investment_id}")
def patch_investment(investment_id: str, payload: ManualInvestmentUpdate) -> dict:
    try:
        investment = update_manual_investment(investment_id, payload.model_dump())
        clear_summary_cache()
        return {"success": True, "investment": investment}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/investment/{investment_id}")
def remove_investment(investment_id: str) -> dict:
    try:
        delete_manual_investment(investment_id)
        clear_summary_cache()
        return {"success": True}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/capital-movements")
def get_capital_movements() -> dict:
    return {"movements": list_capital_movements()}


@router.get("/capital-movement-options")
def get_capital_movement_options(category: str = "income_source") -> dict:
    return {"options": list_capital_movement_options(category)}


@router.post("/capital-movement-options")
def add_capital_movement_option(payload: CapitalMovementOptionCreate) -> dict:
    return {"success": True, "option": create_capital_movement_option(payload.model_dump())}


@router.delete("/capital-movement-options/{option_id}")
def remove_capital_movement_option(option_id: str) -> dict:
    delete_capital_movement_option(option_id)
    return {"success": True}


@router.post("/capital-movements")
def add_capital_movement(payload: CapitalMovementCreate) -> dict:
    data = {key: value for key, value in payload.model_dump(mode="json").items() if value is not None}
    movement = create_capital_movement(data)
    try:
        apply_capital_movement_effect(data)
    except Exception:
        if movement.get("id"):
            delete_capital_movement(movement["id"])
        raise
    clear_summary_cache()
    return {"success": True, "movement": movement}


def movement_balance_effects(data: dict, cash_names: set[str], direction: float = 1) -> dict[tuple[str, str, str], float]:
    amount = float(data["amount"])
    currency = data.get("currency") or "TWD"
    to_amount = float(data.get("to_amount") or amount)
    to_currency = data.get("to_currency") or currency

    effects: dict[tuple[str, str, str], float] = {}

    def add(bucket: str | None, bucket_currency: str, delta: float) -> None:
        if bucket in ACCOUNTS:
            key = ("account", bucket, bucket_currency)
        elif bucket in cash_names:
            key = ("cash", bucket, bucket_currency)
        else:
            return
        effects[key] = effects.get(key, 0) + direction * delta

    add(data.get("to_bucket"), to_currency, to_amount)
    add(data.get("from_bucket"), currency, -amount)
    return {key: delta for key, delta in effects.items() if abs(delta) > 0.0000001}


def movement_balance_deltas(previous: dict | None, current: dict | None, cash_names: set[str]) -> dict[tuple[str, str, str], float]:
    deltas: dict[tuple[str, str, str], float] = {}
    for key, delta in (movement_balance_effects(previous, cash_names, direction=-1).items() if previous else []):
        deltas[key] = deltas.get(key, 0) + delta
    for key, delta in (movement_balance_effects(current, cash_names).items() if current else []):
        deltas[key] = deltas.get(key, 0) + delta
    return {key: delta for key, delta in deltas.items() if abs(delta) > 0.0000001}


def restore_balance_changes(changes: list[tuple[str, str, str, float]], cash_rows: list[dict], values: dict[str, float]) -> None:
    cash_map = {(row["name"], row.get("currency") or "TWD"): row for row in cash_rows}
    for kind, bucket, currency, old_value in reversed(changes):
        if kind == "account":
            key = invested_key(bucket)
            upsert_manual_value(key, old_value)
            values[key] = old_value
        else:
            row = cash_map.get((bucket, currency))
            if row:
                update_cash(row["id"], old_value, currency)
                row["amount"] = old_value


def apply_balance_deltas(deltas: dict[tuple[str, str, str], float], cash_rows: list[dict]) -> list[tuple[str, str, str, float]]:
    if not deltas:
        return []
    values = (
        {row["key"]: float(row["value"]) for row in list_manual_values()}
        if any(kind == "account" for kind, _, _ in deltas)
        else {}
    )
    cash_map = {(row["name"], row.get("currency") or "TWD"): row for row in cash_rows}
    changes: list[tuple[str, str, str, float]] = []
    try:
        for (kind, bucket, currency), delta in deltas.items():
            if kind == "account":
                key = invested_key(bucket)
                old_value = values.get(key, 0)
                new_value = max(old_value + delta, 0)
                upsert_manual_value(key, new_value)
                values[key] = new_value
            else:
                row = cash_map.get((bucket, currency))
                old_value = float(row.get("amount") or 0) if row else 0
                new_value = old_value + delta
                if row:
                    update_cash(row["id"], new_value, currency)
                    row["amount"] = new_value
                else:
                    row = create_cash({
                        "name": bucket,
                        "account": "",
                        "category": "欠款" if new_value < 0 or "欠錢" in bucket else "現金",
                        "currency": currency,
                        "amount": new_value,
                    })
                    cash_rows.append(row)
                    cash_map[(bucket, currency)] = row
            changes.append((kind, bucket, currency, old_value))
    except Exception:
        restore_balance_changes(changes, cash_rows, values)
        raise
    return changes


def apply_capital_movement_effect(data: dict, direction: float = 1) -> None:
    cash_rows = list_cash_accounts()
    cash_names = {row["name"] for row in cash_rows} | CASH_ACCOUNT_NAMES
    effects = movement_balance_effects(data, cash_names, direction)
    apply_balance_deltas(effects, cash_rows)


def capital_movement_payload(row: dict) -> dict:
    keys = ("movement_date", "from_bucket", "to_bucket", "amount", "currency", "to_amount", "to_currency", "note")
    return {key: row.get(key) for key in keys}


def capital_movement_balance_signature(row: dict) -> tuple:
    return (
        row.get("from_bucket"),
        row.get("to_bucket"),
        float(row.get("amount") or 0),
        row.get("currency") or "TWD",
        float(row.get("to_amount") or row.get("amount") or 0),
        row.get("to_currency") or row.get("currency") or "TWD",
    )


@router.patch("/capital-movements/{movement_id}")
def patch_capital_movement(movement_id: str, payload: CapitalMovementUpdate) -> dict:
    previous = get_capital_movement(movement_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Capital movement not found.")

    data = {key: value for key, value in payload.model_dump(mode="json").items() if value is not None}
    if capital_movement_balance_signature(previous) == capital_movement_balance_signature(data):
        return {"success": True, "movement": update_capital_movement(movement_id, data)}

    cash_rows = list_cash_accounts()
    cash_names = {row["name"] for row in cash_rows} | CASH_ACCOUNT_NAMES
    deltas = movement_balance_deltas(previous, data, cash_names)
    movement = update_capital_movement(movement_id, data)
    try:
        apply_balance_deltas(deltas, cash_rows)
    except Exception:
        update_capital_movement(movement_id, capital_movement_payload(previous))
        raise
    clear_summary_cache()
    return {"success": True, "movement": movement}


@router.delete("/capital-movements/{movement_id}")
def remove_capital_movement(movement_id: str) -> dict:
    previous = get_capital_movement(movement_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Capital movement not found.")
    cash_rows = list_cash_accounts()
    cash_names = {row["name"] for row in cash_rows} | CASH_ACCOUNT_NAMES
    deltas = movement_balance_deltas(previous, None, cash_names)
    changes = apply_balance_deltas(deltas, cash_rows)
    try:
        delete_capital_movement(movement_id)
    except Exception:
        restore_balance_changes(changes, cash_rows, {})
        raise
    clear_summary_cache()
    return {"success": True}
