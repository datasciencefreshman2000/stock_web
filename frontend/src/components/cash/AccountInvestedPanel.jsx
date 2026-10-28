import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { ACCOUNTS, ACCOUNT_CURRENCY } from '../../constants'
import { usePrivacy } from '../../context/PrivacyContext'
import { usePersistentState } from '../../hooks/usePersistentState'
import { saveQueue } from '../../hooks/useSaveQueue'
import MobileNumericInput from './MobileNumericInput'

export default function AccountInvestedPanel({ values = [] }) {
  const { hideAmounts } = usePrivacy()
  const [drafts, setDrafts] = usePersistentState('net-capital', {})
  const [open, setOpen] = useState(false)
  const map = useMemo(() => Object.fromEntries(values.map(row => [row.key, row])), [values])
  useEffect(() => {
    setDrafts(current => Object.fromEntries(Object.entries(current).filter(([key, draft]) => Number(map[key]?.value) !== Number(draft.value))))
  }, [map])
  function save(key) {
    const draft = drafts[key]
    if (!draft || !Number.isFinite(Number(draft.value)) || draft.value === '' || draft.value === '-') return false
    saveQueue.enqueue('value', { ...draft, key, value: Number(draft.value), reason: '投資帳戶淨入金校正' }, `${key.replace('invested_', '')} 淨入金校正`)
    return true
  }
  return <section className="overflow-hidden rounded-md border border-line bg-surface">
    <button type="button" onClick={() => setOpen(value => !value)} className="flex w-full items-center justify-between bg-panel px-4 py-3 text-left" aria-expanded={open}>
      <span className="text-sm font-medium">投資帳戶淨入金／期初設定</span>{open ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
    </button>
    {open ? <div className="border-t border-line p-3">
      <p className="mb-3 text-xs text-slate-400">淨入金＝累計匯入減匯出；可用現金由淨入金與買賣收付計算。這裡只用於期初設定或校正，會保留調整紀錄。</p>
      <div className="grid gap-3 sm:grid-cols-3">{ACCOUNTS.map(account => {
        const key = `invested_${account}`, original = map[key]
        return <div key={key} className="grid gap-2 text-xs text-slate-300"><span>{account}</span>
          <MobileNumericInput value={drafts[key]?.value ?? original?.value ?? 0} onChange={value => setDrafts(current => ({ ...current, [key]: { expected_updated_at: original?.updated_at, ...current[key], value, operation_id: crypto.randomUUID() } }))}
            label={`${account}淨入金`} currency={ACCOUNT_CURRENCY[account]} masked={hideAmounts} allowNegative onComplete={() => save(key)} primaryLabel="儲存校正" />
          <button type="button" disabled={!drafts[key]} onClick={() => save(key)} className="rounded border border-sky-500 px-3 py-2 text-sky-100 disabled:opacity-40">儲存校正</button>
        </div>
      })}</div>
    </div> : null}
  </section>
}
