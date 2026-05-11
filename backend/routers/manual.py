from fastapi import APIRouter, HTTPException

from models import CashCreate, CashUpdate, ManualInvestmentCreate, ManualInvestmentUpdate, ManualValueUpdate
from repositories.manual import (
    list_cash_accounts,
    create_cash,
    create_manual_investment,
    list_manual_values,
    list_manual_investments,
    update_manual_investment,
    update_cash,
    upsert_manual_value,
)
from repositories.summary_cache import clear_summary_cache

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
