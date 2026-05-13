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

export default function AssetPieChart({ data, title = '資產分布', onItemClick, headerAction }) {
  const { hideAmounts } = usePrivacy()
  const rows = data.filter((item) => item.value > 0)
  const total = rows.reduce((sum, item) => sum + item.value, 0)
  if (!rows.length) {
    return <div className="rounded-md border border-line bg-surface p-5 text-slate-400">{title}：尚無資料</div>
  }

  return (
    <div className="rounded-md border border-line bg-surface p-3 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0 text-sm font-medium leading-tight text-slate-200">{title}</div>
        {headerAction}
      </div>
      <div className="relative h-56 sm:h-72">
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <div className="text-center">
            <div className="text-xs text-slate-500">合計</div>
            <div className="max-w-28 break-words text-sm font-semibold leading-tight text-white sm:max-w-none">{hideAmounts ? maskAmount(money(total)) : money(total)}</div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="name"
              outerRadius={92}
              innerRadius={56}
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
      <div className="mt-2 grid gap-2 text-xs sm:text-sm">
        {rows.map((item, index) => (
          <button
            key={item.name}
            type="button"
            onClick={() => onItemClick?.(item.name)}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md px-2 py-2 text-left text-slate-300 hover:bg-white/5"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[index % COLORS.length] }} />
              <span className="truncate">{item.name}</span>
            </span>
            <span className="text-right tabular-nums text-slate-500">
              {total > 0 ? `${((item.value / total) * 100).toFixed(1)}%` : '--'}
            </span>
            <span className="col-span-2 truncate pl-4 tabular-nums text-slate-200 sm:col-span-1 sm:pl-4 sm:text-right">{hideAmounts ? maskAmount(money(item.value)) : money(item.value)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
