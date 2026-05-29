import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money } from '../utils/format'

const COLORS = ['#22c55e', '#38bdf8', '#f59e0b', '#a78bfa', '#f472b6', '#94a3b8']

function pieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }) {
  if (percent < 0.06) return null
  const radius = innerRadius + (outerRadius - innerRadius) * 0.55
  const x = cx + radius * Math.cos((-midAngle * Math.PI) / 180)
  const y = cy + radius * Math.sin((-midAngle * Math.PI) / 180)

  return (
    <text x={x} y={y} fill="#ffffff" textAnchor="middle" dominantBaseline="central" className="text-[11px] font-semibold">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

export default function AssetPieChart({ data, title = '資產分布', onItemClick, headerAction, compact = false, dense = false }) {
  const { hideAmounts } = usePrivacy()
  const [showLegend, setShowLegend] = useState(true)
  const rows = data.filter((item) => item.value > 0)
  const total = rows.reduce((sum, item) => sum + item.value, 0)
  const chartHeight = dense ? 'h-32 sm:h-36 lg:h-28' : compact ? 'h-40' : 'h-48 sm:h-60'
  const outerRadius = dense ? 54 : compact ? 66 : 82
  const innerRadius = dense ? 34 : compact ? 42 : 52
  if (!rows.length) {
    return <div className="rounded-md border border-line bg-surface p-4 text-slate-400">{title}：沒有資料</div>
  }

  return (
    <div className={`min-w-0 overflow-hidden rounded-md border border-line bg-surface ${dense ? 'p-2.5' : 'p-3'}`}>
      <div className={`${dense ? 'mb-1' : 'mb-2'} flex items-center justify-between gap-3`}>
        <div className="min-w-0 text-sm font-medium leading-tight text-slate-200">{title}</div>
        {headerAction}
      </div>
      <div className={`relative ${chartHeight}`}>
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <div className="text-center">
            <div className="text-xs text-slate-500">合計</div>
            <div className={`${compact || dense ? 'max-w-24 text-xs' : 'max-w-28 text-sm sm:max-w-none'} break-words font-semibold leading-tight text-white`}>
              {hideAmounts ? maskAmount(money(total)) : money(total)}
            </div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="name"
              outerRadius={outerRadius}
              innerRadius={innerRadius}
              label={pieLabel}
              labelLine={false}
              onClick={(item) => onItemClick?.(item.name)}
              className={onItemClick ? 'cursor-pointer' : ''}
            >
              {rows.map((entry, index) => (
                <Cell key={entry.name} fill={COLORS[index % COLORS.length]} className="transition-opacity hover:opacity-80" />
              ))}
            </Pie>
            <Tooltip formatter={(value) => (hideAmounts ? maskAmount(money(value)) : money(value))} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex justify-center">
        <button
          type="button"
          onClick={() => setShowLegend((value) => !value)}
          className="rounded-md border border-line p-1.5 text-slate-400 transition hover:border-sky-500 hover:text-white"
          title={showLegend ? '收起明細' : `顯示明細 (${rows.length})`}
          aria-label={showLegend ? '收起明細' : `顯示明細 (${rows.length})`}
        >
          {showLegend ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      {showLegend ? (
        <div className={`page-enter mt-2 grid ${dense ? 'gap-1 text-[11px]' : 'gap-1.5 text-xs'}`}>
          {rows.map((item, index) => (
            <button
              key={item.name}
              type="button"
              onClick={() => onItemClick?.(item.name)}
              className={`grid w-full min-w-0 grid-cols-[minmax(0,1fr)_3.2rem_minmax(0,5.8rem)] items-center gap-2 rounded-md px-2 text-left text-slate-300 hover:bg-white/5 ${
                dense ? 'py-1' : 'py-1.5'
              }`}
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: COLORS[index % COLORS.length] }} />
                <span className="truncate">{item.name}</span>
              </span>
              <span className="text-right tabular-nums text-slate-500">
                {total > 0 ? `${((item.value / total) * 100).toFixed(1)}%` : '--'}
              </span>
              <span className="min-w-0 truncate text-right tabular-nums text-slate-200">
                {hideAmounts ? maskAmount(money(item.value)) : money(item.value)}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
