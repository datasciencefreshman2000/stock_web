from datetime import date

from models import CapitalMovementCreate, CapitalMovementUpdate
from routers import manual as manual_router


def test_expense_creates_missing_on_hand_cash_balance(monkeypatch):
    created_cash = []
    payload = CapitalMovementCreate(
        movement_date=date(2026, 8, 5),
        from_bucket="身上現金",
        to_bucket="支出",
        amount=120,
        currency="TWD",
        note="飲食",
    )

    monkeypatch.setattr(manual_router, "create_capital_movement", lambda data: data)
    monkeypatch.setattr(manual_router, "list_manual_values", lambda: [])
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [])
    monkeypatch.setattr(
        manual_router,
        "create_cash",
        lambda data: created_cash.append(data) or {"id": "cash-1", **data},
    )
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: None)

    result = manual_router.add_capital_movement(payload)

    assert result["success"] is True
    assert created_cash == [{
        "name": "身上現金",
        "account": "",
        "category": "欠款",
        "currency": "TWD",
        "amount": -120.0,
    }]


def test_usd_account_can_exchange_directly_into_twd_cash(monkeypatch):
    """美股 USD 可直接換匯到國泰現金 TWD，不需要中間帳戶。"""
    updates = []
    payload = CapitalMovementCreate(
        movement_date=date(2026, 8, 23),
        from_bucket="美股",
        to_bucket="國泰現金",
        amount=1000,
        currency="USD",
        to_amount=32000,
        to_currency="TWD",
        note="美股賣出後換回台幣",
    )

    monkeypatch.setattr(manual_router, "create_capital_movement", lambda data: data)
    monkeypatch.setattr(manual_router, "list_manual_values", lambda: [
        {"key": "invested_美股", "value": 5000},
    ])
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [
        {"id": "cathay-twd", "name": "國泰現金", "currency": "TWD", "amount": 10000},
    ])
    monkeypatch.setattr(
        manual_router,
        "upsert_manual_value",
        lambda key, value: updates.append(("account", key, value)) or {"key": key, "value": value},
    )
    monkeypatch.setattr(
        manual_router,
        "update_cash",
        lambda cash_id, amount, currency: updates.append(("cash", cash_id, amount, currency)) or {
            "id": cash_id,
            "amount": amount,
            "currency": currency,
        },
    )
    monkeypatch.setattr(manual_router, "money_changed", lambda _scope: None)

    result = manual_router.add_capital_movement(payload)

    assert result["success"] is True
    assert set(updates) == {
        ("account", "invested_美股", 4000.0),
        ("cash", "cathay-twd", 42000.0, "TWD"),
    }


def test_exchange_rejects_more_than_account_balance(monkeypatch):
    """來源帳戶不足時不能留下目的地入帳或換匯紀錄。"""
    deleted = []
    created_cash = []
    payload = CapitalMovementCreate(
        movement_date=date(2026, 8, 24),
        from_bucket="美股",
        to_bucket="國泰現金",
        amount=6000,
        currency="USD",
        to_amount=192000,
        to_currency="TWD",
    )

    monkeypatch.setattr(manual_router, "create_capital_movement", lambda data: {"id": "movement-1", **data})
    monkeypatch.setattr(manual_router, "delete_capital_movement", lambda movement_id: deleted.append(movement_id))
    monkeypatch.setattr(manual_router, "list_manual_values", lambda: [
        {"key": "invested_美股", "value": 5000},
    ])
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [
        {"id": "cathay-twd", "name": "國泰現金", "currency": "TWD", "amount": 10000},
    ])
    monkeypatch.setattr(
        manual_router,
        "update_cash",
        lambda cash_id, amount, currency: created_cash.append((cash_id, amount, currency)),
    )

    response = None
    try:
        manual_router.add_capital_movement(payload)
    except Exception as exc:
        response = exc

    assert getattr(response, "status_code", None) == 400
    assert deleted == ["movement-1"]
    assert created_cash == [
        ("cathay-twd", 202000.0, "TWD"),
        ("cathay-twd", 10000.0, "TWD"),
    ]


def test_edit_expense_reverses_old_source_and_applies_new_source(monkeypatch):
    updates = []
    previous = {
        "id": "movement-1",
        "movement_date": "2026-08-05",
        "from_bucket": "身上現金",
        "to_bucket": "支出",
        "amount": 120,
        "currency": "TWD",
        "to_amount": None,
        "to_currency": None,
        "note": "飲食",
    }
    payload = CapitalMovementUpdate(
        movement_date=date(2026, 8, 5),
        from_bucket="信用卡欠錢",
        to_bucket="支出",
        amount=200,
        currency="TWD",
        note="飲食, 娛樂 - 晚餐",
    )

    monkeypatch.setattr(manual_router, "get_capital_movement", lambda _id: previous)
    monkeypatch.setattr(manual_router, "update_capital_movement", lambda movement_id, data: {"id": movement_id, **data})
    monkeypatch.setattr(manual_router, "list_manual_values", lambda: [])
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [
        {"id": "cash-on-hand", "name": "身上現金", "currency": "TWD", "amount": 1000},
        {"id": "cash-card", "name": "信用卡欠錢", "currency": "TWD", "amount": -500},
    ])
    monkeypatch.setattr(
        manual_router,
        "update_cash",
        lambda cash_id, amount, currency: updates.append((cash_id, amount, currency)) or {"id": cash_id, "amount": amount, "currency": currency},
    )
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: None)

    result = manual_router.patch_capital_movement("movement-1", payload)

    assert result["success"] is True
    assert updates == [
        ("cash-on-hand", 1120.0, "TWD"),
        ("cash-card", -700.0, "TWD"),
    ]


def test_delete_expense_reverses_balance(monkeypatch):
    updates = []
    previous = {
        "id": "movement-1",
        "movement_date": "2026-08-05",
        "from_bucket": "身上現金",
        "to_bucket": "支出",
        "amount": 120,
        "currency": "TWD",
        "note": "飲食",
    }

    monkeypatch.setattr(manual_router, "get_capital_movement", lambda _id: previous)
    monkeypatch.setattr(manual_router, "delete_capital_movement", lambda _id: None)
    monkeypatch.setattr(manual_router, "list_manual_values", lambda: [])
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [
        {"id": "cash-on-hand", "name": "身上現金", "currency": "TWD", "amount": 1000},
    ])
    monkeypatch.setattr(
        manual_router,
        "update_cash",
        lambda cash_id, amount, currency: updates.append((cash_id, amount, currency)) or {"id": cash_id, "amount": amount, "currency": currency},
    )
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: None)

    result = manual_router.remove_capital_movement("movement-1")

    assert result == {"success": True}
    assert updates == [("cash-on-hand", 1120.0, "TWD")]


def test_editing_note_only_does_not_touch_balances(monkeypatch):
    updates = []
    cache_clears = []
    previous = {
        "id": "movement-1",
        "movement_date": "2026-08-05",
        "from_bucket": "身上現金",
        "to_bucket": "支出",
        "amount": 120,
        "currency": "TWD",
        "to_amount": None,
        "to_currency": None,
        "note": "飲食",
    }
    payload = CapitalMovementUpdate(
        movement_date=date(2026, 8, 5),
        from_bucket="身上現金",
        to_bucket="支出",
        amount=120,
        currency="TWD",
        note="飲食 - 晚餐",
    )

    monkeypatch.setattr(manual_router, "get_capital_movement", lambda _id: previous)
    monkeypatch.setattr(manual_router, "update_capital_movement", lambda movement_id, data: {"id": movement_id, **data})
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: (_ for _ in ()).throw(AssertionError("cash should not be loaded")))
    monkeypatch.setattr(manual_router, "update_cash", lambda *args: updates.append(args))
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: cache_clears.append(True))

    result = manual_router.patch_capital_movement("movement-1", payload)

    assert result["success"] is True
    assert updates == []
    assert cache_clears == []
