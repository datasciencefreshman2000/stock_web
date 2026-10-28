from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import require_auth
from models import CapitalMovementCreate, CapitalMovementOptionCreate, CapitalMovementUpdate, CashCreate, CashUpdate, ManualInvestmentBulkUpdate, ManualInvestmentCreate, ManualInvestmentUpdate, ManualValueUpdate
from repositories.manual import (
    list_cash_accounts,
    create_capital_movement_option,
    delete_capital_movement_option,
    get_capital_movement,
    list_capital_movements,
    list_capital_movement_options,
    list_manual_values,
    list_manual_investments,
)
from repositories.operations import atomic_write
from services.movements import write_movement
from repositories.manual import list_balance_adjustments

# 整個 router 都需要登入
router = APIRouter(dependencies=[Depends(require_auth)])
TAIPEI_TZ = timezone(timedelta(hours=8))


def month_bounds(month: str) -> tuple[str, str]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1)
    next_month = datetime(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1)
    return start.date().isoformat(), next_month.date().isoformat()


def money_changed(scope: str) -> None:
    # Revision invalidation happens inside the committed DB transaction.
    # Cache failures must never turn an already committed write into a failed save.
    return None


@router.get("")
def get_manual() -> dict:
    return {"values": list_manual_values(), "cash": list_cash_accounts(), "investments": list_manual_investments()}


@router.patch("/value")
def patch_manual_value(update: ManualValueUpdate) -> dict:
    value = atomic_write("value.set", update.model_dump(mode="json"))
    money_changed("invested" if update.key.startswith("invested_") else "manual")
    return {"success": True, "value": value}


@router.patch("/cash/{cash_id}")
def patch_cash(cash_id: str, update: CashUpdate) -> dict:
    cash = atomic_write("cash.update", update.model_dump(mode="json"), record_id=cash_id)
    money_changed("cash")
    return {"success": True, "cash": cash}


@router.post("/cash")
def add_cash(payload: CashCreate) -> dict:
    cash = atomic_write("cash.create", payload.model_dump(mode="json"))
    money_changed("cash")
    return {"success": True, "cash": cash}


@router.post("/investment")
def add_investment(payload: ManualInvestmentCreate) -> dict:
    try:
        investment = atomic_write("investment.create", payload.model_dump(mode="json"))
        money_changed("investment")
        return {"success": True, "investment": investment}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/investment/{investment_id}")
def patch_investment(investment_id: str, payload: ManualInvestmentUpdate) -> dict:
    try:
        investment = atomic_write("investment.update", payload.model_dump(mode="json", exclude_none=True), record_id=investment_id)
        money_changed("investment")
        return {"success": True, "investment": investment}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/investments")
def patch_investments(payload: ManualInvestmentBulkUpdate) -> dict:
    try:
        investments = atomic_write("investment.bulk", payload.model_dump(mode="json"))
        money_changed("investment")
        return {"success": True, "investments": investments}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/investment/{investment_id}")
def remove_investment(investment_id: str, operation_id: str | None = None) -> dict:
    try:
        atomic_write("investment.delete", record_id=investment_id, operation_id=operation_id)
        money_changed("investment")
        return {"success": True}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/capital-movements")
def get_capital_movements(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
) -> dict:
    selected_month = month or datetime.now(TAIPEI_TZ).strftime("%Y-%m")
    start_date, end_date = month_bounds(selected_month)
    return {"month": selected_month, "movements": list_capital_movements(start_date, end_date)}


@router.get("/capital-movement-options")
def get_capital_movement_options(category: str = "income_source") -> dict:
    return {"options": list_capital_movement_options(category)}


@router.get("/balance-adjustments")
def get_balance_adjustments(month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")) -> dict:
    start, end = month_bounds(month)
    return {"adjustments": list_balance_adjustments(start, end)}


@router.post("/capital-movement-options")
def add_capital_movement_option(payload: CapitalMovementOptionCreate) -> dict:
    return {"success": True, "option": create_capital_movement_option(payload.model_dump())}


@router.delete("/capital-movement-options/{option_id}")
def remove_capital_movement_option(option_id: str) -> dict:
    delete_capital_movement_option(option_id)
    return {"success": True}


@router.post("/capital-movements")
def add_capital_movement(payload: CapitalMovementCreate) -> dict:
    movement = write_movement("movement.create", payload.model_dump(mode="json", exclude_none=True))
    return {"success": True, "movement": movement}


@router.patch("/capital-movements/{movement_id}")
def patch_capital_movement(movement_id: str, payload: CapitalMovementUpdate) -> dict:
    movement = write_movement("movement.update", payload.model_dump(mode="json", exclude_none=True), record_id=movement_id)
    return {"success": True, "movement": movement}


@router.delete("/capital-movements/{movement_id}")
def remove_capital_movement(movement_id: str, operation_id: str | None = None) -> dict:
    result = write_movement("movement.delete", record_id=movement_id, operation_id=operation_id)
    return {"success": True, "balance_effect_note": result.get("balance_effect_note")}
