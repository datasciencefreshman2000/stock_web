import { useState } from 'react'
import { Trash2 } from 'lucide-react'

import { api } from '../api/client'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import { ACCOUNTS } from '../constants'
import { usePrivacy } from '../context/PrivacyContext'
import { useSummary } from '../hooks/useSummary'
import { useTrades } from '../hooks/useTrades'
import { number, percent } from '../utils/format'

const COMBINED_HISTORY_ACCOUNT = '__combined__'
const MASKED_VALUE = '••••'
const HISTORY_ACCOUNT_OPTIONS = [
  ...ACCOUNTS.map((item) => ({ value: item, label: item })),
  {
    value: COMBINED_HISTORY_ACCOUNT,
    label: `${ACCOUNTS[0]} + ${ACCOUNTS[1]} + ${ACCOUNTS[2]}`,
  },
]

function dateValue(date) {
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 10)
}

function rangeFilters(type) {
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

function tradeQty(trade) {
  return Number(trade.buy_qty || 0) > 0 ? Number(trade.buy_qty || 0) : Number(trade.sell_qty || 0)
}

function tradeAmount(trade) {
  const total = Number(trade.total)
  if (!Number.isNaN(total) && total !== 0) return Math.abs(total)
  return Math.abs(Number(trade.price || 0) * tradeQty(trade))
}

function tradeAccountRatio(trade, accountSummaries, fallbackAccount) {
  const account = trade.account || fallbackAccount
  const accountTotal = Number(accountSummaries?.[account]?.account_total || 0)
  const amount = tradeAmount(trade)
  return accountTotal > 0 && amount > 0 ? amount / accountTotal : null
}

function TradeSideBadge({ isBuy }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
        isBuy
          ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-100'
          : 'border-rose-400/40 bg-rose-500/15 text-rose-100'
      }`}
    >
      {isBuy ? '買入' : '賣出'}
    </span>
  )
}

export default function History() {
  const { hideAmounts } = usePrivacy()
  const [account, setAccount] = useState(ACCOUNTS[0])
  const [filters, setFilters] = useState(() => ({ ticker: '', ...rangeFilters('7d') }))
  const { data, error, loading, reload } = useTrades(account, filters)
  const summary = useSummary()
  const accountSummaries = summary.data?.accounts || {}
  const trades = data?.trades || []

  async function remove(id) {
    if (!window.confirm('確定刪除這筆交易？')) return
    await api.deleteTrade(id)
    reload()
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
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2" value={account} onChange={(e) => setAccount(e.target.value)}>
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

      {!loading && !error ? (
        <div className="overflow-hidden rounded-md border border-line bg-surface">
          <div className="divide-y divide-line sm:hidden">
            {trades.map((trade) => {
              const isBuy = Number(trade.buy_qty || 0) > 0
              const qty = tradeQty(trade)
              const ratio = tradeAccountRatio(trade, accountSummaries, account)
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
                    <button className="rounded-md p-2 text-slate-400 hover:bg-panel hover:text-rose-300" onClick={() => remove(trade.id)}>
                      <Trash2 size={17} />
                    </button>
                  </div>
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
                </div>
              )
            })}
          </div>
          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full min-w-[940px] text-left text-sm">
              <thead className="border-b border-line bg-panel text-slate-300">
                <tr>
                  <th className="px-4 py-3">日期</th>
                  <th className="px-4 py-3">帳戶</th>
                  <th className="px-4 py-3">代號</th>
                  <th className="px-4 py-3">買賣</th>
                  <th className="px-4 py-3 text-right">股數</th>
                  <th className="px-4 py-3 text-right">價格</th>
                  <th className="px-4 py-3 text-right">佔帳戶</th>
                  <th className="px-4 py-3">備註</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => {
                  const isBuy = Number(trade.buy_qty || 0) > 0
                  const qty = tradeQty(trade)
                  const ratio = tradeAccountRatio(trade, accountSummaries, account)
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
                        <button className="rounded-md p-2 text-slate-400 hover:bg-panel hover:text-rose-300" onClick={() => remove(trade.id)}>
                          <Trash2 size={18} />
                        </button>
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
