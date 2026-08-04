import { ACCOUNTS } from '../constants'

export const COMBINED_HISTORY_ACCOUNT = '__combined__'
export const MASKED_VALUE = '••••'
export const HISTORY_ACCOUNT_OPTIONS = [
  ...ACCOUNTS.map((item) => ({ value: item, label: item })),
  {
    value: COMBINED_HISTORY_ACCOUNT,
    label: `${ACCOUNTS[0]} + ${ACCOUNTS[1]} + ${ACCOUNTS[2]}`,
  },
]

export function dateValue(date) {
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 10)
}

export function rangeFilters(type) {
  const end = new Date()
  const start = new Date()
  if (type === '1d') start.setDate(end.getDate())
  if (type === '7d') start.setDate(end.getDate() - 6)
  if (type === '1m') start.setMonth(end.getMonth() - 1)
  if (type === '3m') start.setMonth(end.getMonth() - 3)
  if (type === '1y') start.setFullYear(end.getFullYear() - 1)
  if (type === 'ytd') {
    start.setMonth(0)
    start.setDate(1)
  }
  return { start_date: dateValue(start), end_date: dateValue(end) }
}

export function tradeQty(trade) {
  return Number(trade.buy_qty || 0) > 0 ? Number(trade.buy_qty || 0) : Number(trade.sell_qty || 0)
}

export function tradeAmount(trade) {
  const total = Number(trade.total)
  if (!Number.isNaN(total) && total !== 0) return Math.abs(total)
  return Math.abs(Number(trade.price || 0) * tradeQty(trade))
}

export function tradeAccountRatio(trade, accountSummaries, fallbackAccount) {
  const account = trade.account || fallbackAccount
  const accountTotal = Number(accountSummaries?.[account]?.account_total || 0)
  const amount = tradeAmount(trade)
  return accountTotal > 0 && amount > 0 ? amount / accountTotal : null
}

export function compareTradesNewestFirst(a, b) {
  const dateCompare = String(b.date || '').localeCompare(String(a.date || ''))
  if (dateCompare) return dateCompare
  const createdCompare = String(b.created_at || '').localeCompare(String(a.created_at || ''))
  if (createdCompare) return createdCompare
  return String(b.id || '').localeCompare(String(a.id || ''))
}

export function tradeFormFromTrade(trade, fallbackAccount) {
  const isBuy = Number(trade.buy_qty || 0) > 0
  const fallback = fallbackAccount === COMBINED_HISTORY_ACCOUNT ? ACCOUNTS[0] : fallbackAccount
  return {
    account: trade.account || fallback,
    ticker: trade.ticker || '',
    date: trade.date || dateValue(new Date()),
    side: isBuy ? 'buy' : 'sell',
    qty: tradeQty(trade) ? String(tradeQty(trade)) : '',
    price: trade.price === null || trade.price === undefined ? '' : String(trade.price),
    fee: trade.fee === null || trade.fee === undefined ? '' : String(trade.fee || ''),
    note: trade.note || '',
  }
}

export function isTwTradeForm(form) {
  return form.account === ACCOUNTS[0]
}

export function tradePayloadFromForm(form) {
  const qty = Number(form.qty)
  return {
    account: form.account,
    ticker: form.ticker.trim().toUpperCase(),
    date: form.date,
    buy_qty: form.side === 'buy' ? qty : null,
    sell_qty: form.side === 'sell' ? qty : null,
    price: Number(form.price),
    fee: isTwTradeForm(form) ? 0 : Number(form.fee || 0),
    note: form.note,
  }
}
