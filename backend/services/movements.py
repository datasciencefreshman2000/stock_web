from fastapi import HTTPException
from repositories.operations import atomic_write, get_data_revision
from repositories.manual import list_cash_accounts, list_manual_values, get_capital_movement
from repositories.trades import list_trades
from services.accounts import ACCOUNTS, CASH_ACCOUNT_NAMES, ACCOUNT_CURRENCY, BUCKET_ALIASES, invested_key
from services.calculator import analyze_account_trades
from services.money import decimal


def balance_effects(data: dict | None, cash_names: set[str], direction=1) -> dict:
    if not data or data.get("affects_balance") is False:
        return {}
    result = {}
    for name, currency, amount in [
        (data.get("from_bucket"), data.get("currency", "TWD"), -decimal(data.get("amount"))),
        (data.get("to_bucket"), data.get("to_currency") or data.get("currency", "TWD"), decimal(data.get("to_amount") or data.get("amount"))),
    ]:
        name = BUCKET_ALIASES.get(name, name)
        if not name or name == "支出":
            continue
        if name not in ACCOUNTS and name not in cash_names:
            raise HTTPException(400, f"找不到帳戶：{name}")
        if name in ACCOUNT_CURRENCY and currency != ACCOUNT_CURRENCY[name]:
            raise HTTPException(400, f"{name} 的幣別必須為 {ACCOUNT_CURRENCY[name]}")
        key = ("account" if name in ACCOUNTS else "cash", name, currency)
        result[key] = result.get(key, decimal(0)) + amount * direction
    return result


def write_movement(action: str, payload: dict | None = None, record_id=None, operation_id=None):
    # A revision CAS ensures the available cash checked here is still current at commit.
    revision = get_data_revision()
    previous = get_capital_movement(record_id) if record_id else None
    current = payload if action != "movement.delete" else None
    names = CASH_ACCOUNT_NAMES | {row["name"] for row in list_cash_accounts()}
    effects = balance_effects(previous, names, -1)
    for key, delta in balance_effects(current, names).items():
        effects[key] = effects.get(key, decimal(0)) + delta
    withdrawals = {name: delta for (kind, name, _), delta in effects.items() if kind == "account" and delta < 0}
    available = {}
    if withdrawals:
        values = {row["key"]: decimal(row["value"]) for row in list_manual_values()}
        for name, delta in withdrawals.items():
            results = analyze_account_trades(name, list_trades(name))
            cost = sum((decimal(r["total_cost"]) for r in results.values()), decimal(0))
            pnl = sum((decimal(r["realized_pnl"]) for r in results.values()), decimal(0))
            cash = values.get(invested_key(name), decimal(0)) - cost + pnl
            available[name] = str(cash)
    return atomic_write(action, payload, record_id=record_id, operation_id=operation_id, revision=revision,
                        effects=[{"kind": kind, "bucket": name, "currency": currency, "delta": str(delta), "available_cash": available.get(name)}
                                 for (kind, name, currency), delta in effects.items() if delta])
