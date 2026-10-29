export const CREDIT_DEBT = '信用卡欠錢'
export function paymentSources(rows, currency) {
  return rows.filter(row => row.currency === currency && !/欠錢|待收|待還/.test(row.name)
    && !['負債', '應收款'].includes(row.category))
}
export function creditPaymentState(rows, draft) {
  const debt = rows.find(row => row.name === CREDIT_DEBT && row.currency === draft.currency)
  const sources = paymentSources(rows, draft.currency)
  const source = sources.find(row => row.id === draft.source_id)
  const owing = Math.max(0, -Number(debt?.amount || 0))
  const amount = draft.mode === 'all' ? owing : Number(draft.amount)
  const available = Number(source?.amount || 0)
  let error = ''
  if (!debt) error = '尚未設定此幣別的信用卡欠款。'
  else if (!owing) error = '此幣別已無待繳欠款。'
  else if (!source) error = '請選擇付款現金帳戶。'
  else if (!Number.isFinite(amount) || amount <= 0) error = '請輸入大於 0 的繳款金額。'
  else if (draft.mode !== 'all' && Math.abs(amount * 100 - Math.round(amount * 100)) > 0.000001) error = '繳款金額最多兩位小數。'
  else if (amount > owing) error = '繳款金額不能超過目前欠款。'
  else if (amount > available) error = '付款帳戶餘額不足，請換帳戶或改為部分繳款。'
  return { debt, sources, source, owing, amount, available, error,
    sourceAfter: Math.round((available - amount) * 1e8) / 1e8,
    owingAfter: Math.round((owing - amount) * 1e8) / 1e8 }
}
