import { X } from 'lucide-react'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
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
const COMPACT_COLUMNS = ['ticker', 'market_value', 'pnl', 'pnl_pct', 'weight']

export default function HoldingsTable({ holdings, account, currency = 'TWD' }) {
  const { hideAmounts } = usePrivacy()
  const [sort, setSort] = useState({ key: 'market_value', direction: 'desc' })
  const [expanded, setExpanded] = useState(false)
  const [compact, setCompact] = useState(false)
  const [activeTicker, setActiveTicker] = useState('')
  const [detailTrades, setDetailTrades] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const detailRef = useRef(null)
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
    if (!activeTicker || !account) {
      setDetailTrades([])
      return
    }
    let active = true
    setDetailLoading(true)
    setDetailError('')
    api
      .getTrades(account, { ticker: activeTicker })
      .then((data) => {
        if (!active) return
        setDetailTrades((data.trades || []).filter((trade) => Number(trade.buy_qty || 0) > 0))
      })
      .catch((err) => {
        if (active) setDetailError(err.message || '讀取明細失敗')
      })
      .finally(() => {
        if (active) setDetailLoading(false)
      })

    return () => {
      active = false
    }
  }, [account, activeTicker])

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
          currency={currency}
          hideAmounts={hideAmounts}
          activeTicker={activeTicker}
          onToggle={toggleDetail}
          renderDetail={renderDetail}
        />
      </div>

      <div className={expanded ? 'overflow-x-auto' : 'hidden overflow-x-auto sm:block'}>
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-panel text-slate-300">
            <tr>
              {visibleColumns.map((column) => (
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
              <Fragment key={row.ticker}>
                <tr key={row.ticker} className={`border-b border-line/70 last:border-0 ${activeTicker === row.ticker ? 'bg-sky-500/5' : ''}`}>
                  <td className="px-4 py-3">
                    <button type="button" onClick={() => toggleDetail(row.ticker)} className="min-h-0 text-left">
                      <div className="font-medium text-white underline-offset-4 hover:underline">{row.ticker}</div>
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

function MobileCardList({ holdings, currency, hideAmounts, activeTicker, onToggle, renderDetail }) {
  return (
    <div className="divide-y divide-line">
      {holdings.map((row) => (
        <div key={row.ticker} className={`px-3 py-2 ${activeTicker === row.ticker ? 'bg-sky-500/5' : ''}`}>
          <button type="button" onClick={() => onToggle(row.ticker)} className="mb-1 flex min-h-0 w-full items-start justify-between gap-3 text-left">
            <div className="min-w-0">
              <div className="text-sm font-medium text-white underline-offset-4">{row.ticker}</div>
              {row.company_name ? <div className="truncate text-[11px] text-slate-400">{row.company_name}</div> : null}
            </div>
            <div className="shrink-0 text-right text-[11px] text-slate-400">
              <div className="leading-tight">佔比</div>
              <div className="text-sm font-semibold leading-tight text-white">{percent(row.weight)}</div>
            </div>
          </button>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Metric label="市值" value={hideAmounts ? '••••' : money(row.market_value, currency)} />
            <Metric label="損益%" value={percent(row.pnl_pct)} accent={pnlClass(row.pnl)} />
          </div>
          {activeTicker === row.ticker ? renderDetail(row, 'mt-3') : null}
        </div>
      ))}
    </div>
  )
}

function HoldingTradeDetails({ row, trades, loading, error, currency, hideAmounts, onClose, detailRef, className = '' }) {
  const currentPrice = Number(row.current_price || 0)

  return (
    <div ref={detailRef} className={`rounded-md border border-line bg-panel/70 p-3 ${className}`}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-white">{row.ticker} 買入紀錄</div>
          <div className="text-xs text-slate-500">以目前現價估算每筆買入損益</div>
        </div>
        <button type="button" onClick={onClose} className="rounded-md border border-line p-1.5 text-slate-400 hover:border-sky-500 hover:text-white" aria-label="收起明細">
          <X size={15} />
        </button>
      </div>
      {loading ? <div className="text-xs text-slate-400">讀取買入紀錄中...</div> : null}
      {error ? <div className="text-xs text-rose-300">{error}</div> : null}
      {!loading && !error && !trades.length ? <div className="text-xs text-slate-500">沒有買入紀錄。</div> : null}
      {!loading && !error && trades.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-xs">
            <thead className="text-slate-400">
              <tr>
                <th className="py-2 text-left">日期</th>
                <th className="py-2 text-right">股數</th>
                <th className="py-2 text-right">買入均價</th>
                <th className="py-2 text-right">損益</th>
                <th className="py-2 text-right">損益%</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => {
                const qty = Number(trade.buy_qty || 0)
                const price = Number(trade.price || 0)
                const pnl = (currentPrice - price) * qty
                const pnlRatio = price > 0 ? (currentPrice - price) / price : null
                return (
                  <tr key={trade.id || `${trade.date}-${trade.price}-${trade.buy_qty}`} className="border-t border-line/70">
                    <td className="py-2 text-slate-300">{trade.date || '--'}</td>
                    <td className="py-2 text-right text-slate-300">{number(qty, 4)}</td>
                    <td className="py-2 text-right text-slate-300">{hideAmounts ? '••••' : number(price, 2)}</td>
                    <td className={`py-2 text-right ${pnlClass(pnl)}`}>{hideAmounts ? maskAmount(money(pnl, currency)) : money(pnl, currency)}</td>
                    <td className={`py-2 text-right ${pnlClass(pnl)}`}>{percent(pnlRatio)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}
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
