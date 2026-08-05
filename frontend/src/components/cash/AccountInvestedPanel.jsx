import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

import { api } from '../../api/client'
import { ACCOUNTS } from '../../constants'
import { usePrivacy } from '../../context/PrivacyContext'
import MobileNumericInput from './MobileNumericInput'

export default function AccountInvestedPanel({ values = [], onSaved }) {
  const { hideAmounts } = usePrivacy()
  const [drafts, setDrafts] = useState({})
  const [open, setOpen] = useState(false)
  const map = useMemo(() => Object.fromEntries(values.map((item) => [item.key, item.value])), [values])

  useEffect(() => {
    setDrafts(Object.fromEntries(ACCOUNTS.map((account) => [`invested_${account}`, map[`invested_${account}`] ?? 0])))
  }, [map])

  async function save(account) {
    const key = `invested_${account}`
    await api.updateManualValue(key, Number(drafts[key] || 0))
    await onSaved?.()
  }

  return (
    <section className="overflow-hidden rounded-md border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-2 bg-panel px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-medium">投資帳戶已投入金額</span>
        {open ? <ChevronUp size={17} className="text-slate-400" /> : <ChevronDown size={17} className="text-slate-400" />}
      </button>
      <div className={`${open ? 'grid' : 'hidden'} gap-2 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-4`}>
        {ACCOUNTS.map((account) => {
          const key = `invested_${account}`
          return (
            <div key={account} className="grid gap-1 text-xs text-slate-400">
              <span>{account}</span>
              <MobileNumericInput
                value={drafts[key] ?? ''}
                onChange={(value) => setDrafts((current) => ({ ...current, [key]: value }))}
                label={`${account}已投入金額`}
                currency={account === '台股' ? 'TWD' : 'USD'}
                masked={hideAmounts}
                onComplete={() => save(account)}
                onDesktopBlur={() => save(account)}
              />
            </div>
          )
        })}
      </div>
    </section>
  )
}
