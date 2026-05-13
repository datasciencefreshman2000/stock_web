import { useMemo, useState } from 'react'

import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money, number, percent, pnlClass } from '../utils/format'

const ALL_COLUMNS = [
  { key: 'ticker', label: '代號', align: 'left' },
  { key: 'qty', label: '股數' },
  { key: 'avg_price', label: '均價' },
  { key: 'current_price', label: '現價' },
  { key: 'market_value', label: '市值' },
  { key: 'pnl', label: '損益' },
  { key: 'pnl_pct', label: '損益%' },
  { key: 'weight', label: '佔比' },
]

const MOBILE_SORT_KEYS = ['market_value', 'pnl_pct', 'ticker']

export default function HoldingsTable({ holdings, currency = 'TWD' }) {
  const { hideAmounts } = usePrivacy()
  const [sort, setSort] = useState({ key: 'market_value', direction: 'desc' })
  const [expanded, setExpanded] = useState(false)

  const sortedHoldings = useMemo(() => {
    return [...holdings].sort((a, b) => {
      const av = a[sort.key]
      const bv = b[sort.key]
      if (sort.key === 'ticker') {
        return sort.direction === 'asc'
          ? String(av).localeCompare(String(bv))
          : String(bv).localeCompare(String(av))
      }
      const diff = Number(av ?? -Infinity) - Number(bv ?? -Infinity)
      return sort.direction === 'asc' ? diff : -diff
    })
  }, [holdings, sort])

  function toggleSort(key) {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }))
  }

  if (!holdings.length) {
    return <div className="rounded-md border border-line bg-surface p-5 text-slate-400">目前沒有持倉</div>
  }

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-3 py-2 sm:hidden">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs text-slate-400">持倉排序</span>
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="rounded border border-line px-2 py-1 text-xs text-slate-300 hover:border-sky-500 hover:text-white"
          >
            {expanded ? '卡片' : '表格'}
          </button>
        </div>
        <div className="scrollbar-hide flex gap-2 overflow-x-auto">
          {ALL_COLUMNS.filter((column) => MOBILE_SORT_KEYS.includes(column.key)).map((column) => (
            <button
              key={column.key}
              type="button"
              onClick={() => toggleSort(column.key)}
              className={`shrink-0 rounded-md border px-2.5 py-1.5 text-xs ${
                sort.key === column.key ? 'border-sky-400 bg-sky-500/15 text-white' : 'border-line bg-surface text-slate-300'
              }`}
            >
              {column.label}
              {sort.key === column.key ? (sort.direction === 'desc' ? ' ↓' : ' ↑') : ''}
            </button>
          ))}
        </div>
      </div>

      <div className={expanded ? 'hidden' : 'sm:hidden'}>
        <MobileCardList holdings={sortedHoldings} currency={currency} hideAmounts={hideAmounts} />
      </div>

      <div className={expanded ? 'overflow-x-auto' : 'hidden overflow-x-auto sm:block'}>
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-panel text-slate-300">
            <tr>
              {ALL_COLUMNS.map((column) => (
                <th key={column.key} className={`px-4 py-3 ${column.align === 'left' ? '' : 'text-right'}`}>
                  <button
                    type="button"
                    onClick={() => toggleSort(column.key)}
                    className={`inline-flex w-full items-center gap-1 ${column.align === 'left' ? '' : 'justify-end'} hover:text-white`}
                  >
                    <span>{column.label}</span>
                    <span className="text-xs text-slate-500">
                      {sort.key === column.key ? (sort.direction === 'desc' ? '↓' : '↑') : ''}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedHoldings.map((row) => (
              <tr key={row.ticker} className="border-b border-line/70 last:border-0">
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{row.ticker}</div>
                  {row.company_name ? <div className="text-xs text-slate-400">{row.company_name}</div> : null}
                </td>
                <td className="px-4 py-3 text-right">{number(row.qty, 4)}</td>
                <td className="px-4 py-3 text-right">{hideAmounts ? '••••' : number(row.avg_price, 2)}</td>
                <td className="px-4 py-3 text-right">{hideAmounts ? '••••' : number(row.current_price, 2)}</td>
                <td className="px-4 py-3 text-right">{hideAmounts ? maskAmount(money(row.market_value, currency)) : money(row.market_value, currency)}</td>
                <td className={`px-4 py-3 text-right ${pnlClass(row.pnl)}`}>
                  {hideAmounts ? maskAmount(money(row.pnl, currency)) : money(row.pnl, currency)}
                </td>
                <td className={`px-4 py-3 text-right ${pnlClass(row.pnl)}`}>{percent(row.pnl_pct)}</td>
                <td className="px-4 py-3 text-right">{percent(row.weight)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MobileCardList({ holdings, currency, hideAmounts }) {
  return (
    <div className="divide-y divide-line">
      {holdings.map((row) => (
        <div key={row.ticker} className="px-3 py-2.5">
          <div className="mb-1.5 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-medium text-white">{row.ticker}</div>
              {row.company_name ? <div className="truncate text-[11px] text-slate-400">{row.company_name}</div> : null}
            </div>
            <div className="shrink-0 text-right text-xs text-slate-400">
              <div>佔比</div>
              <div className="font-medium text-white">{percent(row.weight)}</div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Metric label="現價" value={hideAmounts ? '••••' : number(row.current_price, 2)} />
            <Metric label="損益%" value={percent(row.pnl_pct)} accent={pnlClass(row.pnl)} />
          </div>
          {!hideAmounts ? (
            <div className="mt-1 truncate text-[11px] text-slate-500">{money(row.market_value, currency)}</div>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function Metric({ label, value, accent = 'text-slate-100' }) {
  return (
    <div className="min-w-0">
      <div className="text-slate-400">{label}</div>
      <div className={`truncate tabular-nums ${accent}`}>{value}</div>
    </div>
  )
}
