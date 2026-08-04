export default function Metric({ label, value, accent = 'text-slate-100', inline = false }) {
  if (inline) {
    return (
      <div className="flex min-w-0 items-center justify-between gap-2 rounded-md bg-panel/50 px-2 py-1.5">
        <div className="shrink-0 text-slate-400">{label}</div>
        <div className={`min-w-0 truncate text-right tabular-nums ${accent}`}>{value}</div>
      </div>
    )
  }

  return (
    <div className="min-w-0">
      <div className="text-slate-400">{label}</div>
      <div className={`truncate tabular-nums ${accent}`}>{value}</div>
    </div>
  )
}
