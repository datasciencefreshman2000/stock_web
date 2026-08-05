import { useEffect, useState } from 'react'

import { api } from '../api/client'
import MobileNumericInput from './cash/MobileNumericInput'
import { usePrivacy } from '../context/PrivacyContext'

export default function AccountCapitalPanel({ account, manualValues = [], onSaved }) {
  const { hideAmounts } = usePrivacy()
  const key = `invested_${account}`
  const valueMap = Object.fromEntries(manualValues.map((item) => [item.key, item.value]))
  const [invested, setInvested] = useState(valueMap[key] ?? '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setInvested(valueMap[key] ?? '')
  }, [key, valueMap[key]])

  async function save() {
    setSaving(true)
    try {
      await api.updateManualValue(key, Number(invested || 0))
      await onSaved?.()
    } finally {
      setSaving(false)
    }
  }

  return (
    <label className="grid gap-2 rounded-md border border-line bg-surface p-3 text-sm text-slate-300">
      <span>已投入金額</span>
      <MobileNumericInput
        value={invested}
        onChange={setInvested}
        label={`${account}已投入金額`}
        currency={account === '台股' ? 'TWD' : 'USD'}
        masked={hideAmounts}
        onComplete={save}
        onDesktopBlur={save}
        busy={saving}
      />
      {saving ? <span className="text-xs text-slate-500">儲存中</span> : null}
    </label>
  )
}
