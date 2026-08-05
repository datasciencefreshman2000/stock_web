import { money } from '../../utils/format'
import AllocationBar from './AllocationBar'

export default function CashRatioSection({ ownAccounts, hideAmounts }) {
  const rows = Object.entries(ownAccounts).map(([name, row]) => {
    const cash = Math.max(Number(row.inferred_cash ?? 0), 0)
    const stocks = Math.max(Number(row.market_value ?? 0), 0)
    const total = cash + stocks
    const cashRatio = total > 0 ? cash / total : 0
    const stockRatio = 1 - cashRatio
    const currency = name === '美股' ? 'USD' : 'TWD'
    return { name, cash, stocks, total, cashRatio, stockRatio, currency }
  })

  if (!rows.length) return null

  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">帳戶現金比例</div>
      <div className="divide-y divide-line">
        {rows.map((row) => (
          <div key={row.name} className="px-4 py-4">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium text-white">{row.name}</span>
              <span className="text-slate-400 tabular-nums">
                現金 <span className="text-white">{(row.cashRatio * 100).toFixed(1)}%</span>
                {' / '}
                股票 <span className="text-white">{(row.stockRatio * 100).toFixed(1)}%</span>
              </span>
            </div>
            <div className="mb-3">
              <AllocationBar stockRatio={row.stockRatio} cashRatio={row.cashRatio} />
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-sm bg-sky-400" />
                <div>
                  <div className="text-slate-400">股票市值</div>
                  <div className="text-slate-100">{hideAmounts ? '••••' : money(row.stocks, row.currency)}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-sm bg-amber-400" />
                <div>
                  <div className="text-slate-400">帳戶現金</div>
                  <div className="text-slate-100">{hideAmounts ? '••••' : money(row.cash, row.currency)}</div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
