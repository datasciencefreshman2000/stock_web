import { useMemo, useState } from 'react'
import { ArrowLeft, ChevronLeft, ChevronRight, Edit3, Save, Trash2, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import MobileNumericInput from '../components/cash/MobileNumericInput'
import { CREDIT_CARD_DEBT, EXPENSE_TAGS, ON_HAND_CASH, OTHER_TYPES } from '../components/cash/constants'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import { ACCOUNTS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useCapitalMovementsQuery, useManualQuery } from '../hooks/queries'
import { api } from '../api/client'
import { queryKeys } from '../lib/queryClient'
import { money } from '../utils/format'

function unique(items) {
  return [...new Set(items.filter(Boolean))]
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function shiftMonth(value, offset) {
  const [year, month] = value.split('-').map(Number)
  const date = new Date(year, month - 1 + offset, 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

function movementType(row) {
  if (row.to_bucket === '支出') return 'expense'
  if (row.from_bucket) return 'transfer'
  if (OTHER_TYPES.includes(row.to_bucket)) return 'other'
  return 'income'
}

const TYPE_LABELS = {
  all: '全部',
  income: '收入',
  transfer: '調動',
  expense: '支出',
  other: '其他',
}

function splitExpenseNote(note = '') {
  const [prefix = '', ...detailParts] = note.split(' - ')
  const candidates = prefix.split(',').map((item) => item.trim()).filter(Boolean)
  const tags = candidates.filter((item) => EXPENSE_TAGS.includes(item))
  return {
    tags: tags.length ? tags : ['其他'],
    note: tags.length ? detailParts.join(' - ') : note,
  }
}

function editFormFromMovement(row) {
  const type = movementType(row)
  const expense = type === 'expense' ? splitExpenseNote(row.note) : { tags: [], note: row.note || '' }
  return {
    movement_date: row.movement_date || '',
    from_bucket: row.from_bucket || '',
    to_bucket: row.to_bucket || '',
    amount: String(row.amount ?? ''),
    currency: row.currency || 'TWD',
    to_amount: row.to_amount === null || row.to_amount === undefined ? '' : String(row.to_amount),
    to_currency: row.to_currency || row.currency || 'TWD',
    tags: expense.tags,
    note: expense.note,
    type,
  }
}

function payloadFromForm(form) {
  const tags = form.tags.length ? form.tags : ['其他']
  const note = form.type === 'expense'
    ? [tags.join(', '), form.note.trim()].filter(Boolean).join(' - ')
    : form.note.trim()
  return {
    movement_date: form.movement_date,
    from_bucket: form.from_bucket || null,
    to_bucket: form.to_bucket,
    amount: Number(form.amount),
    currency: form.currency,
    to_amount: form.to_amount ? Number(form.to_amount) : null,
    to_currency: form.to_amount ? form.to_currency : null,
    note,
  }
}

function displayNote(row) {
  if (movementType(row) !== 'expense') return { tags: [], note: row.note || '' }
  return splitExpenseNote(row.note)
}

export default function CashLedger() {
  const { hideAmounts } = usePrivacy()
  const [month, setMonth] = useState(currentMonth)
  const movementsQuery = useCapitalMovementsQuery(month)
  const manualQuery = useManualQuery()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('all')
  const [editingId, setEditingId] = useState('')
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const movements = useMemo(() => {
    const rows = [...(movementsQuery.data?.movements || [])]
    rows.sort((a, b) => (
      String(b.movement_date || '').localeCompare(String(a.movement_date || ''))
      || String(b.created_at || '').localeCompare(String(a.created_at || ''))
    ))
    return filter === 'all' ? rows : rows.filter((row) => movementType(row) === filter)
  }, [filter, movementsQuery.data?.movements])

  const bucketOptions = useMemo(() => unique([
    ...(movementsQuery.data?.movements || []).flatMap((row) => [row.from_bucket, row.to_bucket]),
    ...(manualQuery.data?.cash || []).map((row) => row.name),
    ...ACCOUNTS,
    ON_HAND_CASH,
    CREDIT_CARD_DEBT,
  ]).filter((item) => item !== '支出'), [manualQuery.data?.cash, movementsQuery.data?.movements])

  function startEdit(row) {
    setEditingId(row.id)
    setForm(editFormFromMovement(row))
    setMessage('')
  }

  function selectMonth(nextMonth) {
    setMonth(nextMonth)
    setEditingId('')
    setForm(null)
    setMessage('')
  }

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function toggleTag(tag) {
    setForm((current) => {
      const selected = current.tags.includes(tag)
      const tags = selected ? current.tags.filter((item) => item !== tag) : [...current.tags, tag]
      return { ...current, tags: tags.length ? tags : ['其他'] }
    })
  }

  function markDependentDataStale() {
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.summary, refetchType: 'none' }),
      queryClient.invalidateQueries({ queryKey: ['portfolio'], refetchType: 'none' }),
      queryClient.invalidateQueries({ queryKey: queryKeys.manual, exact: true, refetchType: 'none' }),
    ])
  }

  function replaceMovement(movement) {
    queryClient.setQueryData(queryKeys.capitalMovements(month), (current) => ({
      ...(current || {}),
      movements: (current?.movements || []).flatMap((row) => {
        if (row.id !== movement.id) return [row]
        return String(movement.movement_date || '').startsWith(month) ? [movement] : []
      }),
    }))
    markDependentDataStale()
  }

  function removeMovementFromCache(movementId) {
    queryClient.setQueryData(queryKeys.capitalMovements(month), (current) => ({
      ...(current || {}),
      movements: (current?.movements || []).filter((row) => row.id !== movementId),
    }))
    markDependentDataStale()
  }

  async function save(event) {
    event.preventDefault()
    const amount = Number(form?.amount)
    if (!form?.movement_date || !form?.to_bucket || !Number.isFinite(amount) || amount <= 0) {
      setMessage('請確認日期、帳戶與金額。')
      return
    }
    setSaving(true)
    setMessage('')
    try {
      const response = await api.updateCapitalMovement(editingId, payloadFromForm(form))
      replaceMovement(response.movement)
      setEditingId('')
      setForm(null)
      setMessage('記帳紀錄與帳戶餘額已更新。')
    } catch (error) {
      setMessage(error.message || '更新失敗')
    } finally {
      setSaving(false)
    }
  }

  async function remove(row) {
    if (!window.confirm(`刪除 ${row.movement_date} 的這筆記帳紀錄？帳戶餘額也會一併沖回。`)) return
    setSaving(true)
    setMessage('')
    try {
      await api.deleteCapitalMovement(row.id)
      removeMovementFromCache(row.id)
      if (editingId === row.id) {
        setEditingId('')
        setForm(null)
      }
      setMessage('記帳紀錄已刪除，帳戶餘額已沖回。')
    } catch (error) {
      setMessage(error.message || '刪除失敗')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-5">
      <header className="flex items-center gap-3">
        <Link
          to="/cash"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line text-slate-300 transition hover:border-sky-500 hover:text-white"
          aria-label="返回現金"
          title="返回現金"
        >
          <ArrowLeft size={17} />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold">記帳紀錄</h1>
          <p className="mt-1 text-sm text-slate-400">檢視並修正收入、調動與支出</p>
        </div>
      </header>

      <section className="grid grid-cols-[2.5rem_minmax(0,1fr)_2.5rem] items-center gap-2 rounded-md border border-line bg-surface p-2 sm:ml-auto sm:max-w-sm">
        <button
          type="button"
          onClick={() => selectMonth(shiftMonth(month, -1))}
          className="grid h-10 w-10 place-items-center rounded-md text-slate-300 transition hover:bg-panel hover:text-white active:scale-[0.96]"
          aria-label="上一個月"
          title="上一個月"
        >
          <ChevronLeft size={18} />
        </button>
        <input
          type="month"
          value={month}
          onChange={(event) => selectMonth(event.target.value || currentMonth())}
          className="min-w-0 rounded-md border border-line bg-[#0b1020] px-3 py-2 text-center text-sm font-medium text-white"
          aria-label="選擇記帳月份"
        />
        <button
          type="button"
          onClick={() => selectMonth(shiftMonth(month, 1))}
          disabled={month >= currentMonth()}
          className="grid h-10 w-10 place-items-center rounded-md text-slate-300 transition hover:bg-panel hover:text-white active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="下一個月"
          title="下一個月"
        >
          <ChevronRight size={18} />
        </button>
      </section>

      <div className="grid grid-cols-5 gap-1 rounded-md border border-line bg-surface p-1">
        {Object.entries(TYPE_LABELS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilter(key)}
            className={`rounded-md px-1 py-2 text-xs transition ${filter === key ? 'bg-sky-500/15 text-white' : 'text-slate-400 hover:bg-panel hover:text-white'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {message ? <div className={`rounded-md border px-4 py-3 text-sm ${message.includes('已') ? 'border-emerald-900/60 bg-emerald-950/30 text-emerald-200' : 'border-rose-900/60 bg-rose-950/30 text-rose-200'}`}>{message}</div> : null}
      {movementsQuery.isLoading ? <LoadingBlock label="正在讀取記帳紀錄" /> : null}
      {movementsQuery.error ? <ErrorBlock error={movementsQuery.error} /> : null}

      {!movementsQuery.isLoading && !movementsQuery.error ? (
        <section className="overflow-hidden rounded-md border border-line bg-surface">
          <div className="divide-y divide-line">
            {movements.map((row) => {
              const type = movementType(row)
              const details = displayNote(row)
              const editing = editingId === row.id && form
              return (
                <div key={row.id} className="px-3 py-3 sm:px-4">
                  {editing ? (
                    <form onSubmit={save} className="grid gap-3">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <label className="grid gap-1 text-xs text-slate-400">
                          日期
                          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" type="date" value={form.movement_date} onChange={(event) => update('movement_date', event.target.value)} />
                        </label>
                        {type !== 'income' && type !== 'other' ? (
                          <label className="grid gap-1 text-xs text-slate-400">
                            從哪裡
                            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.from_bucket} onChange={(event) => update('from_bucket', event.target.value)}>
                              {bucketOptions.map((item) => <option key={item}>{item}</option>)}
                            </select>
                          </label>
                        ) : null}
                        {type !== 'expense' ? (
                          <label className="grid gap-1 text-xs text-slate-400">
                            放到哪裡
                            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.to_bucket} onChange={(event) => update('to_bucket', event.target.value)}>
                              {bucketOptions.map((item) => <option key={item}>{item}</option>)}
                            </select>
                          </label>
                        ) : null}
                        <div className="grid gap-1 text-xs text-slate-400">
                          金額
                          <MobileNumericInput
                            value={form.amount}
                            onChange={(value) => update('amount', value)}
                            label="記帳金額"
                            currency={form.currency}
                            onCurrencyChange={(value) => update('currency', value)}
                            allowZero={false}
                            masked={hideAmounts}
                          />
                        </div>
                        {form.to_amount !== '' ? (
                          <div className="grid gap-1 text-xs text-slate-400">
                            換入金額
                            <MobileNumericInput
                              value={form.to_amount}
                              onChange={(value) => update('to_amount', value)}
                              label="換入金額"
                              currency={form.to_currency}
                              onCurrencyChange={(value) => update('to_currency', value)}
                              allowZero={false}
                              masked={hideAmounts}
                            />
                          </div>
                        ) : null}
                      </div>
                      {type === 'expense' ? (
                        <div className="flex flex-wrap gap-2">
                          {EXPENSE_TAGS.map((tag) => (
                            <button
                              key={tag}
                              type="button"
                              onClick={() => toggleTag(tag)}
                              className={`rounded-full border px-3 py-1 text-xs ${form.tags.includes(tag) ? 'border-sky-400 bg-sky-500/15 text-sky-100' : 'border-line text-slate-400'}`}
                            >
                              {tag}
                            </button>
                          ))}
                        </div>
                      ) : null}
                      <label className="grid gap-1 text-xs text-slate-400">
                        備註
                        <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.note} onChange={(event) => update('note', event.target.value)} />
                      </label>
                      <div className="flex justify-end gap-2">
                        <button type="submit" disabled={saving} className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/70 bg-emerald-500/15 px-3 py-2 text-sm text-emerald-100 disabled:opacity-50">
                          <Save size={15} /> 儲存
                        </button>
                        <button type="button" disabled={saving} onClick={() => { setEditingId(''); setForm(null) }} className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-2 text-sm text-slate-300 disabled:opacity-50">
                          <X size={15} /> 取消
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs text-slate-500">{row.movement_date}</span>
                          <span className="rounded-sm bg-panel px-1.5 py-0.5 text-[11px] text-slate-300">{TYPE_LABELS[type]}</span>
                          {details.tags.map((tag) => <span key={tag} className="rounded-full border border-sky-500/30 px-2 py-0.5 text-[10px] text-sky-200">{tag}</span>)}
                        </div>
                        <div className="mt-1 text-sm text-slate-200">
                          {row.from_bucket ? `${row.from_bucket} → ` : ''}{row.to_bucket}
                        </div>
                        {details.note ? <div className="mt-1 truncate text-xs text-slate-500">{details.note}</div> : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-right text-sm font-medium tabular-nums text-white">
                          {hideAmounts ? maskAmount(money(row.amount, row.currency)) : money(row.amount, row.currency)}
                        </div>
                        <button type="button" onClick={() => startEdit(row)} disabled={saving} className="grid h-8 w-8 place-items-center rounded-md border border-line text-slate-400 hover:border-sky-500 hover:text-sky-200" aria-label="修改記帳紀錄" title="修改">
                          <Edit3 size={14} />
                        </button>
                        <button type="button" onClick={() => remove(row)} disabled={saving} className="grid h-8 w-8 place-items-center rounded-md border border-line text-slate-400 hover:border-rose-500 hover:text-rose-300" aria-label="刪除記帳紀錄" title="刪除">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
            {!movements.length ? <div className="px-4 py-8 text-center text-sm text-slate-500">{month} 沒有符合條件的記帳紀錄</div> : null}
          </div>
        </section>
      ) : null}
    </div>
  )
}
