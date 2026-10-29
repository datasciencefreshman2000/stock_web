import test from 'node:test'
import assert from 'node:assert/strict'
import { creditPaymentState, paymentSources } from '../src/utils/creditPayments.js'
const rows=[{id:'cash',name:'國泰現金',currency:'TWD',amount:50000},
  {id:'debt',name:'信用卡欠錢',currency:'TWD',amount:-30000},
  {id:'receivable',name:'公司欠錢 (待收款)',currency:'TWD',amount:90000},
  {id:'usd',name:'國泰現金',currency:'USD',amount:1000}]
const draft={source_id:'cash',currency:'TWD',mode:'partial',amount:'20000'}
test('partial payment previews reduced cash and debt without another expense',()=>{
  const state=creditPaymentState(rows,draft)
  assert.equal(state.error,'');assert.equal(state.sourceAfter,30000);assert.equal(state.owingAfter,10000)
})
test('pay all uses latest full debt, not the partial amount draft',()=>{
  const state=creditPaymentState(rows,{...draft,mode:'all'})
  assert.equal(state.amount,30000);assert.equal(state.owingAfter,0)
})
test('only same-currency cash can be selected',()=>{
  assert.deepEqual(paymentSources(rows,'TWD').map(row=>row.id),['cash'])
})
test('overpayment, insufficient cash, zero and fractional cents are blocked',()=>{
  for (const amount of ['30001','0','1.001']) assert.ok(creditPaymentState(rows,{...draft,amount}).error)
  assert.ok(creditPaymentState(rows.map(row=>row.id==='cash'?{...row,amount:100}:row),draft).error)
})
test('fully paid and unconfigured currencies cannot submit',()=>{
  assert.ok(creditPaymentState(rows.map(row=>row.id==='debt'?{...row,amount:0}:row),draft).error)
  assert.ok(creditPaymentState(rows,{...draft,currency:'USD',source_id:'usd'}).error)
})
