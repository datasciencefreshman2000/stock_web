import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from models import CreditCardPaymentCreate
from services import movements

SOURCE='00000000-0000-4000-8000-000000000001'
DEBT='00000000-0000-4000-8000-000000000002'
OP='00000000-0000-4000-8000-000000000003'

@pytest.fixture
def payment(monkeypatch):
    rows=[dict(id=SOURCE,name='國泰現金',currency='TWD',amount=50000),
          dict(id=DEBT,name='信用卡欠錢',currency='TWD',amount=-30000)]
    calls=[]
    monkeypatch.setattr(movements,'operation_exists',lambda _:False)
    monkeypatch.setattr(movements,'get_data_revision',lambda:11)
    monkeypatch.setattr(movements,'list_cash_accounts',lambda:rows)
    def write(action,payload,**kwargs):
        calls.append((action,payload,kwargs)); return {'id':'new',**payload}
    monkeypatch.setattr(movements,'atomic_write',write)
    payload=CreditCardPaymentCreate(source_id=SOURCE,source_name='國泰現金',debt_id=DEBT,
        amount=20000,movement_date='2026-01-01',operation_id=OP).model_dump(mode='json')
    return payload,rows,calls

def test_partial_payment_is_one_transfer_with_two_effects(payment):
    payload,rows,calls=payment
    result=movements.write_credit_payment(payload)
    assert result['note']=='信用卡繳款'
    assert result['to_bucket']=='信用卡欠錢'
    assert calls[0][2]['revision']==11
    assert [effect['delta'] for effect in calls[0][2]['effects']]==['-20000.0','20000.0']

def test_all_payment_uses_exact_current_debt(payment):
    payload,rows,calls=payment
    payload.update(amount=30000,repayment_mode='all')
    movements.write_credit_payment(payload)
    assert len(calls)==1


def test_usd_payment_keeps_both_sides_in_usd(payment):
    payload,rows,calls=payment
    rows[0].update(currency='USD',amount=1000)
    rows[1].update(currency='USD',amount=-400)
    movements.write_credit_payment({**payload,'currency':'USD','amount':200})
    assert all(effect['currency']=='USD' for effect in calls[0][2]['effects'])
    assert [effect['delta'] for effect in calls[0][2]['effects']]==['-200','200']

@pytest.mark.parametrize('change,status',[
    ({'amount':30001},400),({'repayment_mode':'all'},409),
    ({'currency':'USD'},400),({'source_name':'不存在'},400),
    ({'source_id':'missing'},404),({'debt_id':SOURCE},400),
])
def test_invalid_payment_never_writes(payment,change,status):
    payload,rows,calls=payment
    with pytest.raises(HTTPException) as exc: movements.write_credit_payment({**payload,**change})
    assert exc.value.status_code==status
    assert not calls

@pytest.mark.parametrize('target,value',[(0,10000),(1,0),(1,3000)])
def test_insufficient_cash_or_paid_off_never_writes(payment,target,value):
    payload,rows,calls=payment; rows[target]['amount']=value
    with pytest.raises(HTTPException): movements.write_credit_payment(payload)
    assert not calls

def test_receivable_cannot_pay_credit_card(payment):
    payload,rows,calls=payment
    rows[0]['name']=payload['source_name']='公司欠錢 (待收款)'
    with pytest.raises(HTTPException): movements.write_credit_payment(payload)
    assert not calls

def test_successful_retry_replays_without_checking_now_paid_debt(payment,monkeypatch):
    payload,rows,calls=payment
    rows[1]['amount']=0
    monkeypatch.setattr(movements,'operation_exists',lambda _:True)
    monkeypatch.setattr(movements,'list_cash_accounts',lambda:pytest.fail('replay must precede live balance checks'))
    movements.write_credit_payment(payload)
    assert calls[0][2]=={}
    assert calls[0][1]['operation_id']==OP

def test_request_rejects_future_date_and_fractional_cents(payment):
    payload,_,_=payment
    for changes in [{'movement_date':'2099-01-01'},{'amount':1.001}]:
        with pytest.raises(ValidationError): CreditCardPaymentCreate(**{**payload,**changes})


def test_ledger_edit_cannot_increase_payment_beyond_remaining_debt(payment,monkeypatch):
    payload,rows,calls=payment
    # Original 20k already paid; 10k debt remains. Editing to 40k would overpay.
    rows[0]['amount']=30000; rows[1]['amount']=-10000
    old=dict(from_bucket='國泰現金',to_bucket='信用卡欠錢',currency='TWD',amount=20000)
    monkeypatch.setattr(movements,'get_capital_movement',lambda _:old)
    with pytest.raises(HTTPException):
        movements.write_movement('movement.update',{**old,'amount':40000,'operation_id':OP},record_id='old')
    assert not calls


def test_ledger_edit_reverses_old_payment_before_cash_check(payment,monkeypatch):
    payload,rows,calls=payment
    rows[0]['amount']=30000; rows[1]['amount']=-10000
    old=dict(from_bucket='國泰現金',to_bucket='信用卡欠錢',currency='TWD',amount=20000)
    monkeypatch.setattr(movements,'get_capital_movement',lambda _:old)
    movements.write_movement('movement.update',{**old,'amount':30000,'operation_id':OP},record_id='old')
    assert [item['delta'] for item in calls[0][2]['effects']]==['-10000','10000']
