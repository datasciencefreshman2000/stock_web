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
