import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, PenLine, ReceiptText } from 'lucide-react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import { saveQueue, useAllSaves } from '../hooks/useSaveQueue'
import { usePersistentState } from '../hooks/usePersistentState'
import AccountInvestedPanel from '../components/cash/AccountInvestedPanel'
import CashBalanceChart from '../components/cash/CashBalanceChart'
import CapitalMovementPanel from '../components/cash/CapitalMovementPanel'
import MobileNumericInput from '../components/cash/MobileNumericInput'
import { BANK_ROWS, BASE_ROWS, DEBOUNCE_MS } from '../components/cash/constants'
import { ErrorBlock, LoadingBlock } from '../components/StateBlock'
import SummaryCard from '../components/SummaryCard'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { useDeferredInvalidate, useInvalidateMoney, useManualQuery, useSummaryQuery } from '../hooks/queries'
import { money } from '../utils/format'

export default function Cash() {
  const { hideAmounts } = usePrivacy()
  const manualQuery = useManualQuery()
  const summaryQuery = useSummaryQuery()
  const invalidateMoney = useInvalidateMoney()
  // 連續記帳時不要每筆都等重算，停手 1.5 秒後才合併觸發一次
  const deferred = useDeferredInvalidate(1500)
  const [ledgerSignal, setLedgerSignal] = useState(0)

  // 保留舊有的 { data, error, loading } 形狀，下面的畫面程式碼不用改
  const manual = { data: manualQuery.data, error: manualQuery.error, loading: manualQuery.isLoading }
  const summary = { data: summaryQuery.data, error: summaryQuery.error, loading: summaryQuery.isLoading }
  const [drafts, setDrafts] = usePersistentState('cash-corrections', {})
  const saves = useAllSaves()
  const [statuses, setStatuses] = useState({})
  const [selectedRows, setSelectedRows] = useState(new Set())
  const [zeroRowsOpen, setZeroRowsOpen] = useState(false)
  const [summaryOpen, setSummaryOpen] = useState(true)
  const [accountsOpen, setAccountsOpen] = useState(false)


  useEffect(() => {
    if (!manual.data?.cash) return
    setStatuses({})
    setDrafts(current => Object.fromEntries(Object.entries(current).filter(([key, draft]) => {
      const row = manual.data.cash.find(row => row.id === key || (row.name === draft.name && row.currency === draft.currency))
      return !row || Number(row.amount) !== Number(draft.amount)
    })))
  }, [manual.data])

  const usdRate = summary.data?.usd_rate || 31.316
  const rows = manual.data?.cash || []
  const grouped = useMemo(() => {
    const map = new Map(BASE_ROWS.map((name) => [name, { name, TWD: null, USD: null }]))
    rows
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

  function updateCell(item, currency, rawValue) {
    const key = cellKey(item, currency)
    const original = item[currency]
    setDrafts(current => ({ ...current, [key]: {
      ...(current[key] || original || { name: item.name, currency }), amount: rawValue,
      expected_updated_at: current[key]?.expected_updated_at ?? original?.updated_at,
      operation_id: crypto.randomUUID(),
    } }))
    setStatus(key, 'editing')
  }

  function saveCorrections() {
    const entries = Object.entries(drafts)
    if (!entries.length) return
    if (entries.some(([, row]) => !Number.isFinite(Number(row.amount)) || ['-', '.', '-.'].includes(String(row.amount)))) {
      window.alert('請先完成金額輸入。'); return
    }
    for (const [key, row] of entries) {
      const existing = rows.find(item => item.id === key)
      saveQueue.enqueue(existing ? 'cash' : 'cash-create', { ...row, id: existing?.id,
        amount: Number(row.amount), currency: row.currency, reason: '現金頁餘額校正',
      }, `${row.name} ${row.currency} 餘額校正`)
      setStatus(key, 'saving')
    }
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
    if (!window.confirm(`將選取的 ${selectedRows.size} 個帳戶台幣與美金填為 0？按儲存校正後會保留調整紀錄。`)) return
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

  // 記帳存檔後只排程一次延遲失效，連續輸入時會自動合併
  function refreshMoneyNow() {
    deferred.schedule('movement')
  }

  function openLedgerEntry() {
    setLedgerSignal((n) => n + 1)
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
          <div className="grid gap-1 text-[11px] text-slate-500 sm:block">
            <span className="sm:hidden">台幣淨額</span>
            <MobileNumericInput
              value={twd}
              onChange={(value) => updateCell(item, 'TWD', value)}
              label={`${item.name}台幣金額`}
              subtitle={item.name}
              currency="TWD"
              allowNegative
              masked={hideAmounts}
            />
          </div>
          <div className="grid gap-1 text-[11px] text-slate-500 sm:block">
            <span className="sm:hidden">美金</span>
            <MobileNumericInput
              value={usd}
              onChange={(value) => updateCell(item, 'USD', value)}
              label={`${item.name}美金金額`}
              subtitle={item.name}
              currency="USD"
              allowNegative
              masked={hideAmounts}
            />
          </div>
        </div>
        {rowStatus ? (
          <div className={`text-right text-xs sm:col-span-3 ${rowStatus === 'error' ? 'text-rose-300' : 'text-slate-500'}`}>
            {rowStatus === 'editing' ? '未儲存校正' : '請查看上方儲存狀態'}
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
          <p className="mt-1 text-sm text-slate-400">USD/TWD {Number(usdRate || 0).toFixed(2)} · 修改餘額後請儲存校正</p>
        </div>
        <div className="grid w-full grid-cols-2 items-center gap-2 sm:flex sm:w-auto">
          {deferred.pending ? (
            <span className="col-span-2 text-right text-[11px] text-slate-500 sm:col-span-1">同步中…</span>
          ) : null}
          <button
            type="button"
            onClick={openLedgerEntry}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-emerald-400/70 bg-emerald-500/15 px-3 py-2 text-xs font-medium text-emerald-50 shadow-sm shadow-emerald-950/40 transition hover:border-emerald-300 hover:bg-emerald-500/25 active:scale-[0.97]"
          >
            <PenLine size={17} />
            記帳
          </button>
          <Link
            to="/cash/ledger"
            state={{ pageDirection: 1, navigationSource: 'cash-action' }}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-sky-500/60 bg-sky-500/10 px-3 py-2 text-xs font-medium text-sky-100 transition hover:bg-sky-500/20 active:scale-[0.97]"
          >
            <ReceiptText size={17} />
            記帳紀錄
          </Link>
        </div>
      </header>

      {Object.keys(drafts).length ? <div className="flex flex-wrap items-center gap-3 rounded border border-amber-500/40 p-3 text-sm">
        <span className="flex-1">有 {Object.keys(drafts).length} 個未儲存的餘額校正，草稿已保留。</span>
        <button type="button" onClick={saveCorrections} disabled={saves.some(job => job.state !== 'failed' && ['cash','cash-create'].includes(job.kind))} className="rounded bg-sky-600 px-3 py-2 disabled:opacity-50">儲存餘額校正</button>
        <button type="button" onClick={() => { if(window.confirm('放棄尚未送出的餘額校正？')) setDrafts({}) }} className="rounded border border-line px-3 py-2">取消草稿</button>
      </div> : null}
      <section className={`grid gap-3 ${summaryOpen ? 'sm:grid-cols-3' : ''}`}>
        <button
          type="button"
          onClick={() => setSummaryOpen((open) => !open)}
          className="soft-pop flex min-h-[7.5rem] w-full items-center justify-between rounded-md border border-sky-500/50 bg-panel p-4 text-left transition active:scale-[0.99]"
          aria-expanded={summaryOpen}
        >
          <span>
            <span className="block text-sm text-slate-300">台幣淨額</span>
            <span className="mt-2 block text-3xl font-semibold tabular-nums text-white">
              {hideAmounts ? maskAmount(money(totals.twd)) : money(totals.twd)}
            </span>
          </span>
          {summaryOpen ? <ChevronUp size={19} className="text-slate-400" /> : <ChevronDown size={19} className="text-slate-400" />}
        </button>
        {summaryOpen ? (
          <>
            <SummaryCard label="美金" value={money(totals.usd, 'USD')} />
            <SummaryCard label="現金總金額" value={money(totals.total)} accent="text-sky-200" />
          </>
        ) : null}
      </section>

      <p className="text-xs text-slate-400">淨額包含應收款與負債；應收款不等於可立即使用的現金。首次設定請先核對銀行餘額，再設定投資帳戶淨入金。</p>
      <CashBalanceChart
        data={[
          ...sortedGrouped
            .map((item) => ({ name: item.name, value: accountTotal(item) }))
            .filter((item) => Math.abs(item.value) > 0.000001),
          { name: '現金淨額', value: totals.total, isTotal: true },
        ]}
      />

      <CapitalMovementPanel
        bankNames={bankNames}
        positiveBankNames={positiveBankNames}
        usdRate={usdRate}
        onSaved={refreshMoneyNow}
        openSignal={ledgerSignal}
        openMode="expense"
      />
      <AccountInvestedPanel values={manual.data?.values || []} onSaved={refreshMoneyNow} />

      <section className="overflow-hidden rounded-md border border-line bg-surface">
        <div className="flex items-center gap-2 bg-panel px-4 py-3">
          <button
            type="button"
            onClick={() => setAccountsOpen((open) => !open)}
            className="flex min-h-0 min-w-0 flex-1 items-center justify-between gap-3 text-left"
            aria-expanded={accountsOpen}
          >
            <span className="text-sm font-medium text-slate-200">帳戶</span>
            {accountsOpen ? <ChevronUp size={17} className="text-slate-400" /> : <ChevronDown size={17} className="text-slate-400" />}
          </button>
          {accountsOpen ? (
            <button
              type="button"
              disabled={selectedRows.size === 0}
              onClick={resetSelectedAccounts}
              className="rounded-md border border-rose-500/70 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              歸零選取帳戶
            </button>
          ) : null}
        </div>
        {accountsOpen ? (
          <div className="border-t border-line">
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
          </div>
        ) : null}
      </section>
    </div>
  )
}
