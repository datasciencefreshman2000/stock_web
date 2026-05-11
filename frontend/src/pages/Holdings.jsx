import { useState } from 'react'

import AccountCapitalPanel from '../components/AccountCapitalPanel'
import HoldingsTable from '../components/HoldingsTable'
import ManualValueEditor from '../components/ManualValueEditor'
import PriceStatus from '../components/PriceStatus'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { ACCOUNT_TABS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useAsync } from '../hooks/useAsync'
import { usePortfolio } from '../hooks/usePortfolio'
import { useSummary } from '../hooks/useSummary'
import { api } from '../api/client'
import { money, percent, pnlClass } from '../utils/format'

export default function Holdings() {
  const { hideAmounts } = usePrivacy()
  const [tab, setTab] = useState('台股')
  const [refreshToken, setRefreshToken] = useState(0)
  const isManual = tab === '基金&其他'
  const portfolio = usePortfolio(isManual ? '台股' : tab, refreshToken)
  const manual = useAsync(() => api.getManual(), [])
  const summary = useSummary(0)

  const active = isManual ? manual : portfolio
  const currency = tab === '美股' || tab === '爸媽美股' ? 'USD' : 'TWD'
  const dashboard = portfolio.data?.dashboard || {}
  const accountInvested = Number(dashboard.invested ?? dashboard.cost ?? 0)
  const totalPnl = Number(dashboard.unrealized_pnl || 0) + Number(dashboard.realized_pnl || 0)
  const inferredCash = Number(dashboard.inferred_cash ?? accountInvested - Number(dashboard.cost || 0) + Number(dashboard.realized_pnl || 0))
  const accountTotalValue = Number(dashboard.account_total ?? Number(dashboard.market_value || 0) + inferredCash)
  const pnlRatio = accountInvested > 0 ? totalPnl / accountInvested : null
  const unrealizedRatio = accountInvested > 0 ? Number(dashboard.unrealized_pnl || 0) / accountInvested : null
  const realizedRatio = accountInvested > 0 ? Number(dashboard.realized_pnl || 0) / accountInvested : null

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
              className="rounded-md border border-sky-500 bg-sky-500/15 px-4 py-2 text-sm font-medium text-sky-100 disabled:opacity-60"
            >
              刷新股價
            </button>
          ) : null}
        </div>
      </header>

      <div className="flex gap-2 overflow-x-auto">
        {ACCOUNT_TABS.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`shrink-0 rounded-md border px-4 py-2 text-sm ${
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
          <PriceStatus status={portfolio.data.price_status} />
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <SummaryCard label="總損益%" value={percent(pnlRatio)} accent={pnlClass(totalPnl)} />
            <SummaryCard label="市值" value={money(dashboard.market_value, currency)} />
            <SummaryCard label="已投入金額" value={money(accountInvested, currency)} />
            <SummaryCard label="現金" value={money(inferredCash, currency)} accent={pnlClass(inferredCash)} />
            <SummaryCard label="現金+市值" value={money(accountTotalValue, currency)} />
          </section>
          <section className="grid gap-3 sm:grid-cols-2">
            <SummaryCard
              label="未實現損益"
              value={`${money(dashboard.unrealized_pnl, currency)} (${percent(unrealizedRatio)})`}
              accent={pnlClass(dashboard.unrealized_pnl)}
            />
            <SummaryCard
              label="已實現損益"
              value={`${money(dashboard.realized_pnl, currency)} (${percent(realizedRatio)})`}
              accent={pnlClass(dashboard.realized_pnl)}
            />
          </section>
          <AccountCapitalPanel
            account={tab}
            manualValues={manual.data?.values || []}
            cost={dashboard.cost || 0}
            realizedPnl={dashboard.realized_pnl || 0}
            onSaved={manual.reload}
          />
          <HoldingsTable holdings={portfolio.data.holdings || []} currency={currency} />
          {tab === '台股' ? (
            <div className="rounded-md border border-line bg-surface p-3 text-xs text-slate-500">
              手續費+稅{' '}
              <span className="ml-2 text-slate-300">
                {hideAmounts ? maskAmount(money((dashboard.total_fee || 0) + (dashboard.total_tax || 0))) : money((dashboard.total_fee || 0) + (dashboard.total_tax || 0))}
              </span>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
