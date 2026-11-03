import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money } from '../utils/format'

export default function SummaryCard({ label, value, accent, countTo = null, currency = 'TWD', compact = false, hero = false }) {
  const { hideAmounts } = usePrivacy()
  const shouldCount = countTo !== null && countTo !== undefined && !Number.isNaN(Number(countTo))
  // Show the committed figure immediately; refreshes must not animate assets
  // from zero or spend 1.4 seconds rerendering each summary card on phones.
  const rawValue = shouldCount ? money(countTo, currency) : value
  const shownValue = hideAmounts ? maskAmount(rawValue) : rawValue

  return (
    <div
      className={`soft-pop min-w-0 rounded-md border transition duration-150 hover:-translate-y-0.5 hover:border-sky-500/60 ${
        hero
          ? 'summary-hero-card grid min-h-[8.75rem] place-items-center border-sky-500/50 bg-panel p-5 text-center shadow-sm shadow-sky-950/30 sm:min-h-[9.5rem] lg:min-h-[10.5rem]'
          : `border-line bg-surface ${compact ? 'p-2.5 sm:p-4' : 'p-3 sm:p-4'}`
      }`}
    >
      <div>
        <div className={`${hero ? 'text-sm text-slate-300' : 'text-xs leading-tight text-slate-400 sm:text-sm'}`}>{label}</div>
        <div
          className={`${
            hero ? 'mt-2 text-3xl sm:text-4xl lg:text-5xl' : compact ? 'mt-1 text-lg sm:mt-2 sm:text-2xl' : 'mt-1.5 text-xl sm:mt-2 sm:text-2xl'
          } break-words font-semibold leading-tight tabular-nums ${accent || 'text-white'}`}
        >
          {shownValue}
        </div>
      </div>
    </div>
  )
}
