import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { api } from '../../api/client'
import IncomeSourcePicker from './IncomeSourcePicker'
import { ACCOUNTS } from '../../constants'
import { INCOME_SOURCES, ON_HAND_CASH, OTHER_TYPES, today } from './constants'

export default function CapitalMovementPanel({ bankNames, positiveBankNames, onSaved }) {
  const [mode, setMode] = useState('income')
  const [exchange, setExchange] = useState(false)
  const [form, setForm] = useState({
    movement_date: today,
    income_source: INCOME_SOURCES[0],
    other_type: OTHER_TYPES[0],
    from_bucket: bankNames[0] || '',
    to_bucket: bankNames[0] || ACCOUNTS[0],
    amount: '',
    currency: 'TWD',
    to_amount: '',
    to_currency: 'USD',
    note: '',
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const incomeDestinations = [...bankNames, ACCOUNTS[0]]
  const transferBuckets = [...bankNames, ACCOUNTS[0], ACCOUNTS[1]]
  const transferDestinations = [...transferBuckets, ON_HAND_CASH]
  const expenseSources = positiveBankNames

  useEffect(() => {
    const fromOptions = mode === 'expense' ? expenseSources : transferBuckets
    const toOptions = mode === 'income' ? incomeDestinations : transferDestinations
    setForm((current) => {
      const next = { ...current }
      if ((mode === 'transfer' || mode === 'expense') && !fromOptions.includes(next.from_bucket)) {
        next.from_bucket = fromOptions[0] || ''
      }
      if ((mode === 'income' || mode === 'transfer') && !toOptions.includes(next.to_bucket)) {
        next.to_bucket = toOptions[0] || ''
      }
      return next.from_bucket === current.from_bucket && next.to_bucket === current.to_bucket ? current : next
    })
    if (mode !== 'transfer') setExchange(false)
  }, [mode, bankNames, positiveBankNames])

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      let payload = {
        movement_date: form.movement_date,
        from_bucket: null,
        to_bucket: form.to_bucket,
        amount: Number(form.amount || 0),
        currency: form.currency,
        to_amount: exchange && mode === 'transfer' ? Number(form.to_amount || 0) : null,
        to_currency: exchange && mode === 'transfer' ? form.to_currency : null,
        note: form.note,
      }

      if (mode === 'income') {
        payload = { ...payload, from_bucket: null, to_bucket: form.to_bucket, note: [form.income_source, form.note].filter(Boolean).join(' - ') }
      } else if (mode === 'transfer') {
        payload = { ...payload, from_bucket: form.from_bucket, to_bucket: form.to_bucket }
      } else if (mode === 'expense') {
        payload = { ...payload, from_bucket: form.from_bucket, to_bucket: '支出' }
      } else {
        payload = { ...payload, from_bucket: null, to_bucket: form.other_type, note: [form.other_type, form.note].filter(Boolean).join(' - ') }
      }

      await api.createCapitalMovement(payload)
      setMessage('已記錄資金異動。')
      setForm((current) => ({ ...current, amount: '', note: '' }))
      onSaved?.()
    } catch (err) {
      setMessage(err.message || '資金異動儲存失敗')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">資金異動</div>
      <div className="grid grid-cols-4 gap-2 p-3">
        {[
          ['income', '收入'],
          ['transfer', '調動'],
          ['expense', '支出'],
          ['other', '其他'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setMode(key)}
            className={`rounded-md border px-2 py-2 text-sm transition hover:-translate-y-0.5 hover:border-sky-400/70 hover:bg-sky-500/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.98] ${mode === key ? 'border-sky-400 bg-sky-500/15 text-white shadow-sm shadow-sky-950/40' : 'border-line bg-panel text-slate-300'}`}
          >
            {label}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="grid gap-3 px-3 pb-3 sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
        <label className="grid gap-1 text-xs text-slate-400">
          日期
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" type="date" value={form.movement_date} onChange={(event) => update('movement_date', event.target.value)} />
        </label>

        {mode === 'income' ? (
          <IncomeSourcePicker value={form.income_source} onChange={(value) => update('income_source', value)} />
        ) : null}

        {mode === 'transfer' || mode === 'expense' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            從哪裡
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.from_bucket} onChange={(event) => update('from_bucket', event.target.value)}>
              {(mode === 'expense' ? expenseSources : transferBuckets).map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        {mode === 'income' || mode === 'transfer' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            放到哪裡
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.to_bucket} onChange={(event) => update('to_bucket', event.target.value)}>
              {(mode === 'income' ? incomeDestinations : transferDestinations).map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        {mode === 'other' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            類型
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.other_type} onChange={(event) => update('other_type', event.target.value)}>
              {OTHER_TYPES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        <label className="grid gap-1 text-xs text-slate-400">
          金額
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white" type="number" min="0" step="0.01" value={form.amount} onChange={(event) => update('amount', event.target.value)} required />
        </label>
        <label className="grid max-w-20 gap-1 text-[11px] text-slate-500">
          幣別
          <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.currency} onChange={(event) => update('currency', event.target.value)}>
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </label>
        {mode === 'transfer' ? (
          <label className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-300">
            <input className="min-h-0" type="checkbox" checked={exchange} onChange={(event) => setExchange(event.target.checked)} />
            換匯
          </label>
        ) : null}
        {mode === 'transfer' && exchange ? (
          <>
            <label className="grid gap-1 text-xs text-slate-400">
              換成金額
              <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white" type="number" min="0" step="0.01" value={form.to_amount} onChange={(event) => update('to_amount', event.target.value)} required />
            </label>
            <label className="grid max-w-20 gap-1 text-[11px] text-slate-500">
              換成
              <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.to_currency} onChange={(event) => update('to_currency', event.target.value)}>
                <option value="USD">USD</option>
                <option value="TWD">TWD</option>
              </select>
            </label>
          </>
        ) : null}
        <button
          className={`flex items-center justify-center gap-2 rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-white transition active:scale-[0.99] disabled:opacity-70 lg:col-span-1 ${saving ? 'submit-pulse' : 'hover:bg-sky-400'}`}
          disabled={saving}
        >
          {saving ? <Loader2 size={15} className="animate-spin" /> : null}
          {saving ? '儲存中' : '新增異動'}
        </button>
        <label className="grid gap-1 text-xs text-slate-400 sm:col-span-2 lg:col-span-5">
          備註
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.note} onChange={(event) => update('note', event.target.value)} />
        </label>
        {message ? <div className="text-xs text-slate-400 lg:col-span-6">{message}</div> : null}
      </form>
    </section>
  )
}
