import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { maskAmount, usePrivacy } from '../../context/PrivacyContext'
import { money } from '../../utils/format'

function compactMoney(value) {
  const amount = Number(value || 0)
  const absolute = Math.abs(amount)
  if (absolute >= 1000000) return `${(amount / 1000000).toFixed(1)}M`
  if (absolute >= 1000) return `${(amount / 1000).toFixed(0)}K`
  return amount.toFixed(0)
}

function Metric({ label, value, tone, hidden }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className={`truncate text-sm font-semibold tabular-nums ${tone}`}>
        {hidden ? maskAmount(money(value)) : money(value)}
      </div>
    </div>
  )
}

function AccountTick({ x, y, payload }) {
  const name = String(payload?.value || '')
  const shown = name.length > 7 ? `${name.slice(0, 7)}…` : name
  return (
    <text x={x - 5} y={y} dy={4} fill="#cbd5e1" fontSize={11} textAnchor="end">
      {shown}
    </text>
  )
}

function CashTooltip({ active, payload, hidden }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  return (
    <div className="rounded-md border border-line bg-[#111827] px-3 py-2 shadow-xl">
      <div className="text-xs font-medium text-white">{row.name}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums text-white">
        {hidden ? maskAmount(money(row.value)) : money(row.value)}
      </div>
    </div>
  )
}

export default function CashBalanceChart({ data }) {
  const { hideAmounts } = usePrivacy()
  const rows = data.filter((item) => item.isTotal || Math.abs(Number(item.value || 0)) > 0.000001)
  const positive = rows.filter((item) => !item.isTotal && item.value > 0).reduce((sum, item) => sum + item.value, 0)
  const negative = rows.filter((item) => !item.isTotal && item.value < 0).reduce((sum, item) => sum + item.value, 0)
  const net = rows.find((item) => item.isTotal)?.value ?? positive + negative
  const extent = Math.max(1, ...rows.map((item) => Math.abs(Number(item.value || 0)))) * 1.12
  const chartHeight = Math.max(220, rows.length * 38)

  return (
    <section className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-4 py-3">
        <div className="text-sm font-medium text-slate-200">現金帳戶正負分布</div>
        <div className="mt-2 grid grid-cols-3 gap-3">
          <Metric label="正資產" value={positive} tone="text-emerald-300" hidden={hideAmounts} />
          <Metric label="負債" value={negative} tone="text-rose-300" hidden={hideAmounts} />
          <Metric label="現金淨額" value={net} tone="text-sky-200" hidden={hideAmounts} />
        </div>
      </div>
      {rows.length ? (
        <div className="px-1 py-3 sm:px-3">
          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 14, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="#253044" strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                domain={[-extent, extent]}
                tickFormatter={(value) => (hideAmounts ? '••' : compactMoney(value))}
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#253044' }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={90}
                tick={<AccountTick />}
                axisLine={false}
                tickLine={false}
              />
              <ReferenceLine x={0} stroke="#94a3b8" strokeWidth={1.5} />
              <Tooltip cursor={{ fill: 'rgba(148, 163, 184, 0.06)' }} content={<CashTooltip hidden={hideAmounts} />} />
              <Bar dataKey="value" radius={4} maxBarSize={22}>
                {rows.map((item) => (
                  <Cell
                    key={item.name}
                    fill={item.isTotal ? '#38bdf8' : item.value >= 0 ? '#34d399' : '#fb7185'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="px-4 py-6 text-sm text-slate-500">目前沒有現金帳戶資料</div>
      )}
    </section>
  )
}
