import { RotateCcw, Save, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { api } from '../api/client'
import { usePrivacy } from '../context/PrivacyContext'
import { money, percent, pnlClass } from '../utils/format'

const NUMERIC_FIELDS = ['cost', 'cash_amount', 'value']

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object || {}, key)
}

function parseAmount(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export default function ManualValueEditor({ investments = [], onSaved }) {
  const { hideAmounts } = usePrivacy()
  const [saving, setSaving] = useState('')
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState({})
  const dirtyIds = useMemo(() => Object.keys(drafts), [drafts])
  const hasChanges = dirtyIds.length > 0

  function rowCurrency(row) {
    return drafts[row.id]?.currency ?? row.currency ?? 'TWD'
  }

  function inputValue(row, key) {
    const draft = drafts[row.id]
    if (hasOwn(draft, key)) return draft[key]
    return row[key] ?? 0
  }

  function numericValue(row, key) {
    const draft = drafts[row.id]
    if (hasOwn(draft, key)) return parseAmount(draft[key])
    return Number(row[key] || 0)
  }

  function update(row, patch) {
    setDrafts((current) => ({
      ...current,
      [row.id]: { ...(current[row.id] || {}), ...patch },
    }))
  }

  function updateNumber(row, key, value) {
    update(row, { [key]: value })
  }

  function clearDraft(row) {
    setDrafts((current) => {
      const next = { ...current }
      delete next[row.id]
      return next
    })
  }

  function payloadFor(row) {
    const draft = drafts[row.id] || {}
    const numericPayload = {}
    NUMERIC_FIELDS.forEach((key) => {
      numericPayload[key] = hasOwn(draft, key) ? parseAmount(draft[key]) : Number(row[key] || 0)
    })
    return {
      name: draft.name ?? row.name,
      asset_type: draft.asset_type ?? row.asset_type,
      ...numericPayload,
      currency: rowCurrency(row),
    }
  }

  async function saveRow(row) {
    if (!drafts[row.id]) return
    setSaving(row.id)
    setError('')
    try {
      await api.updateInvestment(row.id, payloadFor(row))
      clearDraft(row)
      onSaved?.()
    } catch (err) {
      setError(err.message || '儲存失敗')
    } finally {
      setSaving('')
    }
  }

  async function saveAll() {
    const rows = investments.filter((row) => drafts[row.id])
    if (!rows.length) return
    setSaving('all')
    setError('')
    try {
      await Promise.all(rows.map((row) => api.updateInvestment(row.id, payloadFor(row))))
      setDrafts({})
      onSaved?.()
    } catch (err) {
      setError(err.message || '儲存失敗')
    } finally {
      setSaving('')
    }
  }

  async function addInvestment() {
    setError('')
    try {
      await api.createInvestment({
        name: '新增標的',
        asset_type: '其他',
        cost: 0,
        cash_amount: 0,
        value: 0,
        currency: 'TWD',
      })
      onSaved?.()
    } catch (err) {
      setError(err.message || '新增失敗')
    }
  }

  async function removeInvestment(row) {
    if (!window.confirm(`刪除 ${row.name}？`)) return
    setError('')
    try {
      await api.deleteInvestment(row.id)
      onSaved?.()
    } catch (err) {
      setError(err.message || '刪除失敗')
    }
  }

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-panel px-3 py-3 sm:px-4">
        <div className="text-sm font-medium">基金與其他投資</div>
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={saveAll}
            disabled={!hasChanges || saving === 'all'}
            className="inline-flex items-center gap-2 rounded-md border border-emerald-500 bg-emerald-500/15 px-3 py-2 text-sm text-emerald-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Save size={15} />
            儲存變更
          </button>
          <button
            type="button"
            onClick={() => setDrafts({})}
            disabled={!hasChanges || saving === 'all'}
            className="rounded-md border border-line px-3 py-2 text-slate-300 hover:border-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
            title="取消未儲存變更"
          >
            <RotateCcw size={15} />
          </button>
          <button type="button" onClick={addInvestment} className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-sm text-sky-100">
            新增標的
          </button>
        </div>
      </div>
      {error ? <div className="border-b border-rose-900/60 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</div> : null}
      <div className="divide-y divide-line">
        {investments.map((row) => {
          const draft = drafts[row.id] || {}
          const isDirty = Boolean(drafts[row.id])
          const currency = rowCurrency(row)
          const cost = numericValue(row, 'cost')
          const cash = numericValue(row, 'cash_amount')
          const value = numericValue(row, 'value')
          const currentTotal = cash + value
          const cashRatio = currentTotal > 0 ? cash / currentTotal : null
          const pnl = currentTotal - cost
          const roi = cost > 0 ? pnl / cost : null
          const rowSaving = saving === row.id || saving === 'all'
          return (
            <div key={row.id} className="grid gap-3 px-3 py-3 sm:px-4 lg:grid-cols-[1.1fr_0.72fr_0.58fr_0.82fr_0.82fr_0.82fr_1fr_auto] lg:items-center">
              <div className="grid grid-cols-[1fr_auto] gap-2 lg:block">
                <input
                  className="min-w-0 rounded-md border border-line bg-[#0b1020] px-3 py-2 outline-none focus:border-sky-500"
                  value={draft.name ?? row.name}
                  onChange={(event) => update(row, { name: event.target.value })}
                  disabled={rowSaving}
                />
                <button
                  type="button"
                  onClick={() => removeInvestment(row)}
                  className="rounded-md border border-line px-3 text-slate-400 hover:border-rose-500 hover:text-rose-300 lg:hidden"
                  title="刪除"
                >
                  <Trash2 size={16} />
                </button>
              </div>
              <select
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
                value={draft.asset_type ?? row.asset_type}
                onChange={(event) => update(row, { asset_type: event.target.value })}
                disabled={rowSaving}
              >
                <option value="台股">台股</option>
                <option value="美股">美股</option>
                <option value="其他">其他</option>
              </select>
              <select
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
                value={currency}
                onChange={(event) => update(row, { currency: event.target.value })}
                disabled={rowSaving}
              >
                <option value="TWD">TWD</option>
                <option value="USD">USD</option>
              </select>
              <label className="grid gap-1 text-xs text-slate-400 lg:block">
                <span>投入金額</span>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={inputValue(row, 'cost')}
                  onChange={(event) => updateNumber(row, 'cost', event.target.value)}
                  disabled={rowSaving}
                />
              </label>
              <label className="grid gap-1 text-xs text-slate-400 lg:block">
                <span>現金量</span>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={inputValue(row, 'cash_amount')}
                  onChange={(event) => updateNumber(row, 'cash_amount', event.target.value)}
                  disabled={rowSaving}
                />
              </label>
              <label className="grid gap-1 text-xs text-slate-400 lg:block">
                <span>市值</span>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={inputValue(row, 'value')}
                  onChange={(event) => updateNumber(row, 'value', event.target.value)}
                  disabled={rowSaving}
                />
              </label>
              <div className={`rounded-md bg-panel/60 px-3 py-2 text-right text-sm lg:bg-transparent lg:px-0 ${pnlClass(pnl)}`}>
                <div className="text-xs text-slate-400">現金 {percent(cashRatio)}</div>
                <div>{hideAmounts ? percent(roi) : `${money(pnl, currency)} / ${percent(roi)}`}</div>
                {rowSaving ? <span className="ml-2 text-slate-400">儲存中</span> : isDirty ? <span className="ml-2 text-amber-300">未儲存</span> : null}
              </div>
              <div className="flex justify-end gap-1">
                {isDirty ? (
                  <>
                    <button
                      type="button"
                      onClick={() => saveRow(row)}
                      disabled={rowSaving}
                      className="rounded-md border border-emerald-500/70 p-2 text-emerald-100 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-40"
                      title="儲存"
                    >
                      <Save size={16} />
                    </button>
                    <button
                      type="button"
                      onClick={() => clearDraft(row)}
                      disabled={rowSaving}
                      className="rounded-md border border-line p-2 text-slate-400 hover:border-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                      title="取消"
                    >
                      <RotateCcw size={16} />
                    </button>
                  </>
                ) : null}
                <button
                  type="button"
                  onClick={() => removeInvestment(row)}
                  className="hidden rounded-md p-2 text-slate-400 hover:bg-panel hover:text-rose-300 lg:block"
                  title="刪除"
                >
                  <Trash2 size={17} />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
