export default function TradeSideBadge({ isBuy }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
        isBuy
          ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-100'
          : 'border-rose-400/40 bg-rose-500/15 text-rose-100'
      }`}
    >
      {isBuy ? '買入' : '賣出'}
    </span>
  )
}
