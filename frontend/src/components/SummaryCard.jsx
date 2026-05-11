import { maskAmount, usePrivacy } from '../context/PrivacyContext'

export default function SummaryCard({ label, value, accent }) {
  const { hideAmounts } = usePrivacy()
  const shownValue = hideAmounts ? maskAmount(value) : value

  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${accent || 'text-white'}`}>{shownValue}</div>
    </div>
  )
}
