from datetime import date

from models import CapitalMovementCreate, CapitalMovementUpdate
from routers import manual as manual_router


def test_expense_creates_missing_on_hand_cash_balance(monkeypatch):
    adjustments = []
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
        "adjust_cash_balance",
        lambda name, currency, delta: adjustments.append((name, currency, delta)),
    )
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: None)

    result = manual_router.add_capital_movement(payload)

    assert result["success"] is True
    assert adjustments == [("身上現金", "TWD", -120.0)]


def test_edit_expense_reverses_old_source_and_applies_new_source(monkeypatch):
    adjustments = []
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
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [])
    monkeypatch.setattr(
        manual_router,
        "adjust_cash_balance",
        lambda name, currency, delta: adjustments.append((name, currency, delta)),
    )
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: None)

    result = manual_router.patch_capital_movement("movement-1", payload)

    assert result["success"] is True
    assert adjustments == [
        ("身上現金", "TWD", 120.0),
        ("信用卡欠錢", "TWD", -200.0),
    ]


def test_delete_expense_reverses_balance(monkeypatch):
    adjustments = []
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
    monkeypatch.setattr(manual_router, "list_cash_accounts", lambda: [])
    monkeypatch.setattr(
        manual_router,
        "adjust_cash_balance",
        lambda name, currency, delta: adjustments.append((name, currency, delta)),
    )
    monkeypatch.setattr(manual_router, "clear_summary_cache", lambda: None)

    result = manual_router.remove_capital_movement("movement-1")

    assert result == {"success": True}
    assert adjustments == [("身上現金", "TWD", 120.0)]
