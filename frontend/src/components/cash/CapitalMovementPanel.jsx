import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { api } from '../../api/client'
import IncomeSourcePicker from './IncomeSourcePicker'
import NumericKeypad from './NumericKeypad'
import { ACCOUNTS } from '../../constants'
import { CREDIT_CARD_DEBT, EXPENSE_TAGS, INCOME_SOURCES, ON_HAND_CASH, OTHER_TYPES, today } from './constants'

function unique(items) {
  return [...new Set(items.filter(Boolean))]
}

export default function CapitalMovementPanel({ bankNames, positiveBankNames, onSaved }) {
  const [mode, setMode] = useState('income')
  const [exchange, setExchange] = useState(false)
  const [form, setForm] = useState({
    movement_date: today,
    income_source: INCOME_SOURCES[0],
    expense_tags: [EXPENSE_TAGS[0]],
    other_type: OTHER_TYPES[0],
    from_bucket: bankNames[0] || ON_HAND_CASH,
    to_bucket: bankNames[0] || ACCOUNTS[0],
    amount: '',
    currency: 'TWD',
    to_amount: '',
    to_currency: 'USD',
    note: '',
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const incomeDestinations = useMemo(() => unique([...bankNames, ON_HAND_CASH, ACCOUNTS[0]]), [bankNames])
  const transferBuckets = useMemo(() => unique([...bankNames, ON_HAND_CASH, ACCOUNTS[0], ACCOUNTS[1]]), [bankNames])
  const transferDestinations = useMemo(() => unique([...transferBuckets, CREDIT_CARD_DEBT]), [transferBuckets])
  const expenseSources = useMemo(
    () => unique([ON_HAND_CASH, ...positiveBankNames, CREDIT_CARD_DEBT]),
    [positiveBankNames],
  )

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
  }, [mode, expenseSources, incomeDestinations, transferBuckets, transferDestinations])

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function noteWithTag(tag, note) {
    return [tag, note.trim()].filter(Boolean).join(' - ')
  }

  function noteWithTags(tags, note) {
    return noteWithTag(tags.join(', '), note)
  }

  function updateAmount(value) {
    const cleaned = value.replace(/[^0-9.]/g, '')
    const [integer = '', ...decimalParts] = cleaned.split('.')
    const decimal = decimalParts.join('').slice(0, 2)
    update('amount', decimalParts.length ? `${integer || '0'}.${decimal}` : integer)
  }

  function toggleExpenseTag(tag) {
    setForm((current) => {
      const selected = current.expense_tags.includes(tag)
      return {
        ...current,
        expense_tags: selected
          ? current.expense_tags.filter((item) => item !== tag)
          : [...current.expense_tags, tag],
      }
    })
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
        note: form.note.trim(),
      }

      if (mode === 'income') {
        payload = { ...payload, to_bucket: form.to_bucket, note: noteWithTag(form.income_source, form.note) }
      } else if (mode === 'transfer') {
        payload = { ...payload, from_bucket: form.from_bucket, to_bucket: form.to_bucket }
      } else if (mode === 'expense') {
        payload = {
          ...payload,
          from_bucket: form.from_bucket,
          to_bucket: '支出',
          note: noteWithTags(form.expense_tags, form.note),
        }
      } else {
        payload = { ...payload, to_bucket: form.other_type, note: noteWithTag(form.other_type, form.note) }
      }

      await api.createCapitalMovement(payload)
      await onSaved?.()
      setMessage('已儲存並更新現金資料')
      setForm((current) => ({ ...current, amount: '', to_amount: '', note: '' }))
    } catch (err) {
      setMessage(err.message || '儲存失敗，請稍後再試')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">資金紀錄</div>
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
            aria-pressed={mode === key}
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
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white"
            type={mode === 'expense' ? 'text' : 'number'}
            inputMode={mode === 'expense' ? 'none' : 'decimal'}
            pattern={mode === 'expense' ? '[0-9.]*' : undefined}
            min="0"
            step="0.01"
            value={form.amount}
            onChange={(event) => (mode === 'expense' ? updateAmount(event.target.value) : update('amount', event.target.value))}
            required
          />
        </label>
        {mode !== 'expense' ? (
          <label className="grid max-w-20 gap-1 text-[11px] text-slate-500">
            幣別
            <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.currency} onChange={(event) => update('currency', event.target.value)}>
              <option value="TWD">TWD</option>
              <option value="USD">USD</option>
            </select>
          </label>
        ) : null}
        {mode === 'transfer' ? (
          <label className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-300">
            <input className="min-h-0" type="checkbox" checked={exchange} onChange={(event) => setExchange(event.target.checked)} />
            換匯
          </label>
        ) : null}
        {mode === 'transfer' && exchange ? (
          <>
            <label className="grid gap-1 text-xs text-slate-400">
              換入金額
              <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white" type="number" min="0" step="0.01" value={form.to_amount} onChange={(event) => update('to_amount', event.target.value)} required />
            </label>
            <label className="grid max-w-20 gap-1 text-[11px] text-slate-500">
              換入幣別
              <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.to_currency} onChange={(event) => update('to_currency', event.target.value)}>
                <option value="USD">USD</option>
                <option value="TWD">TWD</option>
              </select>
            </label>
          </>
        ) : null}

        {mode === 'expense' ? (
          <div className="sm:col-span-2 lg:col-span-6">
            <NumericKeypad
              value={form.amount}
              onChange={updateAmount}
              currency={form.currency}
              onCurrencyChange={(value) => update('currency', value)}
            />
          </div>
        ) : null}
        <button
          className={`flex items-center justify-center gap-2 rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-white transition active:scale-[0.99] disabled:opacity-70 lg:col-span-1 ${saving ? 'submit-pulse' : 'hover:bg-sky-400'}`}
          disabled={saving}
        >
          {saving ? <Loader2 size={15} className="animate-spin" /> : null}
          {saving ? '儲存中' : '儲存紀錄'}
        </button>

        {mode === 'expense' ? (
          <div className="grid gap-2 text-xs text-slate-400 sm:col-span-2 lg:col-span-6">
            支出 tag
            <div className="flex flex-wrap gap-2">
              {EXPENSE_TAGS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleExpenseTag(tag)}
                  aria-pressed={form.expense_tags.includes(tag)}
                  className={`rounded-full border px-3 py-1 text-xs transition hover:border-sky-400/70 hover:bg-sky-500/10 hover:text-white ${
                    form.expense_tags.includes(tag) ? 'border-sky-400 bg-sky-500/15 text-sky-100' : 'border-line bg-panel text-slate-300'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <label className="grid gap-1 text-xs text-slate-400 sm:col-span-2 lg:col-span-6">
          備註
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.note} onChange={(event) => update('note', event.target.value)} placeholder={mode === 'expense' ? '會自動加上支出 tag' : ''} />
        </label>
        {message ? <div className="text-xs text-slate-400 lg:col-span-6">{message}</div> : null}
      </form>
    </section>
  )
}
