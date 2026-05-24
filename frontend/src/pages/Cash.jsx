import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react'

import { api } from '../api/client'
import AssetPieChart from '../components/AssetPieChart'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { ACCOUNTS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useManual } from '../hooks/useManual'
import { useSummary } from '../hooks/useSummary'
import { money } from '../utils/format'

const BASE_ROWS = ['新光現金', '第一現金', '郵局現金', '國泰現金', '外面欠錢 (待收款)', '社團欠錢 (待收款)', '緊急現金', '公司欠錢 (待收款)', '信用卡欠錢', '身上現金']
const BANK_ROWS = ['新光現金', '第一現金', '郵局現金', '國泰現金']
const INCOME_SOURCES = ['宇統資訊', '陽明高中', '實驗小學', '接案']
const OTHER_TYPES = ['外面欠錢 (待收款)', '社團欠錢', '公司欠錢', '外面欠錢 (待還款)', '緊急現金']
const DEBOUNCE_MS = 800
const today = new Date().toISOString().slice(0, 10)

function ChartPanel({ title, data }) {
  return <AssetPieChart title={title} data={data} />
}

function AccountInvestedPanel({ values = [], onSaved }) {
  const [drafts, setDrafts] = useState({})
  const [open, setOpen] = useState(false)
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
      <div className="flex items-center justify-between gap-2 border-b border-line bg-panel px-4 py-3">
        <div className="text-sm font-medium">投資帳戶已投入金額</div>
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="rounded-md border border-line p-1.5 text-slate-400 sm:hidden"
          title={open ? '收起' : '展開'}
          aria-label={open ? '收起投資帳戶已投入金額' : '展開投資帳戶已投入金額'}
        >
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>
      <div className={`${open ? 'grid' : 'hidden'} gap-2 p-3 sm:grid sm:grid-cols-2 lg:grid-cols-4`}>
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

function IncomeSourcePicker({ value, onChange }) {
  const [sources, setSources] = useState(INCOME_SOURCES.map((label) => ({ id: null, label })))
  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState('')
  const [editing, setEditing] = useState(false)

  async function loadSources() {
    try {
      const response = await api.getCapitalMovementOptions('income_source')
      const loaded = response.options || []
      if (loaded.length > 0) {
        setSources(loaded)
        if (!loaded.some((item) => item.label === value)) onChange(loaded[0].label)
      }
    } catch {
      setMessage('收入來源資料表尚未建立')
    }
  }

  useEffect(() => {
    loadSources()
  }, [])

  async function addSource() {
    const label = draft.trim()
    if (!label) return
    try {
      const response = await api.createCapitalMovementOption({ category: 'income_source', label })
      const option = response.option
      setSources((current) => [...current.filter((item) => item.label !== label), option].sort((a, b) => a.label.localeCompare(b.label, 'zh-Hant')))
      setDraft('')
      onChange(label)
      setMessage('')
    } catch (err) {
      setMessage(err.message || '新增收入來源失敗')
    }
  }

  async function removeSource(option) {
    if (!option.id) return
    try {
      await api.deleteCapitalMovementOption(option.id)
      const next = sources.filter((item) => item.id !== option.id)
      setSources(next)
      if (option.label === value) onChange(next[0]?.label || '')
      setMessage('')
    } catch (err) {
      setMessage(err.message || '刪除收入來源失敗')
    }
  }

  return (
    <div className="grid gap-2 sm:col-span-2 lg:col-span-2">
      <div className="grid grid-cols-[1fr_auto] items-end gap-2">
        <label className="grid gap-1 text-xs text-slate-400">
          收入來源
          <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={value} onChange={(event) => onChange(event.target.value)}>
            {sources.map((item) => <option key={item.id || item.label}>{item.label}</option>)}
          </select>
        </label>
        <button
          type="button"
          onClick={() => setEditing((current) => !current)}
          className="rounded-md border border-line bg-panel px-3 py-2 text-xs font-medium text-slate-200"
        >
          更動
        </button>
      </div>
      {editing ? (
        <div className="grid gap-2 rounded-md border border-line bg-panel/50 p-2">
          <div className="flex gap-2">
            <input
              className="min-w-0 flex-1 rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
              placeholder="新增收入來源"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="button" className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-2 text-xs font-medium text-sky-100" onClick={addSource}>
              增加
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {sources.map((item) => (
              <button
                key={item.id || item.label}
                type="button"
                disabled={!item.id}
                onClick={() => removeSource(item)}
                className="rounded-full border border-line bg-[#0b1020] px-2 py-1 text-xs text-slate-300 disabled:opacity-50"
                title={item.id ? '刪除收入來源' : '預設來源需要建立資料表後才能刪除'}
              >
                {item.label} {item.id ? '×' : ''}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {message ? <div className="text-xs text-amber-300">{message}</div> : null}
    </div>
  )
}

function CapitalMovementPanel({ bankNames, positiveBankNames, onSaved }) {
  const [mode, setMode] = useState('income')
  const [exchange, setExchange] = useState(false)
  const [form, setForm] = useState({
    movement_date: today,
    income_source: INCOME_SOURCES[0],
    other_type: OTHER_TYPES[0],
    from_bucket: bankNames[0] || '',
    to_bucket: bankNames[0] || ACCOUNTS[0],
    amount: '',
    currency: 'TWD',
    to_amount: '',
    to_currency: 'USD',
    note: '',
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const incomeDestinations = [...bankNames, ACCOUNTS[0]]
  const transferBuckets = [...bankNames, ACCOUNTS[0], ACCOUNTS[1]]
  const expenseSources = positiveBankNames

  useEffect(() => {
    const fromOptions = mode === 'expense' ? expenseSources : transferBuckets
    const toOptions = mode === 'income' ? incomeDestinations : transferBuckets
    setForm((current) => {
      const next = { ...current }
      if ((mode === 'transfer' || mode === 'expense') && !fromOptions.includes(next.from_bucket)) {
        next.from_bucket = fromOptions[0] || ''
      }
      if ((mode === 'income' || mode === 'transfer') && !toOptions.includes(next.to_bucket)) {
        next.to_bucket = toOptions[0] || ''
      }
      return next.from_bucket === current.from_bucket && next.to_bucket === current.to_bucket ? current : next
    })
    if (mode !== 'transfer') setExchange(false)
  }, [mode, bankNames, positiveBankNames])

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
        to_amount: exchange && mode === 'transfer' ? Number(form.to_amount || 0) : null,
        to_currency: exchange && mode === 'transfer' ? form.to_currency : null,
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
          <IncomeSourcePicker value={form.income_source} onChange={(value) => update('income_source', value)} />
        ) : null}

        {mode === 'transfer' || mode === 'expense' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            從哪裡
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.from_bucket} onChange={(event) => update('from_bucket', event.target.value)}>
              {(mode === 'expense' ? expenseSources : transferBuckets).map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        ) : null}

        {mode === 'income' || mode === 'transfer' ? (
          <label className="grid gap-1 text-xs text-slate-400">
            放到哪裡
            <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.to_bucket} onChange={(event) => update('to_bucket', event.target.value)}>
              {(mode === 'income' ? incomeDestinations : transferBuckets).map((item) => <option key={item}>{item}</option>)}
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
        <label className="grid max-w-20 gap-1 text-[11px] text-slate-500">
          幣別
          <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.currency} onChange={(event) => update('currency', event.target.value)}>
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </label>
        {mode === 'transfer' ? (
          <label className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-300">
            <input className="min-h-0" type="checkbox" checked={exchange} onChange={(event) => setExchange(event.target.checked)} />
            換匯
          </label>
        ) : null}
        {mode === 'transfer' && exchange ? (
          <>
            <label className="grid gap-1 text-xs text-slate-400">
              換成金額
              <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white" type="number" min="0" step="0.01" value={form.to_amount} onChange={(event) => update('to_amount', event.target.value)} required />
            </label>
            <label className="grid max-w-20 gap-1 text-[11px] text-slate-500">
              換成
              <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.to_currency} onChange={(event) => update('to_currency', event.target.value)}>
                <option value="USD">USD</option>
                <option value="TWD">TWD</option>
              </select>
            </label>
          </>
        ) : null}
        <button
          className={`flex items-center justify-center gap-2 rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-white transition active:scale-[0.99] disabled:opacity-70 lg:col-span-1 ${saving ? 'submit-pulse' : 'hover:bg-sky-400'}`}
          disabled={saving}
        >
          {saving ? <Loader2 size={15} className="animate-spin" /> : null}
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
  const [selectedRows, setSelectedRows] = useState(new Set())
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
          <p className="mt-1 text-sm text-slate-400">USD/TWD {usdRate}</p>
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

      <AccountInvestedPanel values={manual.data?.values || []} onSaved={() => { manual.reload(); summary.reload() }} />
      <CapitalMovementPanel bankNames={bankNames} positiveBankNames={positiveBankNames} onSaved={() => { manual.reload(); summary.reload() }} />

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
          {sortedGrouped.map((item) => {
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
          })}
        </div>
      </section>
    </div>
  )
}
