"""Cash checks, both FX directions, edit/delete effects; SQL atomicity has a PG integration suite."""
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError
from models import CapitalMovementCreate
from services import movements


@pytest.fixture
def ledger(monkeypatch):
    captured = {}
    monkeypatch.setattr(movements, 'get_data_revision', lambda: 7)
    monkeypatch.setattr(movements, 'list_cash_accounts', lambda: [{'name': '國泰現金'}])
    monkeypatch.setattr(movements, 'list_manual_values', lambda: [{'key':'invested_美股','value':2000}])
    monkeypatch.setattr(movements, 'list_trades', lambda _: [])
    monkeypatch.setattr(movements, 'analyze_account_trades', lambda *_: {'TEST': {'total_cost':1000,'realized_pnl':100}})
    monkeypatch.setattr(movements, 'get_capital_movement', lambda _: captured.get('previous'))
    def write(action,payload,**kwargs):
        captured.update(action=action,payload=payload,**kwargs)
        return {'id':'result',**(payload or {})}
    monkeypatch.setattr(movements,'atomic_write',write)
    return captured


def effects(result):
    return {(e['kind'],e['bucket'],e['currency']): Decimal(e['delta']) for e in result['effects']}


def test_twd_bank_directly_into_us_account(ledger):
    payload=CapitalMovementCreate(movement_date=date(2026,8,23),from_bucket='國泰現金',to_bucket='美股',amount=32000,currency='TWD',to_amount=1000,to_currency='USD')
    movements.write_movement('movement.create',payload.model_dump(mode='json'))
    assert ledger['revision']==7
    assert effects(ledger)=={('cash','國泰現金','TWD'):Decimal('-32000'),('account','美股','USD'):Decimal('1000')}


def test_us_account_directly_back_to_twd_bank_checks_cash(ledger):
    payload=CapitalMovementCreate(movement_date=date(2026,8,23),from_bucket='美股',to_bucket='國泰現金',amount=500,currency='USD',to_amount=16000,to_currency='TWD')
    movements.write_movement('movement.create',payload.model_dump(mode='json'))
    source=next(e for e in ledger['effects'] if e['kind']=='account')
    assert source['available_cash']=='1100'  # net deposits - remaining cost + realized profit
    assert effects(ledger)=={('account','美股','USD'):Decimal('-500'),('cash','國泰現金','TWD'):Decimal('16000')}


@pytest.mark.parametrize('kwargs',[
    dict(from_bucket='美股',to_bucket='國泰現金',amount=100,currency='TWD'),
    dict(from_bucket='國泰現金',to_bucket='美股',amount=100,currency='TWD'),
    dict(from_bucket='國泰現金',to_bucket='美股',amount=100,currency='TWD',to_currency='USD'),
    dict(from_bucket='國泰現金',to_bucket='國泰現金',amount=100,currency='TWD'),
])
def test_invalid_currency_or_same_bucket_is_rejected(kwargs):
    with pytest.raises(ValidationError): CapitalMovementCreate(movement_date=date(2026,8,23),**kwargs)


def test_expense_can_create_on_hand_bucket(ledger):
    movements.write_movement('movement.create',dict(from_bucket='身上現金',to_bucket='支出',amount=120,currency='TWD'))
    assert effects(ledger)=={('cash','身上現金','TWD'):Decimal('-120')}


def test_unknown_bucket_fails_instead_of_silent_success(ledger):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc: movements.balance_effects({'to_bucket':'不存在','amount':1},set())
    assert exc.value.status_code==400


def test_edit_reverses_old_source_and_applies_new_source(ledger):
    ledger['previous']=dict(from_bucket='身上現金',to_bucket='支出',amount=120,currency='TWD')
    movements.write_movement('movement.update',dict(from_bucket='信用卡欠錢',to_bucket='支出',amount=200,currency='TWD'),record_id='movement')
    assert effects(ledger)=={('cash','身上現金','TWD'):Decimal('120'),('cash','信用卡欠錢','TWD'):Decimal('-200')}


def test_delete_reverses_balance(ledger):
    ledger['previous']=dict(from_bucket='身上現金',to_bucket='支出',amount=120,currency='TWD')
    movements.write_movement('movement.delete',record_id='movement')
    assert effects(ledger)=={('cash','身上現金','TWD'):Decimal('120')}


def test_edit_note_has_no_balance_effect(ledger):
    ledger['previous']=dict(from_bucket='身上現金',to_bucket='支出',amount=120,currency='TWD')
    movements.write_movement('movement.update',{**ledger['previous'],'note':'晚餐'},record_id='movement')
    assert ledger['effects']==[]


def test_other_bucket_aliases_are_normalized():
    payload=CapitalMovementCreate(movement_date=date(2026,8,23),to_bucket='公司欠錢',amount=120)
    assert payload.to_bucket=='公司欠錢 (待收款)'
