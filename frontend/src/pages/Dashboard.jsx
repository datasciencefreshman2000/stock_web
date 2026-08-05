import { useState } from 'react'
import { RefreshCw } from 'lucide-react'

import AssetPieChart from '../components/AssetPieChart'
import CashRatioSection from '../components/dashboard/CashRatioSection'
import PriceStatus from '../components/PriceStatus'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useRefreshAll, useSummaryQuery } from '../hooks/queries'
import {
  investmentCashTwd,
  investmentCostTwd,
  investmentPnlTwd,
  investmentTotalTwd,
  investmentValueTwd,
} from '../utils/investments'
import { money, percent, pnlClass } from '../utils/format'

export default function Dashboard() {
  const [selectedInvestmentGroup, setSelectedInvestmentGroup] = useState(null)
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const { hideAmounts } = usePrivacy()
  const { data, error, isLoading: loading } = useSummaryQuery()

  // 刷新是同步的：等後端抓完價、重算完，快取失效後畫面自動重讀
  const { refreshing: refreshInBackground, refreshNow } = useRefreshAll()

  const today = new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  }).format(new Date())
  const summaryTime = data?.summary_cached_at ? new Date(data.summary_cached_at).toLocaleString('zh-TW') : null

  if (loading && !data) return <LoadingBlock label="正在讀取總覽資料" />
  if (error && !data) return <ErrorBlock error={error} />

  const accounts = data.accounts || {}
  const ownAccountNames = ['台股', '美股']
  const externalAccountNames = ['爸媽美股']
  const ownAccounts = Object.fromEntries(Object.entries(accounts).filter(([name]) => ownAccountNames.includes(name)))
  const externalAccounts = Object.fromEntries(Object.entries(accounts).filter(([name]) => externalAccountNames.includes(name)))
  const stockRows = Object.entries(ownAccounts).map(([name, row]) => ({
    name,
    value: row.market_value_twd || 0,
  }))
  const investments = data.investments || []
  const investmentTotal = data.investment_total || 0
  const manualInvestmentCashTotal = data.manual_investment_cash_total || 0
  const investmentsByType = investments.reduce((acc, row) => {
    const key = row.asset_type || '其他'
    acc[key] = (acc[key] || 0) + investmentValueTwd(row)
    return acc
  }, {})
  const ownCashTotal = data.cash?.twd_equivalent || 0
  const ownStockTotal = stockRows.reduce((sum, row) => sum + row.value, 0)
  const ownInvestmentTotal = ownStockTotal + investmentTotal
  const investmentCashTotal = manualInvestmentCashTotal + Object.values(ownAccounts).reduce(
    (sum, row) => sum + Math.max(Number(row.inferred_cash_twd || 0), 0),
    0,
  )
  const chartData = ['台股', '美股', '其他']
    .map((name) => ({
      name,
      value: (ownAccounts[name]?.market_value_twd || 0) + (investmentsByType[name] || 0),
    }))
    .filter((row) => row.value > 0)
  const investmentDetails = selectedInvestmentGroup
    ? [
    selectedInvestmentGroup === '台股' && ownAccounts.台股
      ? { name: '自選台股', value: ownAccounts.台股.market_value_twd || 0 }
      : null,
    selectedInvestmentGroup === '美股' && ownAccounts.美股
      ? { name: '自選美股', value: ownAccounts.美股.market_value_twd || 0 }
      : null,
    ...investments
      .filter((row) => (row.asset_type || '其他') === selectedInvestmentGroup)
      .map((row) => ({ name: row.name, value: investmentValueTwd(row) })),
  ].filter(Boolean)
    : []
  const investmentChartRows = selectedInvestmentGroup ? investmentDetails : chartData
  const cashAssetChart = [
    { name: '投資', value: ownInvestmentTotal },
    { name: '投資內現金', value: investmentCashTotal },
  ]
  const totalChart = [
    { name: '投資', value: ownInvestmentTotal + investmentCashTotal },
    { name: '現金', value: ownCashTotal },
  ]
  const investmentPnlTotal = investments.reduce((sum, row) => sum + investmentPnlTwd(row), 0)
  const investmentCostTotal = investments.reduce((sum, row) => sum + investmentCostTwd(row), 0)
  const totalRealized = Object.values(ownAccounts).reduce((sum, row) => sum + (row.realized_pnl_twd || 0), 0)
  const totalUnrealized =
    Object.values(ownAccounts).reduce((sum, row) => sum + (row.unrealized_pnl_twd || 0), 0) + investmentPnlTotal
  const ownInvestedTotal =
    Object.values(ownAccounts).reduce((sum, row) => sum + Number(row.invested_twd || row.cost_twd || 0), 0) +
    investmentCostTotal
  const totalAssets = data.own_total_assets || data.total_assets
  const summaryCards = [
    { key: 'total-assets', label: '總資產', value: money(totalAssets), countTo: totalAssets },
    { key: 'investment-value', label: '投資市值', value: money(ownInvestmentTotal), countTo: ownInvestmentTotal },
    { key: 'cash', label: '現金', value: money(ownCashTotal), countTo: ownCashTotal },
    { key: 'investment-cash', label: '投資用現金', value: money(investmentCashTotal), countTo: investmentCashTotal },
  ]
  const toggleSummary = () => {
    setSummaryExpanded((expanded) => !expanded)
  }

  const pieCharts = [
    {
      key: 'total',
      title: '總資產分布',
      data: totalChart,
    },
    {
      key: 'investment',
      title: selectedInvestmentGroup ? `${selectedInvestmentGroup}投資組成` : '投資資產分布',
      data: investmentChartRows,
      onItemClick: selectedInvestmentGroup ? undefined : setSelectedInvestmentGroup,
      headerAction: selectedInvestmentGroup ? (
        <button
          type="button"
          onClick={() => setSelectedInvestmentGroup(null)}
          className="rounded-md border border-line px-2.5 py-1 text-xs text-slate-300 hover:border-sky-500 hover:text-white"
        >
          返回分布
        </button>
      ) : null,
    },
    {
      key: 'cash',
      title: '投資內現金與資產比例',
      data: cashAssetChart,
    },
  ]

  return (
    <div className="grid gap-5">
      {/* Header */}
      <header>
        {summaryTime ? (
          <div className="flex justify-end">
            <div className="max-w-[11rem] text-right text-xs leading-tight text-slate-500">
              {data.summary_cached ? '快取' : '更新'} {summaryTime}
            </div>
          </div>
        ) : null}
        <div className={`${summaryTime ? 'mt-1.5' : ''} flex items-center gap-2`}>
          <p className="flex-1 text-xs text-slate-400">
            {today} · USD/TWD {Number(data.usd_rate || 0).toFixed(2)}
          </p>
          <button
            type="button"
            onClick={refreshNow}
            disabled={loading || refreshInBackground}
            className={`flex items-center gap-1.5 rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-sm font-medium text-sky-100 transition active:scale-[0.99] disabled:opacity-70 ${loading || refreshInBackground ? 'submit-pulse' : 'hover:bg-sky-500/20'}`}
          >
            <RefreshCw size={14} className={loading || refreshInBackground ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">{refreshInBackground ? '更新中…' : '刷新股價'}</span>
          </button>
        </div>
      </header>

      {/* 摘要卡片：點擊可在總資產大卡與四格摘要間切換 */}
      <section>
        {!summaryExpanded ? (
          <button
            type="button"
            onClick={toggleSummary}
            className="summary-single-enter relative block w-full text-left transition active:scale-[0.99]"
            aria-expanded={summaryExpanded}
          >
            <SummaryCard hero label="總資產" value={money(totalAssets)} countTo={totalAssets} />
          </button>
        ) : null}
        <div className={`${summaryExpanded ? 'summary-grid-enter grid' : 'hidden'} grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3`}>
          {summaryCards.map((card) => (
            <button
              key={card.key}
              type="button"
              onClick={toggleSummary}
              className="relative text-left transition active:scale-[0.99]"
              aria-label="切換總資產摘要"
              aria-expanded={summaryExpanded}
            >
              <SummaryCard compact label={card.label} value={card.value} countTo={card.countTo} />
            </button>
          ))}
        </div>
      </section>

      {/* 圓餅圖：手機單張滑動 carousel，桌機 3 欄 grid */}
      <section>
        {/* 手機 carousel */}
        <div className="scrollbar-hide flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3 lg:hidden">
          {pieCharts.map((chart) => (
            <div key={chart.key} className="w-full flex-none snap-start">
              <AssetPieChart
                title={chart.title}
                data={chart.data}
                onItemClick={chart.onItemClick}
                headerAction={chart.headerAction}
                compact
              />
            </div>
          ))}
          {/* 尾端佔位 = container 寬 - 卡片寬 = 2rem，讓最後一張也能 snap 到左側 */}
          <div className="w-8 flex-none" aria-hidden="true" />
        </div>
        <p className="mb-1 text-center text-xs text-slate-600 lg:hidden">← 左右滑動查看圖表 →</p>

        {/* 桌機 grid */}
        <div className="hidden gap-5 lg:grid lg:grid-cols-3">
          {pieCharts.map((chart) => (
            <AssetPieChart
              key={chart.key}
              title={chart.title}
              data={chart.data}
              onItemClick={chart.onItemClick}
              headerAction={chart.headerAction}
            />
          ))}
        </div>
      </section>

      {/* 帳戶現金比例 */}
      <CashRatioSection ownAccounts={ownAccounts} hideAmounts={hideAmounts} />

      {investmentDetails.length ? (
        <section className="rounded-md border border-line bg-surface">
          <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">
            {selectedInvestmentGroup}投資組成
          </div>
          <div className="divide-y divide-line">
            {investmentDetails.map((row) => (
              <div key={row.name} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3 text-sm">
                <div className="text-slate-300">{row.name}</div>
                <div className="text-right text-white">{hideAmounts ? maskAmount(money(row.value)) : money(row.value)}</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-md border border-line bg-surface">
          <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">各帳戶快速摘要</div>
          <div className="divide-y divide-line">
            {Object.entries(ownAccounts).map(([name, row]) => {
              const pnl = Number(row.unrealized_pnl_twd || 0) + Number(row.realized_pnl_twd || 0)
              const invested = Number(row.invested_twd || row.cost_twd || 0)
              const roi = invested > 0 ? pnl / invested : null
              return (
                <div key={name} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3">
                  <div>
                    <div className="font-medium">{name}</div>
                    <div className="text-sm text-slate-400">投入 {hideAmounts ? maskAmount(money(invested)) : money(invested)}</div>
                  </div>
                  <div className="text-right">
                    <div>{hideAmounts ? maskAmount(money(row.market_value_twd)) : money(row.market_value_twd)}</div>
                    <div className={`text-sm ${pnlClass(pnl)}`}>
                      {hideAmounts ? percent(roi) : `${money(pnl)} / ${percent(roi)}`}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        <div className="rounded-md border border-line bg-surface">
          <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">基金與其他投資</div>
          <div className="divide-y divide-line">
            {investments.map((row) => {
              const currency = row.currency || 'TWD'
              const cost = Number(row.cost || 0)
              const total = Number(row.value || 0) + Number(row.cash_amount || 0)
              const pnl = total - cost
              const roi = cost > 0 ? pnl / cost : null
              return (
                <div key={row.id} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3">
                  <div>
                    <div className="font-medium">{row.name}</div>
                    <div className="text-sm text-slate-400">{row.asset_type} · {currency}</div>
                  </div>
                  <div className="text-right">
                    <div>{hideAmounts ? maskAmount(money(total, currency)) : money(total, currency)}</div>
                    <div className={`text-sm ${pnlClass(pnl)}`}>
                      {hideAmounts ? percent(roi) : `${money(pnl, currency)} / ${percent(roi)}`}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="rounded-md border border-line bg-surface p-4">
        <div className="mb-3 text-sm font-medium">損益</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <SummaryCard
            label="未實現損益"
            value={`${money(totalUnrealized)} (${percent(ownInvestedTotal > 0 ? totalUnrealized / ownInvestedTotal : null)})`}
            accent={pnlClass(totalUnrealized)}
          />
          <SummaryCard
            label="已實現損益"
            value={`${money(totalRealized)} (${percent(ownInvestedTotal > 0 ? totalRealized / ownInvestedTotal : null)})`}
            accent={pnlClass(totalRealized)}
          />
        </div>
      </section>

      <section className="rounded-md border border-line bg-surface">
        <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">獨立管理帳戶</div>
        <div className="divide-y divide-line">
          {Object.entries(externalAccounts).map(([name, row]) => {
            const pnl = Number(row.unrealized_pnl_twd || 0) + Number(row.realized_pnl_twd || 0)
            const invested = Number(row.invested_twd || row.cost_twd || 0)
            const roi = invested > 0 ? pnl / invested : null
            return (
              <div key={name} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3">
                <div>
                  <div className="font-medium">{name}</div>
                  <div className="text-sm text-slate-400">不列入我的總資產</div>
                </div>
                <div className="text-right">
                  <div>{hideAmounts ? maskAmount(money(row.market_value_twd)) : money(row.market_value_twd)}</div>
                  <div className={`text-sm ${pnlClass(pnl)}`}>
                    {hideAmounts ? percent(roi) : `${money(pnl)} / ${percent(roi)}`}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <PriceStatus status={data.price_status} />
    </div>
  )
}
