from datetime import date
import pytest
from services.accounts import enrich_account_summary
from services.calculator import build_holdings_from_results, summarize_account_from_results
from services.fifo import calc_fifo
from services.settlement import analyze_account, _state_to_checkpoint
from repositories.snapshots import build_snapshot_rows

BUY=dict(id='a',date='2026-01-01',buy_qty=10,sell_qty=None,price=100,fee=10)


def test_buy_fee_reduces_real_cash_and_total_assets():
    result=calc_fifo([BUY],'美股','TEST')
    holdings=build_holdings_from_results({'TEST':result},{'TEST':100})
    summary=enrich_account_summary(summarize_account_from_results({'TEST':result},holdings),'美股',32,2000)
    assert summary['inferred_cash']==pytest.approx(990)
    assert summary['account_total']==pytest.approx(1990)


def test_zero_and_negative_net_capital_are_not_replaced_by_cost():
    for value in [0,-100]:
        result=enrich_account_summary(dict(cost=1000,market_value=1100,realized_pnl=2000),'美股',32,value)
        assert result['invested']==value


def test_missing_quote_is_unknown_not_a_full_loss():
    result=calc_fifo([BUY],'美股','TEST')
    summary=summarize_account_from_results({'TEST':result},build_holdings_from_results({'TEST':result},{}))
    assert summary['unrealized_pnl'] is None
    assert summary['missing_prices']==['TEST']


def test_partial_quotes_do_not_show_known_holding_as_full_allocation():
    result=calc_fifo([BUY],'美股','TEST')
    holdings=build_holdings_from_results({'TEST':result,'MISSING':result},{'TEST':100})
    assert all(item['weight'] is None for item in holdings)


def test_future_split_and_trade_do_not_change_current_holdings():
    result=calc_fifo([BUY,{**BUY,'date':'2099-01-01'}],'美股','TEST',actions=[dict(action_type='split',ex_date='2099-01-01',ratio=2)])
    assert result['current_qty']==10


def test_fee_checkpoint_equals_full_recompute():
    trades=[BUY,{**BUY,'id':'b','date':'2026-02-01','buy_qty':None,'sell_qty':5,'price':150,'fee':2}]
    trades=[dict(t,ticker='TEST') for t in trades]
    cp_result=analyze_account('美股',trades,up_to='2026-01-31')['TEST']
    cp=_state_to_checkpoint('美股','TEST','2026-01-31',cp_result['_state'])
    full=analyze_account('美股',trades)['TEST']
    resumed=analyze_account('美股',trades,checkpoints={'TEST':cp})['TEST']
    for key in ['total_cost','realized_pnl','current_qty','total_fee']:
        assert resumed[key]==pytest.approx(full[key])


def test_snapshot_uses_one_cash_definition_and_own_twd_capital():
    accounts={'台股':dict(inferred_cash=1000,inferred_cash_twd=1000,invested_twd=10000,market_value_twd=2000),'美股':dict(invested_twd=32000),'爸媽美股':dict(invested_twd=16000)}
    rows=build_snapshot_rows({'accounts':accounts,'cash':{'twd_equivalent':1000},'invested':{'台股':10000,'美股':1000,'爸媽美股':500}})
    assert rows[0]['cash_twd']==rows[0]['allocation']['cash_twd']==1000
    assert rows[-1]['invested_twd']==42000
