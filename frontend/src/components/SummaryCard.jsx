import { maskAmount, usePrivacy } from '../context/PrivacyContext'

export default function SummaryCard({ label, value, accent }) {
  const { hideAmounts } = usePrivacy()
  const shownValue = hideAmounts ? maskAmount(value) : value

  return (
    <div className="min-w-0 rounded-md border border-line bg-surface p-3 sm:p-4">
      <div className="text-xs leading-tight text-slate-400 sm:text-sm">{label}</div>
      <div className={`mt-1.5 break-words text-xl font-semibold leading-tight sm:mt-2 sm:text-2xl ${accent || 'text-white'}`}>{shownValue}</div>
    </div>
  )
}
