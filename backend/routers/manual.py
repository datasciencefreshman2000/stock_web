from fastapi import APIRouter, Depends, HTTPException

from dependencies import require_auth
from models import CapitalMovementCreate, CapitalMovementOptionCreate, CapitalMovementUpdate, CashCreate, CashUpdate, ManualInvestmentCreate, ManualInvestmentUpdate, ManualValueUpdate
from repositories.manual import (
    list_cash_accounts,
    create_cash,
    create_capital_movement,
    create_capital_movement_option,
    adjust_cash_balance,
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


def apply_capital_movement_effect(data: dict, direction: float = 1) -> None:
    values = {row["key"]: float(row["value"]) for row in list_manual_values()}
    cash_names = {row["name"] for row in list_cash_accounts()} | CASH_ACCOUNT_NAMES

    def adjust_bucket(bucket: str | None, currency: str, delta: float) -> None:
        if not bucket:
            return
        if bucket in ACCOUNTS:
            key = invested_key(bucket)
            value = max(values.get(key, 0) + delta, 0)
            upsert_manual_value(key, value)
            values[key] = value
        elif bucket in cash_names:
            adjust_cash_balance(bucket, currency, delta)

    amount = float(data["amount"])
    currency = data.get("currency") or "TWD"
    to_amount = float(data.get("to_amount") or amount)
    to_currency = data.get("to_currency") or currency
    operations = [
        (data.get("to_bucket"), to_currency, direction * to_amount),
        (data.get("from_bucket"), currency, direction * -amount),
    ]
    completed: list[tuple[str | None, str, float]] = []
    try:
        for bucket, bucket_currency, delta in operations:
            adjust_bucket(bucket, bucket_currency, delta)
            completed.append((bucket, bucket_currency, delta))
    except Exception:
        for bucket, bucket_currency, delta in reversed(completed):
            adjust_bucket(bucket, bucket_currency, -delta)
        raise


def capital_movement_payload(row: dict) -> dict:
    keys = ("movement_date", "from_bucket", "to_bucket", "amount", "currency", "to_amount", "to_currency", "note")
    return {key: row.get(key) for key in keys}


@router.patch("/capital-movements/{movement_id}")
def patch_capital_movement(movement_id: str, payload: CapitalMovementUpdate) -> dict:
    previous = get_capital_movement(movement_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Capital movement not found.")

    data = {key: value for key, value in payload.model_dump(mode="json").items() if value is not None}
    apply_capital_movement_effect(previous, direction=-1)
    try:
        movement = update_capital_movement(movement_id, data)
        apply_capital_movement_effect(data)
    except Exception:
        update_capital_movement(movement_id, capital_movement_payload(previous))
        apply_capital_movement_effect(previous)
        raise
    clear_summary_cache()
    return {"success": True, "movement": movement}


@router.delete("/capital-movements/{movement_id}")
def remove_capital_movement(movement_id: str) -> dict:
    previous = get_capital_movement(movement_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Capital movement not found.")
    apply_capital_movement_effect(previous, direction=-1)
    try:
        delete_capital_movement(movement_id)
    except Exception:
        apply_capital_movement_effect(previous)
        raise
    clear_summary_cache()
    return {"success": True}
