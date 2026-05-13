import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import { ACCOUNTS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money } from '../utils/format'

const today = new Date().toISOString().slice(0, 10)

function estimateTwFee(price, qty) {
  return Math.max(Math.trunc(Number(price || 0) * Number(qty || 0) * 0.001425 * 0.6), 1)
}

function estimateTwTax(price, qty, ticker) {
  const isEtf = ['0050', '00981A'].includes(String(ticker).toUpperCase())
  return Math.trunc(Number(price || 0) * Number(qty || 0) * (isEtf ? 0.001 : 0.003))
}

function estimateCathayUsFee(price, qty) {
  return Number(price || 0) * Number(qty || 0) * 0.001
}

export default function TradeForm({ onSubmit, submitting }) {
  const { hideAmounts } = usePrivacy()
  const [form, setForm] = useState({
    account: '台股',
    ticker: '',
    side: 'buy',
    qty: '',
    price: '',
    date: today,
    fee: '',
    note: '',
  })
  const [tickers, setTickers] = useState([])
  const [tickerLoading, setTickerLoading] = useState(false)

  const isTw = form.account === '台股' || form.account === 'x'
  const cathayUsFee = useMemo(() => estimateCathayUsFee(form.price, form.qty), [form.price, form.qty])
  const fee = useMemo(() => (isTw ? estimateTwFee(form.price, form.qty) : Number(form.fee || 0)), [form, isTw])
  const tax = useMemo(
    () => (isTw && form.side === 'sell' ? estimateTwTax(form.price, form.qty, form.ticker) : 0),
    [form, isTw],
  )
  const gross = Number(form.price || 0) * Number(form.qty || 0)
  const total = form.side === 'buy' ? gross + fee : gross - fee - tax
  const tickerSuggestions = useMemo(() => {
    const keyword = form.ticker.trim().toUpperCase()
    if (!keyword) return tickers.slice(0, 12)
    return tickers
      .filter((ticker) => ticker.includes(keyword) || keyword.includes(ticker))
      .sort((a, b) => {
        const aStarts = a.startsWith(keyword) ? 0 : 1
        const bStarts = b.startsWith(keyword) ? 0 : 1
        return aStarts - bStarts || a.localeCompare(b)
      })
      .slice(0, 12)
  }, [form.ticker, tickers])

  useEffect(() => {
    let active = true
    setTickerLoading(true)
    api
      .getTrades(form.account)
      .then((data) => {
        if (!active) return
        const unique = [...new Set((data.trades || []).map((trade) => trade.ticker).filter(Boolean))]
        setTickers(unique.sort())
      })
      .catch(() => {
        if (active) setTickers([])
      })
      .finally(() => {
        if (active) setTickerLoading(false)
      })

    return () => {
      active = false
    }
  }, [form.account])

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function submit(event) {
    event.preventDefault()
    const qty = Number(form.qty)
    const payload = {
      account: form.account,
      ticker: form.ticker.trim().toUpperCase(),
      date: form.date,
      buy_qty: form.side === 'buy' ? qty : null,
      sell_qty: form.side === 'sell' ? qty : null,
      price: Number(form.price),
      fee: isTw ? 0 : Number(form.fee || 0),
      note: form.note,
    }
    onSubmit(payload)
  }

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-md border border-line bg-surface p-3 sm:p-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_1fr_1fr_auto] sm:gap-3">
        {ACCOUNTS.map((account) => (
          <button
            key={account}
            type="button"
            onClick={() => update('account', account)}
            className={`rounded-md border px-3 py-2 text-sm ${
              account === 'x' ? 'text-xs sm:px-2 sm:py-1.5' : ''
            } ${
              form.account === account ? 'border-sky-400 bg-sky-500/15 text-white' : 'border-line bg-panel text-slate-300'
            }`}
          >
            {account}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
        <label className="grid gap-2 text-sm">
          代號
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
            value={form.ticker}
            list="ticker-suggestions"
            onChange={(e) => update('ticker', e.target.value.toUpperCase())}
            placeholder={tickerLoading ? '讀取代號中...' : '輸入代號'}
            required
          />
          <datalist id="ticker-suggestions">
            {tickerSuggestions.map((ticker) => (
              <option key={ticker} value={ticker} />
            ))}
          </datalist>
        </label>
        <label className="grid gap-2 text-sm">
          日期
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" type="date" value={form.date} onChange={(e) => update('date', e.target.value)} required />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-3 sm:gap-4">
        <label className="grid gap-2 text-sm">
          買賣
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2" value={form.side} onChange={(e) => update('side', e.target.value)}>
            <option value="buy">買入</option>
            <option value="sell">賣出</option>
          </select>
        </label>
        <label className="grid gap-2 text-sm">
          股數
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" type="number" min="0" step="0.0001" value={form.qty} onChange={(e) => update('qty', e.target.value)} required />
        </label>
        <label className="grid gap-2 text-sm">
          價格
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
            type={hideAmounts ? 'password' : 'number'}
            min="0"
            step="0.0001"
            value={form.price}
            onChange={(e) => update('price', e.target.value)}
            required
          />
        </label>
      </div>

      {!isTw ? (
        <div className="grid gap-2 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span>美股手續費</span>
            <button
              type="button"
              onClick={() => update('fee', cathayUsFee.toFixed(2))}
              className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-100"
            >
              國泰 {hideAmounts ? maskAmount(money(cathayUsFee, 'USD')) : money(cathayUsFee, 'USD')}
            </button>
          </div>
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
            type={hideAmounts ? 'password' : 'number'}
            min="0"
            step="0.01"
            value={form.fee}
            onChange={(e) => update('fee', e.target.value)}
          />
        </div>
      ) : null}

      <label className="grid gap-2 text-sm">
        備註
        <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" value={form.note} onChange={(e) => update('note', e.target.value)} />
      </label>

      <div className="grid gap-2 rounded-md border border-line bg-panel p-3 text-xs text-slate-300 sm:grid-cols-3 sm:text-sm">
        <div>手續費：{hideAmounts ? maskAmount(money(fee)) : money(fee)}</div>
        <div>證交稅：{form.side === 'sell' ? (hideAmounts ? maskAmount(money(tax)) : money(tax)) : '--'}</div>
        <div>交易總額：{hideAmounts ? maskAmount(money(total)) : money(total)}</div>
      </div>

      <button disabled={submitting} className="rounded-md bg-sky-500 px-4 py-3 font-medium text-white disabled:opacity-60">
        {submitting ? '送出中' : '新增交易'}
      </button>
    </form>
  )
}
