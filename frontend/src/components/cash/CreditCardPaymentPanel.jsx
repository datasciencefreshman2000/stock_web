import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { usePersistentState } from '../../hooks/usePersistentState'
import { saveQueue, useAllSaves } from '../../hooks/useSaveQueue'
import { usePrivacy } from '../../context/PrivacyContext'
import { taipeiDate } from '../../utils/dates'
import { creditPaymentState } from '../../utils/creditPayments'
import MobileNumericInput from './MobileNumericInput'

const initial = () => ({ currency: 'TWD', source_id: '', mode: 'all', amount: '',
  date: taipeiDate(), note: '', operation_id: crypto.randomUUID() })

export default function CreditCardPaymentPanel({ rows, hasCorrections, openSignal }) {
  const { hideAmounts } = usePrivacy()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = usePersistentState('credit-card-payment', initial)
  const [message, setMessage] = useState('')
  const jobs = useAllSaves()
  const panel = useRef(null)
  const sourceSelect = useRef(null)
  const state = creditPaymentState(rows, draft)
  const blocked = hasCorrections ? '請先儲存或取消現金餘額校正，再記錄繳款。'
    : jobs.length ? '請先等候其他帳務儲存完成，或處理上方尚未確認的操作。' : ''
  const show = value => hideAmounts ? '••••' : new Intl.NumberFormat('zh-TW', {
    style: 'currency', currency: draft.currency,
    minimumFractionDigits: draft.currency === 'USD' ? 2 : 0, maximumFractionDigits: 2,
  }).format(Number(value))
  useEffect(() => {
    if (!openSignal) return
    setOpen(true)
    panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [openSignal])
  useEffect(() => {
    if (open) sourceSelect.current?.focus({ preventScroll: true })
  }, [open])
  function update(key, value) {
    setMessage('')
    setDraft(current => ({ ...current, [key]: value, ...(key === 'currency' ? { source_id: '' } : {}), operation_id: crypto.randomUUID() }))
  }
  function submit(event) {
    event.preventDefault()
    if (blocked || state.error) return
    if (!draft.date || draft.date > taipeiDate()) { setMessage('請填寫今天或之前的實際繳款日期。'); return }
    saveQueue.enqueue('credit-payment', {
      operation_id: draft.operation_id, source_id: state.source.id,
      source_name: state.source.name, debt_id: state.debt.id, currency: draft.currency,
      amount: state.amount, repayment_mode: draft.mode, movement_date: draft.date, note: draft.note,
    }, `${state.source.name} 信用卡繳款`)
    setDraft(current => ({ ...initial(), currency: current.currency, source_id: current.source_id }))
    setMessage('繳款已送出；請查看上方儲存狀態與最新餘額。')
    setOpen(false)
  }
  return <section ref={panel} className="scroll-mt-4 overflow-hidden rounded-md border border-amber-500/40 bg-surface">
    <div className="flex flex-wrap items-center justify-between gap-3 bg-panel p-4">
      <div><h2 className="text-sm font-semibold text-white">信用卡欠錢</h2>
        <p className="mt-1 text-sm text-amber-200">{draft.currency} 待繳 {show(state.owing)}{state.debt && !state.owing ? ' · 已繳清' : ''}</p></div>
      <button type="button" aria-expanded={open} onClick={() => setOpen(value => !value)} className="rounded border border-amber-400/60 px-3 py-2 text-sm text-amber-100">{open ? '收合繳款' : '繳信用卡'}</button>
    </div>
    {message ? <p role="status" className="px-4 py-2 text-sm text-sky-200">{message}</p> : null}
    {open ? <form onSubmit={submit} className="grid gap-4 border-t border-line p-4">
      <p className="text-xs text-slate-400">記錄已在銀行完成的繳款，會扣現金並減少欠款。繳款不重複計入消費支出。</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-xs text-slate-400">繳款幣別<select value={draft.currency} onChange={e => update('currency', e.target.value)} className="rounded border border-line bg-panel p-2 text-sm text-white"><option>TWD</option><option>USD</option></select></label>
        <label className="grid gap-1 text-xs text-slate-400">付款帳戶<select ref={sourceSelect} value={draft.source_id} onChange={e => update('source_id', e.target.value)} className="rounded border border-line bg-panel p-2 text-sm text-white"><option value="">請選擇現金帳戶</option>{state.sources.map(row => <option key={row.id} value={row.id}>{row.name} · 可用 {show(row.amount)}</option>)}</select></label>
      </div>
      <fieldset className="grid gap-2"><legend className="mb-2 text-xs text-slate-400">繳款方式</legend><div className="flex flex-wrap gap-4">{[['all','全部繳清'],['partial','指定金額']].map(([value,label]) => <label key={value} className="flex items-center gap-2 text-sm"><input type="radio" name="credit-payment-mode" value={value} checked={draft.mode === value} onChange={() => update('mode', value)} />{label}</label>)}</div></fieldset>
      {draft.mode === 'partial' ? <div className="grid gap-1 text-xs text-slate-400">本次繳款金額<MobileNumericInput label="本次繳款金額" value={draft.amount} onChange={value => update('amount', value)} currency={draft.currency} masked={hideAmounts} allowZero={false} /></div> : <p className="text-sm">本次繳款：{show(state.amount)}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-xs text-slate-400">實際繳款日期<input type="date" required max={taipeiDate()} value={draft.date} onChange={e => update('date',e.target.value)} className="rounded border border-line bg-panel p-2 text-sm text-white" /></label>
        <label className="grid gap-1 text-xs text-slate-400">繳款備註<input maxLength={200} value={draft.note} onChange={e => update('note',e.target.value)} className="rounded border border-line bg-panel p-2 text-sm text-white" /></label>
      </div>
      {!state.error ? <div className="grid gap-2 rounded border border-line p-3 text-sm" aria-live="polite"><p>{state.source.name}：{show(state.available)} → {show(state.sourceAfter)}</p><p>信用卡剩餘欠款：{show(state.owing)} → {show(state.owingAfter)}</p></div> : null}
      {blocked || state.error ? <p role="alert" className="text-sm text-amber-200">{blocked || state.error}</p> : null}
      <div className="flex flex-wrap gap-3"><button disabled={Boolean(blocked || state.error)} className="rounded bg-sky-600 px-4 py-2 text-sm text-white disabled:opacity-40">確認記錄繳款</button><button type="button" onClick={() => setOpen(false)} className="rounded border border-line px-4 py-2 text-sm">取消</button><Link to="/cash/ledger" className="self-center text-sm text-sky-300 underline">查看繳款紀錄</Link></div>
    </form> : null}
  </section>
}
