from fastapi import APIRouter, HTTPException

from models import CapitalMovementCreate, CapitalMovementOptionCreate, CashCreate, CashUpdate, ManualInvestmentCreate, ManualInvestmentUpdate, ManualValueUpdate
from repositories.manual import (
    list_cash_accounts,
    create_cash,
    create_capital_movement,
    create_capital_movement_option,
    adjust_cash_balance,
    create_manual_investment,
    delete_capital_movement_option,
    delete_manual_investment,
    list_capital_movements,
    list_capital_movement_options,
    list_manual_values,
    list_manual_investments,
    update_manual_investment,
    update_cash,
    upsert_manual_value,
)
from repositories.summary_cache import clear_summary_cache
from services.accounts import ACCOUNTS, invested_key

router = APIRouter()


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
    values = {row["key"]: float(row["value"]) for row in list_manual_values()}
    cash_names = {row["name"] for row in list_cash_accounts()}
    amount = float(data["amount"])
    to_amount = float(data.get("to_amount") or data["amount"])
    currency = data["currency"]
    to_currency = data.get("to_currency") or currency
    if data.get("to_bucket") in ACCOUNTS:
        key = invested_key(data["to_bucket"])
        upsert_manual_value(key, values.get(key, 0) + to_amount)
    elif data.get("to_bucket") in cash_names:
        adjust_cash_balance(data["to_bucket"], to_currency, to_amount)
    if data.get("from_bucket") in ACCOUNTS:
        key = invested_key(data["from_bucket"])
        upsert_manual_value(key, max(values.get(key, 0) - amount, 0))
    elif data.get("from_bucket") in cash_names:
        adjust_cash_balance(data["from_bucket"], currency, -amount)
    clear_summary_cache()
    return {"success": True, "movement": movement}
