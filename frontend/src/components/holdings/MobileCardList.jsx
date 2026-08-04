import Metric from './Metric'
import { money, percent, pnlClass } from '../../utils/format'

export default function MobileCardList({ holdings, account, currency, hideAmounts, activeTicker, onToggle, renderDetail }) {
  return (
    <div className="divide-y divide-line">
      {holdings.map((row) => (
        <div key={row.ticker} className={`px-3 py-2 transition-colors ${activeTicker === row.ticker ? 'bg-sky-500/5' : 'hover:bg-sky-500/5'}`}>
          <button type="button" onClick={() => onToggle(row.ticker)} className="group mb-1 flex min-h-0 w-full items-start justify-between gap-3 rounded-md px-1 py-1 text-left transition hover:-translate-y-0.5 hover:bg-sky-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.99]">
            <div className="min-w-0">
              <div className="flex min-w-0 items-baseline gap-2">
                <span className="shrink-0 text-sm font-medium text-white underline-offset-4 group-hover:text-sky-100 group-hover:underline">{row.ticker}</span>
                {account === '台股' && row.company_name ? <span className="truncate text-[11px] text-slate-400">{row.company_name}</span> : null}
              </div>
              {account !== '台股' && row.company_name ? <div className="truncate text-[11px] text-slate-400">{row.company_name}</div> : null}
            </div>
            <div className="shrink-0 text-right text-[11px] text-slate-400">
              <div className="leading-tight">佔比</div>
              <div className="text-sm font-semibold leading-tight text-white">{percent(row.weight)}</div>
            </div>
          </button>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Metric label="市值" value={hideAmounts ? '••••' : money(row.market_value, currency)} inline />
            <Metric label="損益" value={percent(row.pnl_pct)} accent={pnlClass(row.pnl)} inline />
          </div>
          {activeTicker === row.ticker ? renderDetail(row, 'mt-3') : null}
        </div>
      ))}
    </div>
  )
}
