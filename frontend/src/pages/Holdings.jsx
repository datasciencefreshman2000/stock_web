import { useState } from 'react'

import AssetPieChart from '../components/AssetPieChart'
import HoldingsTable from '../components/HoldingsTable'
import ManualValueEditor from '../components/ManualValueEditor'
import PriceStatus from '../components/PriceStatus'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import { ACCOUNT_TABS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useAsync } from '../hooks/useAsync'
import { usePortfolio } from '../hooks/usePortfolio'
import { useSummary } from '../hooks/useSummary'
import { api } from '../api/client'
import { money, percent, pnlClass } from '../utils/format'

function MiniMetric({ label, value, accent }) {
  return (
    <div className="min-w-0 rounded-md border border-line bg-surface p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`mt-1 truncate text-base font-semibold tabular-nums sm:text-lg ${accent || 'text-white'}`}>{value}</div>
    </div>
  )
}

export default function Holdings() {
  const { hideAmounts } = usePrivacy()
  const [tab, setTab] = useState(ACCOUNT_TABS[0])
  const [refreshToken, setRefreshToken] = useState(0)
  const isManual = tab === ACCOUNT_TABS[3]
  const portfolio = usePortfolio(isManual ? ACCOUNT_TABS[0] : tab, refreshToken)
  const manual = useAsync(() => api.getManual(), [])
  const summary = useSummary(0)

  const active = isManual ? manual : portfolio
  const currency = tab === ACCOUNT_TABS[1] || tab === ACCOUNT_TABS[2] ? 'USD' : 'TWD'
  const dashboard = portfolio.data?.dashboard || {}
  const accountInvested = Number(dashboard.invested ?? dashboard.cost ?? 0)
  const totalPnl = Number(dashboard.unrealized_pnl || 0) + Number(dashboard.realized_pnl || 0)
  const inferredCash = Number(dashboard.inferred_cash ?? accountInvested - Number(dashboard.cost || 0) + Number(dashboard.realized_pnl || 0))
  const accountTotalValue = Number(dashboard.account_total ?? Number(dashboard.market_value || 0) + inferredCash)
  const pnlRatio = accountInvested > 0 ? totalPnl / accountInvested : null
  const unrealizedRatio = accountInvested > 0 ? Number(dashboard.unrealized_pnl || 0) / accountInvested : null
  const realizedRatio = accountInvested > 0 ? Number(dashboard.realized_pnl || 0) / accountInvested : null
  const allocation = [
    { name: '已投入金額', value: Math.max(Number(dashboard.cost || 0), 0) },
    { name: '現金', value: Math.max(inferredCash, 0) },
  ]

  return (
    <div className="grid gap-5">
      <header>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold">持倉明細</h1>
          {!isManual ? (
            <button
              type="button"
              onClick={() => setRefreshToken((value) => value + 1)}
              disabled={portfolio.loading}
              className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-sm font-medium text-sky-100 disabled:opacity-60 sm:px-4"
            >
              刷新股價
            </button>
          ) : null}
        </div>
      </header>

      <div className="scrollbar-hide flex gap-2 overflow-x-auto pb-1">
        {ACCOUNT_TABS.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`shrink-0 rounded-md border px-3 py-2 text-sm sm:px-4 ${
              tab === item ? 'border-sky-400 bg-sky-500/15 text-white' : 'border-line bg-surface text-slate-300'
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {active.loading ? <LoadingBlock label="正在讀取持倉資料" /> : null}
      {active.error ? <ErrorBlock error={active.error} /> : null}

      {!active.loading && !active.error && isManual ? (
        <ManualValueEditor investments={manual.data?.investments || []} usdRate={summary.data?.usd_rate || 31.316} onSaved={manual.reload} />
      ) : null}

      {!active.loading && !active.error && !isManual ? (
        <>
          <section className="grid gap-3 lg:grid-cols-[1fr_0.9fr]">
            <div className="grid grid-cols-2 gap-3">
              <MiniMetric
                label="總損益"
                value={`${hideAmounts ? maskAmount(money(totalPnl, currency)) : money(totalPnl, currency)} (${percent(pnlRatio)})`}
                accent={pnlClass(totalPnl)}
              />
              <MiniMetric label="現金+市值" value={hideAmounts ? maskAmount(money(accountTotalValue, currency)) : money(accountTotalValue, currency)} />
              <MiniMetric label="現金" value={hideAmounts ? maskAmount(money(inferredCash, currency)) : money(inferredCash, currency)} accent={pnlClass(inferredCash)} />
              <MiniMetric label="市值" value={hideAmounts ? maskAmount(money(dashboard.market_value, currency)) : money(dashboard.market_value, currency)} />
              <MiniMetric
                label="未實現損益"
                value={`${hideAmounts ? maskAmount(money(dashboard.unrealized_pnl, currency)) : money(dashboard.unrealized_pnl, currency)} (${percent(unrealizedRatio)})`}
                accent={pnlClass(dashboard.unrealized_pnl)}
              />
              <MiniMetric
                label="已實現損益"
                value={`${hideAmounts ? maskAmount(money(dashboard.realized_pnl, currency)) : money(dashboard.realized_pnl, currency)} (${percent(realizedRatio)})`}
                accent={pnlClass(dashboard.realized_pnl)}
              />
            </div>
            <AssetPieChart title="現金與已投入金額分布" data={allocation} />
          </section>

          <HoldingsTable holdings={portfolio.data.holdings || []} account={tab} currency={currency} />

          {tab === ACCOUNT_TABS[0] ? (
            <div className="rounded-md border border-line bg-surface p-3 text-xs text-slate-500">
              手續費+稅
              <span className="ml-2 text-slate-300">
                {hideAmounts ? maskAmount(money((dashboard.total_fee || 0) + (dashboard.total_tax || 0))) : money((dashboard.total_fee || 0) + (dashboard.total_tax || 0))}
              </span>
            </div>
          ) : null}

          <PriceStatus status={portfolio.data.price_status} />
        </>
      ) : null}
    </div>
  )
}
