import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/client'
import { useCapitalMovementOptionsQuery } from '../../hooks/queries'
import { queryKeys } from '../../lib/queryClient'
import { INCOME_SOURCES } from './constants'

export default function IncomeSourcePicker({ value, onChange }) {
  const [sources, setSources] = useState(INCOME_SOURCES.map((label) => ({ id: null, label })))
  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState('')
  const [editing, setEditing] = useState(false)
  const queryClient = useQueryClient()
  const optionsQuery = useCapitalMovementOptionsQuery('income_source')

  useEffect(() => {
    const loaded = optionsQuery.data?.options || []
    if (loaded.length > 0) {
      setSources(loaded)
      if (!loaded.some((item) => item.label === value)) onChange(loaded[0].label)
    }
    if (optionsQuery.error) setMessage('收入來源資料表尚未建立')
  }, [optionsQuery.data, optionsQuery.error])

  function updateCachedSources(next) {
    setSources(next)
    queryClient.setQueryData(queryKeys.capitalMovementOptions('income_source'), { options: next })
  }

  async function addSource() {
    const label = draft.trim()
    if (!label) return
    try {
      const response = await api.createCapitalMovementOption({ category: 'income_source', label })
      const option = response.option
      updateCachedSources([...sources.filter((item) => item.label !== label), option].sort((a, b) => a.label.localeCompare(b.label, 'zh-Hant')))
      setDraft('')
      onChange(label)
      setMessage('')
    } catch (err) {
      setMessage(err.message || '新增收入來源失敗')
    }
  }

  async function removeSource(option) {
    if (!option.id) return
    try {
      await api.deleteCapitalMovementOption(option.id)
      const next = sources.filter((item) => item.id !== option.id)
      updateCachedSources(next)
      if (option.label === value) onChange(next[0]?.label || '')
      setMessage('')
    } catch (err) {
      setMessage(err.message || '刪除收入來源失敗')
    }
  }

  return (
    <div className="grid gap-2 sm:col-span-2 lg:col-span-2">
      <div className="grid grid-cols-[1fr_auto] items-end gap-2">
        <label className="grid gap-1 text-xs text-slate-400">
          收入來源
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={value} onChange={(event) => onChange(event.target.value)}>
            {sources.map((item) => <option key={item.id || item.label}>{item.label}</option>)}
          </select>
        </label>
        <button
          type="button"
          onClick={() => setEditing((current) => !current)}
          className="rounded-md border border-line bg-panel px-3 py-2 text-xs font-medium text-slate-200"
        >
          更動
        </button>
      </div>
      {editing ? (
        <div className="grid gap-2 rounded-md border border-line bg-panel/50 p-2">
          <div className="flex gap-2">
            <input
              className="min-w-0 flex-1 rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
              placeholder="新增收入來源"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="button" className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-xs font-medium text-sky-100" onClick={addSource}>
              增加
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {sources.map((item) => (
              <button
                key={item.id || item.label}
                type="button"
                disabled={!item.id}
                onClick={() => removeSource(item)}
                className="rounded-full border border-line bg-[#0b1020] px-2 py-1 text-xs text-slate-300 disabled:opacity-50"
                title={item.id ? '刪除收入來源' : '預設來源需要建立資料表後才能刪除'}
              >
                {item.label} {item.id ? '×' : ''}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {message ? <div className="text-xs text-amber-300">{message}</div> : null}
    </div>
  )
}
