import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import AssetPieChart from '../components/AssetPieChart'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useManual } from '../hooks/useManual'
import { useSummary } from '../hooks/useSummary'
import { money } from '../utils/format'

const BASE_ROWS = ['新光現金', '第一現金', '郵局現金', '國泰現金', '外面欠錢 (待收款)', '緊急現金', '公司欠錢 (待收款)', '信用卡欠錢', '身上現金']
const DEBOUNCE_MS = 800

function ChartPanel({ title, data }) {
  return (
    <section className="grid gap-3">
      <h2 className="text-sm font-medium text-slate-300">{title}</h2>
      <AssetPieChart data={data} />
    </section>
  )
}

export default function Cash() {
  const { hideAmounts } = usePrivacy()
  const manual = useManual()
  const summary = useSummary(0)
  const [drafts, setDrafts] = useState({})
  const [statuses, setStatuses] = useState({})
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
      .filter((row) => row.name !== '社團欠錢 (待收款)')
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
            account: '台股',
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

  async function addForeign() {
    const response = await api.createCash({ name: '新增外幣', account: '台股', category: '現金', currency: 'USD', amount: 0 })
    setDrafts((current) => ({ ...current, [response.cash.id]: response.cash }))
    manual.reload()
  }

  if (manual.loading || summary.loading) return <LoadingBlock label="正在讀取現金資料" />
  if (manual.error) return <ErrorBlock error={manual.error} />
  if (summary.error) return <ErrorBlock error={summary.error} />

  return (
    <div className="grid gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">現金</h1>
          <p className="mt-1 text-sm text-slate-400">USD/TWD {usdRate}</p>
        </div>
        <button type="button" onClick={addForeign} className="rounded-md border border-sky-500 bg-sky-500/15 px-4 py-2 text-sm font-medium text-sky-100">
          新增外幣
        </button>
      </header>

      <section className="grid gap-3 sm:grid-cols-[1.4fr_1fr_1fr]">
        <div className="rounded-md border border-line bg-surface p-5">
          <div className="text-sm text-slate-400">現金總金額</div>
          <div className="mt-2 text-3xl font-semibold text-white">{hideAmounts ? maskAmount(money(totals.total)) : money(totals.total)}</div>
        </div>
        <SummaryCard label="台幣" value={money(totals.twd)} />
        <SummaryCard label="美金" value={money(totals.usd, 'USD')} />
      </section>

      <section className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <ChartPanel
          title="各現金帳戶分布"
          data={grouped
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
      </section>

      <section className="overflow-hidden rounded-md border border-line bg-surface">
        <div className="grid grid-cols-[1.4fr_1fr_1fr_1fr] gap-3 border-b border-line bg-panel px-4 py-3 text-sm text-slate-300">
          <div>帳戶</div>
          <div className="text-right">台幣</div>
          <div className="text-right">美金</div>
          <div className="text-right">折合台幣</div>
        </div>
        <div className="divide-y divide-line">
          {grouped.map((item) => {
            const twd = cellValue(item, 'TWD')
            const usd = cellValue(item, 'USD')
            const total = Number(twd || 0) + Number(usd || 0) * usdRate
            const twdStatus = statuses[cellKey(item, 'TWD')]
            const usdStatus = statuses[cellKey(item, 'USD')]
            const rowStatus = [twdStatus, usdStatus].find((status) => ['saving', 'pending', 'editing', 'error'].includes(status))
            return (
              <div key={item.name} className="grid grid-cols-[1.4fr_1fr_1fr_1fr] gap-3 px-4 py-3">
                <div className="font-medium text-white">{item.name}</div>
                <input
                  className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={twd}
                  onChange={(e) => updateCell(item, 'TWD', e.target.value)}
                />
                <input
                  className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={usd}
                  onChange={(e) => updateCell(item, 'USD', e.target.value)}
                />
                <div className="text-right text-sm text-slate-300">
                  {hideAmounts ? maskAmount(money(total)) : money(total)}
                  {rowStatus ? (
                    <div className={`text-xs ${rowStatus === 'error' ? 'text-rose-300' : 'text-slate-500'}`}>
                      {rowStatus === 'editing' ? '編輯中' : rowStatus === 'pending' ? '等待儲存' : rowStatus === 'saving' ? '儲存中' : '儲存失敗'}
                    </div>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
