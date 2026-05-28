import { Trash2 } from 'lucide-react'
import { useState } from 'react'

import { api } from '../api/client'
import { usePrivacy } from '../context/PrivacyContext'
import { money, percent, pnlClass } from '../utils/format'

export default function ManualValueEditor({ investments = [], usdRate = 31.316, onSaved }) {
  const { hideAmounts } = usePrivacy()
  const [currency, setCurrency] = useState('TWD')
  const [saving, setSaving] = useState('')
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState({})
  const divisor = currency === 'USD' ? usdRate : 1

  function display(value) {
    return Number(value || 0) / divisor
  }

  function stored(value) {
    return Number(value || 0) * divisor
  }

  function draftValue(row, key) {
    return drafts[row.id]?.[key] ?? display(row[key])
  }

  function update(row, patch) {
    setDrafts((current) => ({
      ...current,
      [row.id]: { ...(current[row.id] || {}), ...patch },
    }))
  }

  async function save(row, patch = {}) {
    const draft = { ...(drafts[row.id] || {}), ...patch }
    setSaving(row.id)
    setError('')
    try {
      await api.updateInvestment(row.id, {
        name: draft.name ?? row.name,
        asset_type: draft.asset_type ?? row.asset_type,
        cost: draft.cost === undefined ? row.cost : stored(draft.cost),
        cash_amount: draft.cash_amount === undefined ? Number(row.cash_amount || 0) : stored(draft.cash_amount),
        value: draft.value === undefined ? row.value : stored(draft.value),
        currency: 'TWD',
      })
      setDrafts((current) => {
        const next = { ...current }
        delete next[row.id]
        return next
      })
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
        <div className="flex gap-2">
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm" value={currency} onChange={(event) => setCurrency(event.target.value)}>
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
          <button type="button" onClick={addInvestment} className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-sm text-sky-100">
            新增標的
          </button>
        </div>
      </div>
      {error ? <div className="border-b border-rose-900/60 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</div> : null}
      <div className="divide-y divide-line">
        {investments.map((row) => {
          const cost = Number(draftValue(row, 'cost') || 0)
          const cash = Number(draftValue(row, 'cash_amount') || 0)
          const value = Number(draftValue(row, 'value') || 0)
          const currentTotal = cash + value
          const cashRatio = currentTotal > 0 ? cash / currentTotal : null
          const pnl = currentTotal - cost
          const roi = cost > 0 ? pnl / cost : null
          return (
            <div key={row.id} className="grid gap-3 px-3 py-3 sm:px-4 lg:grid-cols-[1.1fr_0.75fr_0.82fr_0.82fr_0.82fr_1fr_auto] lg:items-center">
              <div className="grid grid-cols-[1fr_auto] gap-2 lg:block">
                <input
                  className="min-w-0 rounded-md border border-line bg-[#0b1020] px-3 py-2 outline-none focus:border-sky-500"
                  value={drafts[row.id]?.name ?? row.name}
                  onChange={(event) => update(row, { name: event.target.value })}
                  onBlur={() => save(row)}
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
                value={drafts[row.id]?.asset_type ?? row.asset_type}
                onChange={(event) => {
                  const asset_type = event.target.value
                  update(row, { asset_type })
                  save(row, { asset_type })
                }}
              >
                <option value="台股">台股</option>
                <option value="美股">美股</option>
                <option value="其他">其他</option>
              </select>
              <label className="grid gap-1 text-xs text-slate-400 lg:block">
                <span>投入金額</span>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={drafts[row.id]?.cost ?? display(row.cost)}
                  onChange={(event) => update(row, { cost: event.target.value })}
                  onBlur={() => save(row)}
                />
              </label>
              <label className="grid gap-1 text-xs text-slate-400 lg:block">
                <span>現金量</span>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={drafts[row.id]?.cash_amount ?? display(row.cash_amount || 0)}
                  onChange={(event) => update(row, { cash_amount: event.target.value })}
                  onBlur={() => save(row)}
                />
              </label>
              <label className="grid gap-1 text-xs text-slate-400 lg:block">
                <span>市值</span>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={drafts[row.id]?.value ?? display(row.value)}
                  onChange={(event) => update(row, { value: event.target.value })}
                  onBlur={() => save(row)}
                />
              </label>
              <div className={`rounded-md bg-panel/60 px-3 py-2 text-right text-sm lg:bg-transparent lg:px-0 ${pnlClass(pnl)}`}>
                <div className="text-xs text-slate-400">現金 {percent(cashRatio)}</div>
                <div>{hideAmounts ? percent(roi) : `${money(pnl, currency)} / ${percent(roi)}`}</div>
                {saving === row.id ? <span className="ml-2 text-slate-400">儲存中</span> : null}
              </div>
              <button
                type="button"
                onClick={() => removeInvestment(row)}
                className="hidden rounded-md p-2 text-slate-400 hover:bg-panel hover:text-rose-300 lg:block"
                title="刪除"
              >
                <Trash2 size={17} />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
