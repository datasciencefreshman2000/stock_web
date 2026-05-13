import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import AssetPieChart from '../components/AssetPieChart'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { ACCOUNTS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useManual } from '../hooks/useManual'
import { useSummary } from '../hooks/useSummary'
import { money } from '../utils/format'

const BASE_ROWS = ['新光現金', '第一現金', '郵局現金', '國泰現金', '外面欠錢 (待收款)', '緊急現金', '公司欠錢 (待收款)', '信用卡欠錢', '身上現金']
const INCOME_SOURCES = ['宇統資訊', '陽明高中', '實驗小學', '接案']
const OTHER_TYPES = ['外面欠錢 (待收款)', '社團欠錢', '公司欠錢', '外面欠錢 (待還款)', '緊急現金']
const DEBOUNCE_MS = 800
const today = new Date().toISOString().slice(0, 10)

function ChartPanel({ title, data }) {
  return <AssetPieChart title={title} data={data} />
}

function AccountInvestedPanel({ values = [], onSaved }) {
  const [drafts, setDrafts] = useState({})
  const map = useMemo(() => Object.fromEntries(values.map((item) => [item.key, item.value])), [values])

  useEffect(() => {
    setDrafts(Object.fromEntries(ACCOUNTS.map((account) => [`invested_${account}`, map[`invested_${account}`] ?? 0])))
  }, [map])

  async function save(account) {
    const key = `invested_${account}`
    await api.updateManualValue(key, Number(drafts[key] || 0))
    onSaved?.()
  }

  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">投資帳戶已投入金額</div>
      <div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-4">
        {ACCOUNTS.map((account) => {
          const key = `invested_${account}`
          return (
            <label key={account} className="grid gap-1 text-xs text-slate-400">
              {account}
              <input
                className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500"
                type="number"
                value={drafts[key] ?? ''}
                onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))}
                onBlur={() => save(account)}
              />
            </label>
          )
        })}
      </div>
    </section>
  )
}

function CapitalMovementPanel({ cashNames, onSaved }) {
  const [mode, setMode] = useState('income')
  const [form, setForm] = useState({
    movement_date: today,
    income_source: INCOME_SOURCES[0],
    other_type: OTHER_TYPES[0],
    from_bucket: cashNames[0] || '',
    to_bucket: cashNames[0] || ACCOUNTS[0],
    amount: '',
    currency: 'TWD',
    note: '',
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const buckets = [...cashNames, ...ACCOUNTS]

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      let payload = {
        movement_date: form.movement_date,
        from_bucket: null,
        to_bucket: form.to_bucket,
        amount: Number(form.amount || 0),
        currency: form.currency,
        note: form.note,
      }

      if (mode === 'income') {
        payload = { ...payload, from_bucket: null, to_bucket: form.to_bucket, note: [form.income_source, form.note].filter(Boolean).join(' - ') }
      } else if (mode === 'transfer') {
        payload = { ...payload, from_bucket: form.from_bucket, to_bucket: form.to_bucket }
      } else if (mode === 'expense') {
        payload = { ...payload, from_bucket: form.from_bucket, to_bucket: '支出' }
      } else {
        payload = { ...payload, from_bucket: null, to_bucket: form.other_type, note: [form.other_type, form.note].filter(Boolean).join(' - ') }
      }

      await api.createCapitalMovement(payload)
      setMessage('已記錄資金異動。')
      setForm((current) => ({ ...current, amount: '', note: '' }))
      onSaved?.()
    } catch (err) {
      setMessage(err.message || '資金異動儲存失敗')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line bg-panel px-4 py-3 text-sm font-medium">資金異動</div>
      <div className="grid grid-cols-4 gap-2 p-3">
        {[
          ['income', '收入'],
          ['transfer', '調動'],
          ['expense', '支出'],
          ['other', '其他'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setMode(key)}
            className={`rounded-md border px-2 py-2 text-sm ${mode === key ? 'border-sky-400 bg-sky-500/15 text-white' : 'border-line bg-panel text-slate-300'}`}
          >
            {label}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="grid gap-3 px-3 pb-3 sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
        <label className="grid gap-1 text-xs text-slate-400">
          日期
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" type="date" value={form.movement_date} onChange={(event) => update('movement_date', event.target.value)} />
        </label>

        {mode === 'income' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            收入來源
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.income_source} onChange={(event) => update('income_source', event.target.value)}>
              {INCOME_SOURCES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        {mode === 'transfer' || mode === 'expense' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            從哪裡
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.from_bucket} onChange={(event) => update('from_bucket', event.target.value)}>
              {buckets.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        {mode === 'income' || mode === 'transfer' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            放到哪裡
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.to_bucket} onChange={(event) => update('to_bucket', event.target.value)}>
              {buckets.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        {mode === 'other' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            類型
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.other_type} onChange={(event) => update('other_type', event.target.value)}>
              {OTHER_TYPES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        <label className="grid gap-1 text-xs text-slate-400">
          金額
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white" type="number" min="0" step="0.01" value={form.amount} onChange={(event) => update('amount', event.target.value)} required />
        </label>
        <label className="grid gap-1 text-xs text-slate-400">
          幣別
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.currency} onChange={(event) => update('currency', event.target.value)}>
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </label>
        <button className="rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-white disabled:opacity-60" disabled={saving}>
          {saving ? '儲存中' : '新增異動'}
        </button>
        <label className="grid gap-1 text-xs text-slate-400 sm:col-span-2 lg:col-span-5">
          備註
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.note} onChange={(event) => update('note', event.target.value)} />
        </label>
        {message ? <div className="text-xs text-slate-400 lg:col-span-6">{message}</div> : null}
      </form>
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
      .filter((row) => row.name !== '社團欠錢（待收）')
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
  const cashNames = grouped.map((item) => item.name)

  async function addForeign() {
    const response = await api.createCash({ name: '新增外幣', account: '', category: '現金', currency: 'USD', amount: 0 })
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

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-[1.4fr_1fr_1fr]">
        <div className="col-span-2 rounded-md border border-line bg-surface p-4 sm:col-span-1 sm:p-5">
          <div className="text-sm text-slate-400">現金總金額</div>
          <div className="mt-2 text-3xl font-semibold text-white">{hideAmounts ? maskAmount(money(totals.total)) : money(totals.total)}</div>
        </div>
        <SummaryCard label="台幣" value={money(totals.twd)} />
        <SummaryCard label="美金" value={money(totals.usd, 'USD')} />
      </section>

      <AccountInvestedPanel values={manual.data?.values || []} onSaved={() => { manual.reload(); summary.reload() }} />
      <CapitalMovementPanel cashNames={cashNames} onSaved={() => { manual.reload(); summary.reload() }} />

      <section className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <ChartPanel
          title="現金帳戶分布"
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
        <div className="hidden grid-cols-[1.4fr_1fr_1fr_1fr] gap-3 border-b border-line bg-panel px-4 py-3 text-sm text-slate-300 sm:grid">
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
              <div key={item.name} className="grid gap-2 px-3 py-3 sm:grid-cols-[1.4fr_1fr_1fr_1fr] sm:px-4">
                <div className="font-medium text-white">{item.name}</div>
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-1.5 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={twd}
                  onChange={(event) => updateCell(item, 'TWD', event.target.value)}
                />
                <input
                  className="w-full rounded-md border border-line bg-[#0b1020] px-3 py-1.5 text-right text-sm text-white outline-none focus:border-sky-500"
                  type={hideAmounts ? 'password' : 'number'}
                  value={usd}
                  onChange={(event) => updateCell(item, 'USD', event.target.value)}
                />
                <div className="rounded-md bg-panel/60 px-3 py-2 text-right text-sm text-slate-300 sm:bg-transparent sm:px-0 sm:py-0">
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
