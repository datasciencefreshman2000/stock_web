import { X } from 'lucide-react'

import { maskAmount } from '../../context/PrivacyContext'
import { money, number, percent, pnlClass } from '../../utils/format'

export default function HoldingTradeDetails({ row, trades, loading, error, currency, hideAmounts, onClose, detailRef, className = '' }) {
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
          <table className="w-full min-w-[700px] text-xs">
            <thead className="text-slate-400">
              <tr>
                <th className="py-2 text-left">日期</th>
                <th className="py-2 text-right">買入股數</th>
                <th className="py-2 text-right">已賣</th>
                <th className="py-2 text-right">剩餘</th>
                <th className="py-2 text-right">買入均價</th>
                <th className="py-2 text-right">賣出均價</th>
                <th className="py-2 text-right">損益</th>
                <th className="py-2 text-right">損益%</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => {
                const qty = Number(trade.original_qty ?? trade.buy_qty ?? 0)
                const soldQty = Number(trade.sold_qty || 0)
                const remainingQty = Number(trade.remaining_qty ?? qty)
                const activeQty = remainingQty > 1e-7 ? remainingQty : 0
                const price = Number(trade.price || 0)
                const avgSellPrice = soldQty > 0 ? Number(trade.sell_value || 0) / soldQty : null
                const realizedPnl = soldQty > 0 ? Number(trade.sell_value || 0) - soldQty * price : 0
                const unrealizedPnl = activeQty > 0 ? (currentPrice - price) * activeQty : 0
                const pnl = realizedPnl + unrealizedPnl
                const costBasis = price * (soldQty + activeQty)
                const pnlRatio = costBasis > 0 ? pnl / costBasis : null
                return (
                  <tr key={trade.id || `${trade.date}-${trade.price}-${trade.buy_qty}`} className="border-t border-line/70">
                    <td className="py-2 text-slate-300">{trade.date || '--'}</td>
                    <td className="py-2 text-right text-slate-300">{number(qty, 4)}</td>
                    <td className="py-2 text-right text-slate-300">{number(soldQty, 4)}</td>
                    <td className="py-2 text-right text-slate-300">{number(activeQty, 4)}</td>
                    <td className="py-2 text-right text-slate-300">{hideAmounts ? '••••' : number(price, 2)}</td>
                    <td className="py-2 text-right text-slate-300">{hideAmounts ? (soldQty > 0 ? '••••' : '--') : avgSellPrice ? number(avgSellPrice, 2) : '--'}</td>
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
