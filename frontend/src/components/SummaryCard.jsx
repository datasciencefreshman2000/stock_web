import { useEffect, useState } from 'react'

import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money } from '../utils/format'

export default function SummaryCard({ label, value, accent, countTo = null, currency = 'TWD', compact = false, hero = false }) {
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
    <div
      className={`soft-pop min-w-0 rounded-md border transition duration-150 hover:-translate-y-0.5 hover:border-sky-500/60 ${
        hero
          ? 'summary-hero-card grid min-h-[8.75rem] place-items-center border-sky-500/50 bg-panel p-5 text-center shadow-sm shadow-sky-950/30'
          : `border-line bg-surface ${compact ? 'p-2.5 sm:p-4' : 'p-3 sm:p-4'}`
      }`}
    >
      <div>
        <div className={`${hero ? 'text-sm text-slate-300' : 'text-xs leading-tight text-slate-400 sm:text-sm'}`}>{label}</div>
        <div
          className={`${
            hero ? 'mt-2 text-3xl sm:text-2xl' : compact ? 'mt-1 text-lg sm:mt-2 sm:text-2xl' : 'mt-1.5 text-xl sm:mt-2 sm:text-2xl'
          } break-words font-semibold leading-tight tabular-nums ${accent || 'text-white'}`}
        >
          {shownValue}
        </div>
      </div>
    </div>
  )
}
