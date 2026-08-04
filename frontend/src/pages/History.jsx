import { useMemo, useState } from 'react'
import { Edit3, Trash2 } from 'lucide-react'

import TradeEditForm from '../components/history/TradeEditForm'
import TradeSideBadge from '../components/history/TradeSideBadge'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import { ACCOUNTS } from '../constants'
import { usePrivacy } from '../context/PrivacyContext'
import { useSummaryQuery, useTradeMutations, useTradesQuery } from '../hooks/queries'
import {
  HISTORY_ACCOUNT_OPTIONS,
  MASKED_VALUE,
  compareTradesNewestFirst,
  rangeFilters,
  tradeAccountRatio,
  tradeFormFromTrade,
  tradePayloadFromForm,
  tradeQty,
} from '../utils/trades'
import { number, percent } from '../utils/format'

export default function History() {
  const { hideAmounts } = usePrivacy()
  const [account, setAccount] = useState(ACCOUNTS[0])
  const [filters, setFilters] = useState(() => ({ ticker: '', ...rangeFilters('7d') }))
  const [editingId, setEditingId] = useState('')
  const [editForm, setEditForm] = useState(null)
  const [savingId, setSavingId] = useState('')
  const [actionError, setActionError] = useState('')
  const { data, error, isLoading: loading } = useTradesQuery(account, filters)
  const summaryQuery = useSummaryQuery()
  const { update: updateTrade, remove: removeTrade } = useTradeMutations()
  const accountSummaries = summaryQuery.data?.accounts || {}
  const trades = useMemo(() => [...(data?.trades || [])].sort(compareTradesNewestFirst), [data?.trades])

  async function remove(id) {
    if (!window.confirm('確定刪除這筆交易？')) return
    setActionError('')
    try {
      await removeTrade.mutateAsync(id)
      if (editingId === id) {
        setEditingId('')
        setEditForm(null)
      }
    } catch (err) {
      setActionError(err.message || '刪除失敗')
    }
  }

  function startEdit(trade) {
    setActionError('')
    setEditingId(trade.id)
    setEditForm(tradeFormFromTrade(trade, account))
  }

  function cancelEdit() {
    setEditingId('')
    setEditForm(null)
  }

  function updateEdit(key, value) {
    setEditForm((current) => ({ ...current, [key]: value }))
  }

  async function saveEdit(event) {
    event.preventDefault()
    if (!editingId || !editForm) return
    const qty = Number(editForm.qty)
    const price = Number(editForm.price)
    if (!editForm.account || !editForm.ticker.trim() || !editForm.date || qty <= 0 || price <= 0) {
      setActionError('請確認帳戶、代號、日期、股數與價格都有填寫。')
      return
    }

    setSavingId(editingId)
    setActionError('')
    try {
      await updateTrade.mutateAsync({ id: editingId, data: tradePayloadFromForm(editForm) })
      setEditingId('')
      setEditForm(null)
    } catch (err) {
      setActionError(err.message || '儲存失敗')
    } finally {
      setSavingId('')
    }
  }

  function setRange(type) {
    setFilters((current) => ({ ...current, ...rangeFilters(type) }))
  }

  return (
    <div className="grid gap-5">
      <header>
        <h1 className="text-2xl font-semibold">交易紀錄</h1>
      </header>

      <section className="grid gap-3 rounded-md border border-line bg-surface p-4 sm:grid-cols-4">
        <label className="grid gap-2 text-sm">
          帳戶
          <select
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
            value={account}
            onChange={(e) => {
              cancelEdit()
              setAccount(e.target.value)
            }}
          >
            {HISTORY_ACCOUNT_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-2 text-sm">
          代號
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" value={filters.ticker} onChange={(e) => setFilters((current) => ({ ...current, ticker: e.target.value.toUpperCase() }))} />
        </label>
        <label className="grid gap-2 text-sm">
          起日
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" type="date" value={filters.start_date} onChange={(e) => setFilters((current) => ({ ...current, start_date: e.target.value }))} />
        </label>
        <label className="grid gap-2 text-sm">
          迄日
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" type="date" value={filters.end_date} onChange={(e) => setFilters((current) => ({ ...current, end_date: e.target.value }))} />
        </label>
        <div className="flex flex-wrap gap-2 sm:col-span-4">
          {[
            ['1d', '1日'],
            ['7d', '7日'],
            ['1m', '一個月'],
            ['3m', '三個月'],
            ['1y', '一年'],
            ['ytd', '年內交易'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setRange(key)}
              className="rounded-md border border-line bg-panel px-3 py-1.5 text-xs text-slate-300 hover:border-sky-500 hover:text-white"
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {loading ? <LoadingBlock label="正在讀取交易紀錄" /> : null}
      {error ? <ErrorBlock error={error} /> : null}
      {actionError ? <div className="rounded-md border border-rose-900/60 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{actionError}</div> : null}

      {!loading && !error ? (
        <div className="overflow-hidden rounded-md border border-line bg-surface">
          <div className="divide-y divide-line sm:hidden">
            {trades.map((trade) => {
              const isBuy = Number(trade.buy_qty || 0) > 0
              const qty = tradeQty(trade)
              const ratio = tradeAccountRatio(trade, accountSummaries, account)
              const isEditing = editingId === trade.id
              return (
                <div key={trade.id} className="px-3 py-3">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-white">{trade.ticker}</div>
                      {trade.company_name ? <div className="text-xs text-slate-400">{trade.company_name}</div> : null}
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span>{trade.date || '--'}</span>
                        {trade.account ? <span>{trade.account}</span> : null}
                        <TradeSideBadge isBuy={isBuy} />
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-xs text-slate-300 hover:border-sky-500 hover:bg-panel hover:text-sky-200"
                        onClick={() => startEdit(trade)}
                        disabled={Boolean(savingId)}
                        title="修改"
                      >
                        <Edit3 size={14} />
                        修改
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-line p-1.5 text-slate-400 hover:border-rose-500 hover:bg-panel hover:text-rose-300"
                        onClick={() => remove(trade.id)}
                        disabled={Boolean(savingId)}
                        title="刪除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  {isEditing && editForm ? (
                    <TradeEditForm
                      form={editForm}
                      onChange={updateEdit}
                      onSubmit={saveEdit}
                      onCancel={cancelEdit}
                      saving={savingId === trade.id}
                      hideAmounts={hideAmounts}
                    />
                  ) : (
                    <>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <div className="text-slate-400">數量</div>
                          <div className="text-slate-100">{hideAmounts ? MASKED_VALUE : number(qty, 4)}</div>
                        </div>
                        <div>
                          <div className="text-slate-400">價格</div>
                          <div className="text-slate-100">{hideAmounts ? MASKED_VALUE : number(trade.price, 2)}</div>
                        </div>
                        <div>
                          <div className="text-slate-400">佔帳戶</div>
                          <div className="text-slate-100">{percent(ratio)}</div>
                        </div>
                      </div>
                      {trade.note ? <div className="mt-2 text-xs text-slate-500">{trade.note}</div> : null}
                    </>
                  )}
                </div>
              )
            })}
          </div>
          <div className="hidden max-h-[calc(100vh-220px)] overflow-auto sm:block">
            <table className="w-full min-w-[940px] text-left text-sm">
              <thead className="border-b border-line bg-panel text-slate-300">
                <tr>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3">日期</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3">帳戶</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3">代號</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3">買賣</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3 text-right">股數</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3 text-right">價格</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3 text-right">佔帳戶</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3">備註</th>
                  <th className="sticky top-0 z-20 bg-panel px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => {
                  const isBuy = Number(trade.buy_qty || 0) > 0
                  const qty = tradeQty(trade)
                  const ratio = tradeAccountRatio(trade, accountSummaries, account)
                  const isEditing = editingId === trade.id
                  if (isEditing && editForm) {
                    return (
                      <tr key={trade.id} className="border-b border-line/70 last:border-0">
                        <td colSpan={9} className="px-4 py-3">
                          <TradeEditForm
                            form={editForm}
                            onChange={updateEdit}
                            onSubmit={saveEdit}
                            onCancel={cancelEdit}
                            saving={savingId === trade.id}
                            hideAmounts={hideAmounts}
                          />
                        </td>
                      </tr>
                    )
                  }
                  return (
                    <tr key={trade.id} className="border-b border-line/70 last:border-0">
                      <td className="px-4 py-3">{trade.date || '--'}</td>
                      <td className="px-4 py-3 text-slate-300">{trade.account || '--'}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">{trade.ticker}</div>
                        {trade.company_name ? <div className="text-xs text-slate-400">{trade.company_name}</div> : null}
                      </td>
                      <td className="px-4 py-3">
                        <TradeSideBadge isBuy={isBuy} />
                      </td>
                      <td className="px-4 py-3 text-right">{hideAmounts ? MASKED_VALUE : number(qty, 4)}</td>
                      <td className="px-4 py-3 text-right">{hideAmounts ? MASKED_VALUE : number(trade.price, 2)}</td>
                      <td className="px-4 py-3 text-right">{percent(ratio)}</td>
                      <td className="px-4 py-3 text-slate-400">{trade.note}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-xs text-slate-300 hover:border-sky-500 hover:bg-panel hover:text-sky-200"
                            onClick={() => startEdit(trade)}
                            disabled={Boolean(savingId)}
                            title="修改"
                          >
                            <Edit3 size={14} />
                            修改
                          </button>
                          <button
                            type="button"
                            className="rounded-md border border-line p-1.5 text-slate-400 hover:border-rose-500 hover:bg-panel hover:text-rose-300"
                            onClick={() => remove(trade.id)}
                            disabled={Boolean(savingId)}
                            title="刪除"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  )
}
