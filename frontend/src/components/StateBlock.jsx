import { Loader2 } from 'lucide-react'

export function LoadingBlock({ label = '載入中' }) {
  return (
    <div className="soft-pop relative overflow-hidden rounded-md border border-line bg-surface p-5 text-slate-300">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-sky-300 to-transparent loading-sweep" />
      <div className="absolute right-4 top-4 h-12 w-12 rounded-full border border-sky-400/20 loading-orbit" aria-hidden="true" />
      <div className="relative flex items-center gap-3">
        <Loader2 size={18} className="animate-spin text-sky-300" />
      <div>
        <div className="text-sm font-medium text-slate-200">{label}</div>
        <div className="mt-1 flex gap-1" aria-hidden="true">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300 [animation-delay:-0.2s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300 [animation-delay:-0.1s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300" />
        </div>
      </div>
      </div>
    </div>
  )
}

export function ErrorBlock({ error }) {
  return (
    <div className="rounded-md border border-rose-900 bg-rose-950/40 p-5 text-rose-100">
      {error?.message || '發生錯誤'}
    </div>
  )
}
