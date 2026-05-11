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

const COMPACT_KEYS = new Set(['ticker', 'current_price', 'pnl_pct', 'market_value'])

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
      <div className="flex items-center justify-between border-b border-line bg-panel px-4 py-2 sm:hidden">
        <span className="text-xs text-slate-400">持倉明細</span>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="rounded border border-line px-2 py-1 text-xs text-slate-300 hover:border-sky-500 hover:text-white"
        >
          {expanded ? '收合' : '展開全部'}
        </button>
      </div>

      {/* 手機版：卡片式（預設），或展開後的橫向滑動表格 */}
      <div className={expanded ? 'hidden' : 'sm:hidden'}>
        <MobileCardList holdings={sortedHoldings} currency={currency} hideAmounts={hideAmounts} />
      </div>

      {/* 桌機版 + 手機展開版 */}
      <div className={expanded ? 'overflow-x-auto' : 'hidden overflow-x-auto sm:block'}>
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-panel text-slate-300">
            <tr>
              {ALL_COLUMNS.map((column) => (
                <th key={column.key} className={`px-4 py-3 ${column.align === 'left' ? '' : 'text-right'}`}>
                  <button
                    type="button"
                    onClick={() => toggleSort(column.key)}
                    className={`inline-flex items-center gap-1 ${column.align === 'left' ? '' : 'justify-end'} w-full hover:text-white`}
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
        <div key={row.ticker} className="px-4 py-3">
          <div className="mb-2 flex items-start justify-between">
            <div>
              <span className="font-medium text-white">{row.ticker}</span>
              {row.company_name ? <span className="ml-2 text-xs text-slate-400">{row.company_name}</span> : null}
            </div>
            <div className={`text-sm font-medium ${pnlClass(row.pnl)}`}>{percent(row.pnl_pct)}</div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-slate-400">現價</div>
              <div className="text-slate-100">{hideAmounts ? '••••' : number(row.current_price, 2)}</div>
            </div>
            <div>
              <div className="text-slate-400">市值</div>
              <div className="text-slate-100">{hideAmounts ? maskAmount(money(row.market_value, currency)) : money(row.market_value, currency)}</div>
            </div>
            <div>
              <div className="text-slate-400">損益</div>
              <div className={pnlClass(row.pnl)}>{hideAmounts ? maskAmount(money(row.pnl, currency)) : money(row.pnl, currency)}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
