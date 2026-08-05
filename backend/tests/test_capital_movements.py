from datetime import date

from models import CapitalMovementCreate
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
