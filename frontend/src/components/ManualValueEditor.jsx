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
        value: 0,
        currency: 'TWD',
      })
      onSaved?.()
    } catch (err) {
      setError(err.message || '新增失敗')
    }
  }

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-panel px-4 py-3">
        <div className="text-sm font-medium">基金與其他投資</div>
        <div className="flex gap-2">
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
          <button type="button" onClick={addInvestment} className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-sm text-sky-100">
            增加標的
          </button>
        </div>
      </div>
      {error ? <div className="border-b border-rose-900/60 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</div> : null}
      <div className="divide-y divide-line">
        {investments.map((row) => {
          const cost = Number(draftValue(row, 'cost') || 0)
          const value = Number(draftValue(row, 'value') || 0)
          const pnl = value - cost
          return (
            <div key={row.id} className="grid gap-3 px-4 py-3 lg:grid-cols-[1.1fr_0.8fr_1fr_1fr_1fr] lg:items-center">
              <input
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2 outline-none focus:border-sky-500"
                value={drafts[row.id]?.name ?? row.name}
                onChange={(e) => update(row, { name: e.target.value })}
                onBlur={() => save(row)}
              />
              <select
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
                value={drafts[row.id]?.asset_type ?? row.asset_type}
                onChange={(e) => {
                  const asset_type = e.target.value
                  update(row, { asset_type })
                  save(row, { asset_type })
                }}
              >
                <option value="台股">台股</option>
                <option value="美股">美股</option>
                <option value="其他">其他</option>
              </select>
              <input
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right outline-none focus:border-sky-500"
                type={hideAmounts ? 'password' : 'number'}
                value={drafts[row.id]?.cost ?? display(row.cost)}
                onChange={(e) => update(row, { cost: e.target.value })}
                onBlur={() => save(row)}
              />
              <input
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right outline-none focus:border-sky-500"
                type={hideAmounts ? 'password' : 'number'}
                value={drafts[row.id]?.value ?? display(row.value)}
                onChange={(e) => update(row, { value: e.target.value })}
                onBlur={() => save(row)}
              />
              <div className={`text-right text-sm ${pnlClass(pnl)}`}>
                {hideAmounts ? (cost > 0 ? percent(pnl / cost) : '--') : `${money(pnl, currency)} / ${cost > 0 ? percent(pnl / cost) : '--'}`}
                {saving === row.id ? <span className="ml-2 text-slate-400">儲存中</span> : null}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
