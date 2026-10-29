from fastapi import HTTPException
from repositories.operations import atomic_write, get_data_revision, operation_exists
from repositories.manual import list_cash_accounts, list_manual_values, get_capital_movement
from repositories.trades import list_trades
from services.accounts import ACCOUNTS, CASH_ACCOUNT_NAMES, ACCOUNT_CURRENCY, BUCKET_ALIASES, invested_key
from services.calculator import analyze_account_trades
from services.money import decimal


def write_credit_payment(payload: dict) -> dict:
    movement = {**payload, 'from_bucket': payload['source_name'], 'to_bucket': '信用卡欠錢',
                'affects_balance': True, 'note': '信用卡繳款' + (' - ' + payload['note'] if payload.get('note') else '')}
    # A lost successful response must replay even after the debt is fully paid.
    if operation_exists(payload['operation_id']):
        return atomic_write('movement.create', movement)
    revision = get_data_revision()
    rows = {str(row['id']): row for row in list_cash_accounts()}
    source, debt = rows.get(payload['source_id']), rows.get(payload['debt_id'])
    if not source or not debt:
        raise HTTPException(404, '付款帳戶或信用卡欠款已不存在，請重新讀取。')
    if source['name'] != payload['source_name'] or debt['name'] != '信用卡欠錢':
        raise HTTPException(400, '付款帳戶或欠款帳戶不正確。')
    if source['currency'] != payload['currency'] or debt['currency'] != payload['currency']:
        raise HTTPException(400, '繳款須使用同幣別現金，請先完成換匯。')
    if any(word in source['name'] for word in ('欠錢', '待收', '待還')) or source.get('category') in ('負債', '應收款'):
        raise HTTPException(400, '請選擇實際現金帳戶，應收款與負債不能作為付款來源。')
    amount, available, owing = decimal(payload['amount']), decimal(source.get('amount')), -decimal(debt.get('amount'))
    if owing <= 0:
        raise HTTPException(409, '信用卡已繳清，請重新讀取。')
    if amount > owing:
        raise HTTPException(400, '繳款金額不能超過目前欠款。')
    if payload['repayment_mode'] == 'all' and amount != owing:
        raise HTTPException(409, '欠款已變動，請重新讀取後再確認全部繳清金額。')
    if amount > available:
        raise HTTPException(400, '付款帳戶餘額不足，請換帳戶或改為部分繳款。')
    return atomic_write('movement.create', movement, revision=revision, effects=[
        {'kind':'cash','bucket':source['name'],'currency':payload['currency'],'delta':str(-amount)},
        {'kind':'cash','bucket':debt['name'],'currency':payload['currency'],'delta':str(amount)},
    ])


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
    repayment = bool(payload and payload.get('to_bucket') == '信用卡欠錢' and payload.get('from_bucket') and payload.get('affects_balance') is not False)
    if repayment and payload.get('operation_id') and operation_exists(payload['operation_id']):
        return atomic_write(action, payload, record_id=record_id, operation_id=operation_id)
    # A revision CAS ensures the available cash checked here is still current at commit.
    revision = get_data_revision()
    previous = get_capital_movement(record_id) if record_id else None
    current = payload if action != "movement.delete" else None
    cash_rows = list_cash_accounts()
    names = CASH_ACCOUNT_NAMES | {row["name"] for row in cash_rows}
    effects = balance_effects(previous, names, -1)
    for key, delta in balance_effects(current, names).items():
        effects[key] = effects.get(key, decimal(0)) + delta
    if repayment:
        # Ledger edits and the general transfer form must also respect current
        # balances. Net effects include reversal of the old payment on edits.
        for (kind, name, currency), delta in effects.items():
            if kind != 'cash':
                continue
            row = next((row for row in cash_rows if row['name'] == name and row['currency'] == currency), None)
            projected = decimal(row.get('amount')) + delta if row else delta
            if name == '信用卡欠錢' and projected > 0:
                raise HTTPException(400, '繳款金額不能超過目前欠款。')
            if name == payload['from_bucket'] and projected < 0:
                raise HTTPException(400, '付款帳戶餘額不足。')
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
