import { Fragment, useEffect, useMemo, useRef, useState } from 'react'

import HoldingTradeDetails from './holdings/HoldingTradeDetails'
import MobileCardList from './holdings/MobileCardList'
import { ALL_COLUMNS, COMPACT_COLUMNS, MOBILE_SORT_KEYS } from './holdings/columns'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useBuyLotsQuery } from '../hooks/queries'
import { money, number, percent, pnlClass } from '../utils/format'

export default function HoldingsTable({ holdings, account, currency = 'TWD' }) {
  const { hideAmounts } = usePrivacy()
  const [sort, setSort] = useState({ key: 'market_value', direction: 'desc' })
  const [expanded, setExpanded] = useState(false)
  const [compact, setCompact] = useState(false)
  const [activeTicker, setActiveTicker] = useState('')
  const detailRef = useRef(null)

  // 買入明細的 FIFO 由後端計算（含股票分割調整），前端只負責顯示
  const lotsQuery = useBuyLotsQuery(account, activeTicker)
  const detailTrades = lotsQuery.data?.trades || []
  const detailLoading = lotsQuery.isLoading
  const detailError = lotsQuery.error ? lotsQuery.error.message || '讀取明細失敗' : ''
  const visibleColumns = compact ? ALL_COLUMNS.filter((column) => COMPACT_COLUMNS.includes(column.key)) : ALL_COLUMNS

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

  useEffect(() => {
    if (!activeTicker) return

    function closeOnOutside(event) {
      if (detailRef.current && !detailRef.current.contains(event.target)) {
        setActiveTicker('')
      }
    }

    document.addEventListener('mousedown', closeOnOutside)
    return () => document.removeEventListener('mousedown', closeOnOutside)
  }, [activeTicker])

  function toggleDetail(ticker) {
    setActiveTicker((current) => (current === ticker ? '' : ticker))
  }

  function renderDetail(row, className = '') {
    if (activeTicker !== row.ticker) return null
    return (
      <HoldingTradeDetails
        row={row}
        trades={detailTrades}
        loading={detailLoading}
        error={detailError}
        currency={currency}
        hideAmounts={hideAmounts}
        onClose={() => setActiveTicker('')}
        detailRef={detailRef}
        className={className}
      />
    )
  }

  if (!holdings.length) {
    return <div className="rounded-md border border-line bg-surface p-5 text-slate-400">目前沒有持倉</div>
  }

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="hidden items-center justify-between border-b border-line bg-panel px-4 py-2 sm:flex">
        <div className="text-sm font-medium text-slate-200">持倉列表</div>
        <button
          type="button"
          onClick={() => setCompact((value) => !value)}
          className="rounded-md border border-line px-3 py-1.5 text-xs text-slate-300 hover:border-sky-500 hover:text-white"
        >
          {compact ? '完整顯示' : '精簡顯示'}
        </button>
      </div>
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
        <MobileCardList
          holdings={sortedHoldings}
          account={account}
          currency={currency}
          hideAmounts={hideAmounts}
          activeTicker={activeTicker}
          onToggle={toggleDetail}
          renderDetail={renderDetail}
        />
      </div>

      <div className={expanded ? 'max-h-[calc(100vh-220px)] overflow-auto' : 'hidden max-h-[calc(100vh-220px)] overflow-auto sm:block'}>
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-panel text-slate-300">
            <tr>
              {visibleColumns.map((column) => (
                <th key={column.key} className={`sticky top-0 z-20 bg-panel px-4 py-3 ${column.align === 'left' ? '' : 'text-right'}`}>
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
              <Fragment key={row.ticker}>
                <tr key={row.ticker} className={`border-b border-line/70 transition-colors last:border-0 hover:bg-sky-500/5 ${activeTicker === row.ticker ? 'bg-sky-500/5' : ''}`}>
                  <td className="px-4 py-3">
                    <button type="button" onClick={() => toggleDetail(row.ticker)} className="group min-h-0 rounded-md px-1 py-0.5 text-left transition hover:-translate-y-0.5 hover:bg-sky-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.98]">
                      <div className="font-medium text-white underline-offset-4 group-hover:text-sky-100 group-hover:underline">{row.ticker}</div>
                      {row.company_name ? <div className="text-xs text-slate-400">{row.company_name}</div> : null}
                    </button>
                  </td>
                  {visibleColumns.some((column) => column.key === 'qty') ? <td className="px-4 py-3 text-right">{number(row.qty, 4)}</td> : null}
                  {visibleColumns.some((column) => column.key === 'avg_price') ? <td className="px-4 py-3 text-right">{hideAmounts ? '••••' : number(row.avg_price, 2)}</td> : null}
                  {visibleColumns.some((column) => column.key === 'current_price') ? <td className="px-4 py-3 text-right">{hideAmounts ? '••••' : number(row.current_price, 2)}</td> : null}
                  {visibleColumns.some((column) => column.key === 'market_value') ? <td className="px-4 py-3 text-right">{hideAmounts ? maskAmount(money(row.market_value, currency)) : money(row.market_value, currency)}</td> : null}
                  {visibleColumns.some((column) => column.key === 'pnl') ? (
                    <td className={`px-4 py-3 text-right ${pnlClass(row.pnl)}`}>
                      {hideAmounts ? maskAmount(money(row.pnl, currency)) : money(row.pnl, currency)}
                    </td>
                  ) : null}
                  {visibleColumns.some((column) => column.key === 'pnl_pct') ? <td className={`px-4 py-3 text-right ${pnlClass(row.pnl)}`}>{percent(row.pnl_pct)}</td> : null}
                  {visibleColumns.some((column) => column.key === 'weight') ? <td className="px-4 py-3 text-right">{percent(row.weight)}</td> : null}
                </tr>
                {activeTicker === row.ticker ? (
                  <tr key={`${row.ticker}-detail`} className="border-b border-line/70">
                    <td colSpan={visibleColumns.length} className="bg-[#0b1020]/45 px-4 py-3">
                      {renderDetail(row)}
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
