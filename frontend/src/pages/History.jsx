import { useState } from 'react'
import { Trash2 } from 'lucide-react'

import { api } from '../api/client'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import { ACCOUNTS } from '../constants'
import { usePrivacy } from '../context/PrivacyContext'
import { useTrades } from '../hooks/useTrades'
import { number } from '../utils/format'

function dateValue(date) {
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 10)
}

export default function History() {
  const { hideAmounts } = usePrivacy()
  const [account, setAccount] = useState('台股')
  const [filters, setFilters] = useState({ ticker: '', start_date: '', end_date: '' })
  const { data, error, loading, reload } = useTrades(account, filters)

  async function remove(id) {
    if (!window.confirm('確定刪除這筆交易？')) return
    await api.deleteTrade(id)
    reload()
  }

  function setRange(type) {
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
    setFilters((current) => ({ ...current, start_date: dateValue(start), end_date: dateValue(end) }))
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
            {ACCOUNTS.map((item) => (
              <option key={item}>{item}</option>
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
            {(data?.trades || []).map((trade) => {
              const isBuy = Number(trade.buy_qty || 0) > 0
              const qty = isBuy ? trade.buy_qty : trade.sell_qty
              return (
                <div key={trade.id} className="px-3 py-3">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-white">{trade.ticker}</div>
                      {trade.company_name ? <div className="text-xs text-slate-400">{trade.company_name}</div> : null}
                      <div className="text-xs text-slate-400">{trade.date || '--'} · {isBuy ? '買入' : '賣出'}</div>
                    </div>
                    <button className="rounded-md p-2 text-slate-400 hover:bg-panel hover:text-rose-300" onClick={() => remove(trade.id)}>
                      <Trash2 size={17} />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div className="text-slate-400">數量</div>
                      <div className="text-slate-100">{number(qty, 4)}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">價格</div>
                      <div className="text-slate-100">{hideAmounts ? '••••' : number(trade.price, 2)}</div>
                    </div>
                  </div>
                  {trade.note ? <div className="mt-2 text-xs text-slate-500">{trade.note}</div> : null}
                </div>
              )
            })}
          </div>
          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full min-w-[780px] text-left text-sm">
              <thead className="border-b border-line bg-panel text-slate-300">
                <tr>
                  <th className="px-4 py-3">日期</th>
                  <th className="px-4 py-3">代號</th>
                  <th className="px-4 py-3">買賣</th>
                  <th className="px-4 py-3 text-right">股數</th>
                  <th className="px-4 py-3 text-right">價格</th>
                  <th className="px-4 py-3">備註</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {(data?.trades || []).map((trade) => {
                  const isBuy = Number(trade.buy_qty || 0) > 0
                  const qty = isBuy ? trade.buy_qty : trade.sell_qty
                  return (
                    <tr key={trade.id} className="border-b border-line/70 last:border-0">
                      <td className="px-4 py-3">{trade.date || '--'}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">{trade.ticker}</div>
                        {trade.company_name ? <div className="text-xs text-slate-400">{trade.company_name}</div> : null}
                      </td>
                      <td className="px-4 py-3">{isBuy ? '買入' : '賣出'}</td>
                      <td className="px-4 py-3 text-right">{number(qty, 4)}</td>
                      <td className="px-4 py-3 text-right">{hideAmounts ? '••••' : number(trade.price, 2)}</td>
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
