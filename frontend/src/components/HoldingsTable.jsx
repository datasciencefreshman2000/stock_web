import { useMemo, useState } from 'react'

import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money, number, percent, pnlClass } from '../utils/format'

export default function HoldingsTable({ holdings, currency = 'TWD' }) {
  const { hideAmounts } = usePrivacy()
  const [sort, setSort] = useState({ key: 'market_value', direction: 'desc' })
  const columns = [
    { key: 'ticker', label: '代號', align: 'left' },
    { key: 'qty', label: '股數' },
    { key: 'avg_price', label: '均價' },
    { key: 'current_price', label: '現價' },
    { key: 'market_value', label: '市值' },
    { key: 'pnl', label: '損益' },
    { key: 'pnl_pct', label: '損益%' },
    { key: 'weight', label: '佔比' },
  ]

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
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-panel text-slate-300">
            <tr>
              {columns.map((column) => (
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
                <td className="px-4 py-3 font-medium text-white">{row.ticker}</td>
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
