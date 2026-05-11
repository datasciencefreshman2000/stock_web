import { useState } from 'react'
import { Eye, EyeOff, RefreshCw } from 'lucide-react'

import AssetPieChart from '../components/AssetPieChart'
import PriceStatus from '../components/PriceStatus'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useSummary } from '../hooks/useSummary'
import { money, percent, pnlClass } from '../utils/format'

function CashRatioSection({ ownAccounts, hideAmounts }) {
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
            <div className="mb-3 flex h-2.5 overflow-hidden rounded-full bg-line">
              <div
                className="rounded-l-full bg-sky-400 transition-all"
                style={{ width: `${row.stockRatio * 100}%` }}
              />
              <div
                className="rounded-r-full bg-amber-400 transition-all"
                style={{ width: `${row.cashRatio * 100}%` }}
              />
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

export default function Dashboard() {
  const [refreshToken, setRefreshToken] = useState(0)
  const [selectedInvestmentGroup, setSelectedInvestmentGroup] = useState(null)
  const { hideAmounts, toggleHideAmounts } = usePrivacy()
  const { data, error, loading } = useSummary(refreshToken)

  function refreshNow() {
    setRefreshToken((value) => value + 1)
  }

  const today = new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  }).format(new Date())
  const summaryTime = data?.summary_cached_at ? new Date(data.summary_cached_at).toLocaleString('zh-TW') : null

  if (loading) return <LoadingBlock label="正在讀取總覽資料" />
  if (error) return <ErrorBlock error={error} />

  const accounts = data.accounts || {}
  const ownAccountNames = ['台股', '美股']
  const externalAccountNames = ['爸媽美股', 'x']
  const ownAccounts = Object.fromEntries(Object.entries(accounts).filter(([name]) => ownAccountNames.includes(name)))
  const externalAccounts = Object.fromEntries(Object.entries(accounts).filter(([name]) => externalAccountNames.includes(name)))
  const stockRows = Object.entries(ownAccounts).map(([name, row]) => ({
    name,
    value: row.market_value_twd || 0,
  }))
  const investments = data.investments || []
  const investmentTotal = data.investment_total || 0
  const investmentsByType = investments.reduce((acc, row) => {
    const key = row.asset_type || '其他'
    acc[key] = (acc[key] || 0) + Number(row.value || 0)
    return acc
  }, {})
  const ownCashTotal = data.cash?.twd_equivalent || 0
  const ownStockTotal = stockRows.reduce((sum, row) => sum + row.value, 0)
  const ownInvestmentTotal = ownStockTotal + investmentTotal
  const investmentCashTotal = Object.values(ownAccounts).reduce(
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
      .map((row) => ({ name: row.name, value: Number(row.value || 0) })),
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
  const investmentPnlTotal = investments.reduce((sum, row) => sum + Number(row.value || 0) - Number(row.cost || 0), 0)
  const investmentCostTotal = investments.reduce((sum, row) => sum + Number(row.cost || 0), 0)
  const totalRealized = Object.values(ownAccounts).reduce((sum, row) => sum + (row.realized_pnl_twd || 0), 0)
  const totalUnrealized =
    Object.values(ownAccounts).reduce((sum, row) => sum + (row.unrealized_pnl_twd || 0), 0) + investmentPnlTotal
  const ownInvestedTotal =
    Object.values(ownAccounts).reduce((sum, row) => sum + Number(row.invested_twd || row.cost_twd || 0), 0) +
    investmentCostTotal

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
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">蔡加恩的金庫</h1>
            <p className="mt-1 text-xs text-slate-400 sm:text-sm">
              {today} · USD/TWD {data.usd_rate}
              {summaryTime ? (
                <span className="hidden sm:inline"> · {data.summary_cached ? '快取' : '更新'} {summaryTime}</span>
              ) : null}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={toggleHideAmounts}
              className="rounded-md border border-line bg-surface p-2 text-slate-300 hover:border-sky-500 hover:text-white"
              title={hideAmounts ? '顯示金額' : '隱藏金額'}
            >
              {hideAmounts ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
            <button
              type="button"
              onClick={refreshNow}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-sm font-medium text-sky-100 disabled:opacity-60"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">刷新股價</span>
            </button>
          </div>
        </div>
        {summaryTime ? (
          <p className="mt-1 text-xs text-slate-500 sm:hidden">
            {data.summary_cached ? '快取' : '更新'} {summaryTime}
          </p>
        ) : null}
      </header>

      <PriceStatus status={data.price_status} />

      {/* 摘要卡片：手機 2 欄，平板以上 3 欄 */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <SummaryCard label="我的總資產" value={money(data.own_total_assets || data.total_assets)} />
        <SummaryCard label="投資市值" value={money(ownInvestmentTotal)} />
        <SummaryCard label="現金" value={money(ownCashTotal)} />
      </section>

      {/* 圓餅圖：手機橫向滑動，桌機 3 欄 */}
      <section>
        <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0 lg:grid lg:grid-cols-3 lg:overflow-visible lg:pb-0">
          {pieCharts.map((chart) => (
            <div key={chart.key} className="w-[85vw] shrink-0 snap-start sm:w-[60vw] lg:w-auto">
              <AssetPieChart
                title={chart.title}
                data={chart.data}
                onItemClick={chart.onItemClick}
                headerAction={chart.headerAction}
              />
            </div>
          ))}
        </div>
        <p className="mt-1.5 text-center text-xs text-slate-600 lg:hidden">← 左右滑動查看圖表 →</p>
      </section>

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
              const pnl = Number(row.value || 0) - Number(row.cost || 0)
              const roi = Number(row.cost || 0) > 0 ? pnl / Number(row.cost || 0) : null
              return (
                <div key={row.id} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3">
                  <div>
                    <div className="font-medium">{row.name}</div>
                    <div className="text-sm text-slate-400">{row.asset_type}</div>
                  </div>
                  <div className="text-right">
                    <div>{hideAmounts ? maskAmount(money(row.value)) : money(row.value)}</div>
                    <div className={`text-sm ${pnlClass(pnl)}`}>
                      {hideAmounts ? percent(roi) : `${money(pnl)} / ${percent(roi)}`}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* 帳戶現金比例 */}
      <CashRatioSection ownAccounts={ownAccounts} hideAmounts={hideAmounts} />

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
    </div>
  )
}
