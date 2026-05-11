export function LoadingBlock({ label = '載入中' }) {
  return <div className="rounded-md border border-line bg-surface p-5 text-slate-300">{label}</div>
}

export function ErrorBlock({ error }) {
  return (
    <div className="rounded-md border border-rose-900 bg-rose-950/40 p-5 text-rose-100">
      {error?.message || '發生錯誤'}
    </div>
  )
}
