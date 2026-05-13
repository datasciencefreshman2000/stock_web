import { useEffect, useState } from 'react'

import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money } from '../utils/format'

export default function SummaryCard({ label, value, accent, countTo = null, currency = 'TWD' }) {
  const { hideAmounts } = usePrivacy()
  const [displayValue, setDisplayValue] = useState(0)
  const shouldCount = countTo !== null && countTo !== undefined && !Number.isNaN(Number(countTo))

  useEffect(() => {
    if (!shouldCount) return
    const target = Number(countTo)
    const startedAt = performance.now()
    const duration = 1400
    let frameId

    function tick(now) {
      const progress = Math.min((now - startedAt) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayValue(target * eased)
      if (progress < 1) frameId = requestAnimationFrame(tick)
    }

    setDisplayValue(0)
    frameId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameId)
  }, [countTo, shouldCount])

  const rawValue = shouldCount ? money(displayValue, currency) : value
  const shownValue = hideAmounts ? maskAmount(rawValue) : rawValue

  return (
    <div className="soft-pop min-w-0 rounded-md border border-line bg-surface p-3 transition duration-150 hover:-translate-y-0.5 hover:border-sky-500/60 sm:p-4">
      <div className="text-xs leading-tight text-slate-400 sm:text-sm">{label}</div>
      <div className={`mt-1.5 break-words text-xl font-semibold leading-tight tabular-nums sm:mt-2 sm:text-2xl ${accent || 'text-white'}`}>{shownValue}</div>
    </div>
  )
}
