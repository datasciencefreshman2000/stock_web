from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import require_auth
from models import CapitalMovementCreate, CapitalMovementOptionCreate, CapitalMovementUpdate, CashCreate, CashUpdate, ManualInvestmentBulkUpdate, ManualInvestmentCreate, ManualInvestmentUpdate, ManualValueUpdate
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
    update_manual_investments,
    update_cash,
    upsert_manual_value,
)
from repositories.summary_cache import clear_summary_cache
from services.cache_patch import refresh_cash_and_manual_in_cache
from services.accounts import ACCOUNTS, CASH_ACCOUNT_NAMES, invested_key

# 整個 router 都需要登入
router = APIRouter(dependencies=[Depends(require_auth)])
TAIPEI_TZ = timezone(timedelta(hours=8))


def month_bounds(month: str) -> tuple[str, str]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1)
    next_month = datetime(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1)
    return start.date().isoformat(), next_month.date().isoformat()


def money_changed(scope: str) -> None:
    """現金／手動投資變動：只重算便宜的部分並 patch 回快取。

    這類寫入不影響 FIFO，沒有理由讓下一個 GET 完整重算
    （完整重算約 11 次 DB 往返，patch 只要 5 次）。

    退路有兩層：
      1. 沒有快取可 patch → 刪除，讓下次 GET 重建
      2. patch 過程出任何錯 → 也刪除。快取算錯比慢更糟，
         寧可退回重算也不要留下不一致的資料。
    """
    try:
        if refresh_cash_and_manual_in_cache(scope):
            return
    except Exception:
        pass
    clear_summary_cache()



@router.get("")
def get_manual() -> dict:
    return {"values": list_manual_values(), "cash": list_cash_accounts(), "investments": list_manual_investments()}


@router.patch("/value")
def patch_manual_value(update: ManualValueUpdate) -> dict:
    value = upsert_manual_value(update.key, update.value)
    money_changed("invested" if update.key.startswith("invested_") else "manual")
    return {"success": True, "value": value}


@router.patch("/cash/{cash_id}")
def patch_cash(cash_id: str, update: CashUpdate) -> dict:
    cash = update_cash(cash_id, update.amount, update.currency)
    money_changed("cash")
    return {"success": True, "cash": cash}


@router.post("/cash")
def add_cash(payload: CashCreate) -> dict:
    cash = create_cash(payload.model_dump())
    money_changed("cash")
    return {"success": True, "cash": cash}


@router.post("/investment")
def add_investment(payload: ManualInvestmentCreate) -> dict:
    try:
        investment = create_manual_investment(payload.model_dump())
        money_changed("investment")
        return {"success": True, "investment": investment}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/investment/{investment_id}")
def patch_investment(investment_id: str, payload: ManualInvestmentUpdate) -> dict:
    try:
        investment = update_manual_investment(investment_id, payload.model_dump())
        money_changed("investment")
        return {"success": True, "investment": investment}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/investments")
def patch_investments(payload: ManualInvestmentBulkUpdate) -> dict:
    try:
        investments = update_manual_investments([
            item.model_dump(mode="json") for item in payload.investments
        ])
        money_changed("investment")
        return {"success": True, "investments": investments}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/investment/{investment_id}")
def remove_investment(investment_id: str) -> dict:
    try:
        delete_manual_investment(investment_id)
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
    money_changed("movement")
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
    money_changed("movement")
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
    money_changed("movement")
    return {"success": True}
