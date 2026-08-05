const MARKERS = [
  { cash: 10, line: 'w-0.5 bg-rose-500', label: 'text-rose-300' },
  { cash: 25, line: 'w-px bg-slate-300', label: 'text-slate-300' },
  { cash: 50, line: 'w-px bg-black', label: 'text-slate-400' },
]

export default function AllocationBar({ stockRatio, cashRatio }) {
  return (
    <div className="relative pt-4">
      {MARKERS.map((marker) => {
        const left = 100 - marker.cash
        return (
          <div key={marker.cash} className="pointer-events-none absolute inset-y-0 z-10" style={{ left: `${left}%` }}>
            <span className={`absolute top-0 -translate-x-1/2 whitespace-nowrap text-[9px] leading-none ${marker.label}`}>
              {marker.cash}%
            </span>
            <span className={`absolute bottom-0 top-3 -translate-x-1/2 ${marker.line}`} />
          </div>
        )
      })}
      <div className="flex h-2.5 overflow-hidden rounded-full bg-line">
        <div className="bg-sky-400 transition-all" style={{ width: `${stockRatio * 100}%` }} />
        <div className="bg-amber-400 transition-all" style={{ width: `${cashRatio * 100}%` }} />
      </div>
    </div>
  )
}
