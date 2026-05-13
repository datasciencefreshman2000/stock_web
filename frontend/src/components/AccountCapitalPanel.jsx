import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { usePrivacy } from '../context/PrivacyContext'
import AssetPieChart from './AssetPieChart'

export default function AccountCapitalPanel({ account, manualValues = [], cost = 0, realizedPnl = 0, onSaved }) {
  const { hideAmounts } = usePrivacy()
  const key = `invested_${account}`
  const valueMap = Object.fromEntries(manualValues.map((item) => [item.key, item.value]))
  const [invested, setInvested] = useState(valueMap[key] ?? '')
  const [saving, setSaving] = useState(false)
  const inferredCash = Number(invested || 0) - Number(cost || 0) + Number(realizedPnl || 0)

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
    <section className="grid gap-3 sm:gap-5 lg:grid-cols-[0.8fr_1.2fr]">
      <div className="grid content-start gap-3">
        <label className="grid gap-2 rounded-md border border-line bg-surface p-3 text-sm text-slate-300 sm:p-4">
          已投入金額
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-white outline-none focus:border-sky-500"
            type={hideAmounts ? 'password' : 'number'}
            value={invested}
            onChange={(event) => setInvested(event.target.value)}
            onBlur={save}
          />
          {saving ? <span className="text-xs text-slate-500">儲存中</span> : null}
        </label>
      </div>
      <AssetPieChart
        title="現金與已投入金額分布"
        data={[
          { name: '已投入持股成本', value: Math.max(Number(cost || 0), 0) },
          { name: '推算現金', value: Math.max(inferredCash, 0) },
        ]}
      />
    </section>
  )
}
