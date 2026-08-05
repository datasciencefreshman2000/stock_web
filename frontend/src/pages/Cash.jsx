import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import AccountInvestedPanel from '../components/cash/AccountInvestedPanel'
import CapitalMovementPanel from '../components/cash/CapitalMovementPanel'
import ChartPanel from '../components/cash/ChartPanel'
import { BANK_ROWS, BASE_ROWS, DEBOUNCE_MS } from '../components/cash/constants'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useInvalidateMoney, useManualQuery, useSummaryQuery } from '../hooks/queries'
import { money } from '../utils/format'

export default function Cash() {
  const { hideAmounts } = usePrivacy()
  const manualQuery = useManualQuery()
  const summaryQuery = useSummaryQuery()
  const invalidateMoney = useInvalidateMoney()

  // 保留舊有的 { data, error, loading } 形狀，下面的畫面程式碼不用改
  const manual = { data: manualQuery.data, error: manualQuery.error, loading: manualQuery.isLoading }
  const summary = { data: summaryQuery.data, error: summaryQuery.error, loading: summaryQuery.isLoading }
  const [drafts, setDrafts] = useState({})
  const [statuses, setStatuses] = useState({})
  const [selectedRows, setSelectedRows] = useState(new Set())
  const [zeroRowsOpen, setZeroRowsOpen] = useState(false)
  const timersRef = useRef({})
  const processingRef = useRef(false)
  const queueRef = useRef(new Map())

  useEffect(() => {
    if (!manual.data?.cash) return
    setDrafts(Object.fromEntries(manual.data.cash.map((row) => [row.id, row])))
  }, [manual.data])

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach(clearTimeout)
    }
  }, [])

  const usdRate = summary.data?.usd_rate || 31.316
  const rows = manual.data?.cash || []
  const grouped = useMemo(() => {
    const map = new Map(BASE_ROWS.map((name) => [name, { name, TWD: null, USD: null }]))
    rows
      .filter((row) => row.name !== '新增外幣')
      .forEach((row) => {
        if (!map.has(row.name)) map.set(row.name, { name: row.name, TWD: null, USD: null })
        const currency = row.currency || 'TWD'
        if (currency === 'TWD' || currency === 'USD') map.get(row.name)[currency] = row
      })
    return [...map.values()]
  }, [rows])

  function cellKey(item, currency) {
    return item[currency]?.id || `${item.name}-${currency}`
  }

  function cellValue(item, currency) {
    const key = cellKey(item, currency)
    if (drafts[key]?.amount !== undefined) return drafts[key].amount
    return item[currency]?.amount ?? ''
  }

  function setStatus(key, status) {
    setStatuses((current) => ({ ...current, [key]: status }))
  }

  async function processQueue() {
    if (processingRef.current) return
    processingRef.current = true

    while (queueRef.current.size > 0) {
      const [key, job] = queueRef.current.entries().next().value
      queueRef.current.delete(key)
      setStatus(key, 'saving')
      try {
        if (job.row?.id) {
          await api.updateCash(job.row.id, job.amount, job.currency)
          setDrafts((current) => ({
            ...current,
            [job.row.id]: { ...job.row, amount: job.amount, currency: job.currency },
          }))
        } else {
          const response = await api.createCash({
            name: job.name,
            account: '',
            category: '現金',
            currency: job.currency,
            amount: job.amount,
          })
          const created = response.cash
          setDrafts((current) => {
            const next = { ...current, [created.id]: created }
            delete next[key]
            return next
          })
          job.item[job.currency] = created
        }
        setStatus(key, 'saved')
        invalidateMoney()
      } catch {
        setStatus(key, 'error')
      }
    }

    processingRef.current = false
  }

  function enqueueSave(item, currency, rawValue) {
    const key = cellKey(item, currency)
    const amount = Number(rawValue || 0)
    clearTimeout(timersRef.current[key])
    setStatus(key, 'editing')
    timersRef.current[key] = setTimeout(() => {
      queueRef.current.set(key, {
        key,
        item,
        row: item[currency],
        name: item.name,
        currency,
        amount,
      })
      setStatus(key, 'pending')
      processQueue()
    }, DEBOUNCE_MS)
  }

  function updateCell(item, currency, rawValue) {
    const key = cellKey(item, currency)
    setDrafts((current) => ({
      ...current,
      [key]: {
        ...(item[currency] || { name: item.name, currency }),
        amount: rawValue,
      },
    }))
    enqueueSave(item, currency, rawValue)
  }

  function toggleSelected(name) {
    setSelectedRows((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  function resetSelectedAccounts() {
    sortedGrouped
      .filter((item) => selectedRows.has(item.name))
      .forEach((item) => {
        updateCell(item, 'TWD', '0')
        updateCell(item, 'USD', '0')
      })
  }

  function accountTotal(item) {
    const twd = Number(cellValue(item, 'TWD') || 0)
    const usd = Number(cellValue(item, 'USD') || 0)
    return twd + usd * usdRate
  }

  async function refreshMoneyNow() {
    await invalidateMoney()
    await Promise.all([manualQuery.refetch(), summaryQuery.refetch()])
  }

  const totals = grouped.reduce(
    (acc, item) => {
      const twd = Number(cellValue(item, 'TWD') || 0)
      const usd = Number(cellValue(item, 'USD') || 0)
      acc.twd += twd
      acc.usd += usd
      acc.total += twd + usd * usdRate
      return acc
    },
    { twd: 0, usd: 0, total: 0 },
  )
  const bankNames = grouped.filter((item) => BANK_ROWS.includes(item.name)).map((item) => item.name)
  const positiveBankNames = grouped
    .filter((item) => BANK_ROWS.includes(item.name))
    .filter((item) => Number(cellValue(item, 'TWD') || 0) > 0 || Number(cellValue(item, 'USD') || 0) > 0)
    .map((item) => item.name)
  const sortedGrouped = [...grouped].sort((a, b) => Math.abs(accountTotal(b)) - Math.abs(accountTotal(a)))
  const activeGrouped = sortedGrouped.filter((item) => Math.abs(accountTotal(item)) > 0.000001)
  const zeroGrouped = sortedGrouped.filter((item) => Math.abs(accountTotal(item)) <= 0.000001)

  function renderCashRow(item) {
    const twd = cellValue(item, 'TWD')
    const usd = cellValue(item, 'USD')
    const total = Number(twd || 0) + Number(usd || 0) * usdRate
    const twdStatus = statuses[cellKey(item, 'TWD')]
    const usdStatus = statuses[cellKey(item, 'USD')]
    const rowStatus = [twdStatus, usdStatus].find((status) => ['saving', 'pending', 'editing', 'error'].includes(status))
    const selected = selectedRows.has(item.name)
    return (
      <div key={item.name} className={`grid gap-2 px-3 py-3 transition sm:grid-cols-[minmax(10rem,1fr)_7rem_7rem] sm:items-center sm:px-4 ${selected ? 'bg-sky-500/10' : ''}`}>
        <button
          type="button"
          onClick={() => toggleSelected(item.name)}
          className={`grid min-h-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-md border px-2 py-2 text-left transition ${
            selected ? 'border-sky-400 bg-sky-500/15' : 'border-transparent hover:border-line hover:bg-panel/60'
          }`}
        >
          <span className="truncate font-medium text-white">{item.name}</span>
          <span className="shrink-0 text-right text-xs tabular-nums text-slate-300">
            {hideAmounts ? maskAmount(money(total)) : money(total)}
          </span>
        </button>
        <div className="grid grid-cols-2 gap-2 sm:contents">
          <label className="grid gap-1 text-[11px] text-slate-500 sm:block">
            <span className="sm:hidden">台幣</span>
            <input
              className="w-full rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-right text-sm text-white outline-none focus:border-sky-500"
              type={hideAmounts ? 'password' : 'number'}
              value={twd}
              onChange={(event) => updateCell(item, 'TWD', event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-[11px] text-slate-500 sm:block">
            <span className="sm:hidden">美金</span>
            <input
              className="w-full rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-right text-sm text-white outline-none focus:border-sky-500"
              type={hideAmounts ? 'password' : 'number'}
              value={usd}
              onChange={(event) => updateCell(item, 'USD', event.target.value)}
            />
          </label>
        </div>
        {rowStatus ? (
          <div className={`text-right text-xs sm:col-span-3 ${rowStatus === 'error' ? 'text-rose-300' : 'text-slate-500'}`}>
            {rowStatus === 'editing' ? '編輯中' : rowStatus === 'pending' ? '等待儲存' : rowStatus === 'saving' ? '儲存中' : '儲存失敗'}
          </div>
        ) : null}
      </div>
    )
  }

  if ((manual.loading && !manual.data) || (summary.loading && !summary.data)) {
    return (
      <div className="grid gap-5">
        <header>
          <h1 className="text-2xl font-semibold">現金</h1>
          <p className="mt-1 text-sm text-slate-400">正在整理各帳戶資料</p>
        </header>
        <LoadingBlock label="正在讀取現金資料" />
      </div>
    )
  }
  if (manual.error && !manual.data) return <ErrorBlock error={manual.error} />
  if (summary.error && !summary.data) return <ErrorBlock error={summary.error} />

  return (
    <div className="grid gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">現金</h1>
          <p className="mt-1 text-sm text-slate-400">USD/TWD {Number(usdRate || 0).toFixed(2)}</p>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-[1.4fr_1fr_1fr]">
        <div className="col-span-2 rounded-md border border-line bg-surface p-4 sm:col-span-1 sm:p-5">
          <div className="text-sm text-slate-400">現金總金額</div>
          <div className="mt-2 text-3xl font-semibold text-white">{hideAmounts ? maskAmount(money(totals.total)) : money(totals.total)}</div>
        </div>
        <SummaryCard label="台幣" value={money(totals.twd)} />
        <SummaryCard label="美金" value={money(totals.usd, 'USD')} />
      </section>

      <AccountInvestedPanel values={manual.data?.values || []} onSaved={refreshMoneyNow} />
      <CapitalMovementPanel bankNames={bankNames} positiveBankNames={positiveBankNames} onSaved={refreshMoneyNow} />

      <section>
        <div className="scrollbar-hide flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3 lg:hidden">
          <div className="w-[calc(100%-2rem)] flex-none snap-start">
            <ChartPanel
              title="現金帳戶分布"
              data={sortedGrouped
                .map((item) => {
                  const twd = Number(cellValue(item, 'TWD') || 0)
                  const usd = Number(cellValue(item, 'USD') || 0)
                  return { name: item.name, value: twd + usd * usdRate }
                })
                .filter((item) => item.value > 0)}
            />
          </div>
          <div className="w-[calc(100%-2rem)] flex-none snap-start">
            <ChartPanel
              title="幣別分布"
              data={[
                { name: '台幣', value: totals.twd },
                { name: '美金', value: totals.usd * usdRate },
              ].filter((item) => item.value > 0)}
            />
          </div>
          <div className="w-8 flex-none" aria-hidden="true" />
        </div>
        <p className="mb-1 text-center text-xs text-slate-600 lg:hidden">← 左右滑動查看圖表 →</p>

        <div className="hidden gap-5 lg:grid lg:grid-cols-[1fr_1fr]">
          <ChartPanel
            title="現金帳戶分布"
            data={sortedGrouped
              .map((item) => {
                const twd = Number(cellValue(item, 'TWD') || 0)
                const usd = Number(cellValue(item, 'USD') || 0)
                return { name: item.name, value: twd + usd * usdRate }
              })
              .filter((item) => item.value > 0)}
          />
          <ChartPanel
            title="幣別分布"
            data={[
              { name: '台幣', value: totals.twd },
              { name: '美金', value: totals.usd * usdRate },
            ].filter((item) => item.value > 0)}
          />
        </div>
      </section>

      <section className="overflow-hidden rounded-md border border-line bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-panel px-4 py-3">
          <div className="text-sm font-medium text-slate-200">帳戶</div>
          <button
            type="button"
            disabled={selectedRows.size === 0}
            onClick={resetSelectedAccounts}
            className="rounded-md border border-rose-500/70 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            歸零選取帳戶
          </button>
        </div>
        <div className="hidden grid-cols-[minmax(10rem,1fr)_7rem_7rem] gap-3 border-b border-line bg-panel/70 px-4 py-2 text-xs text-slate-400 sm:grid">
          <div>帳戶</div>
          <div className="text-right">台幣</div>
          <div className="text-right">美金</div>
        </div>
        <div className="divide-y divide-line">
          {activeGrouped.map(renderCashRow)}
          {zeroGrouped.length ? (
            <div>
              <button
                type="button"
                onClick={() => setZeroRowsOpen((open) => !open)}
                className="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-slate-300 transition hover:bg-panel/70 hover:text-white"
              >
                <span>0 元帳戶</span>
                <span className="text-xs text-slate-500">{zeroRowsOpen ? '收合' : `展開 ${zeroGrouped.length} 個`}</span>
              </button>
              {zeroRowsOpen ? <div className="divide-y divide-line border-t border-line">{zeroGrouped.map(renderCashRow)}</div> : null}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}
