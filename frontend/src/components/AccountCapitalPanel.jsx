import { useEffect, useState } from 'react'

import { api } from '../api/client'
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
    await api.updateManualValue(key, Number(invested || 0))
    setSaving(false)
    onSaved?.()
  }

  return (
    <label className="grid gap-2 rounded-md border border-line bg-surface p-3 text-sm text-slate-300">
      <span>已投入金額</span>
      <input
        className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-white outline-none focus:border-sky-500"
        type={hideAmounts ? 'password' : 'number'}
        value={invested}
        onChange={(event) => setInvested(event.target.value)}
        onBlur={save}
      />
      {saving ? <span className="text-xs text-slate-500">儲存中</span> : null}
    </label>
  )
}
