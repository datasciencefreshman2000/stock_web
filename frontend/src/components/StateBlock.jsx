import { Loader2 } from 'lucide-react'

export function LoadingBlock({ label = '載入中', fullscreen = false }) {
  return (
    <div
      className={`grid w-full place-items-center bg-[#0b1020] px-4 ${fullscreen ? 'min-h-screen' : 'min-h-[50vh]'}`}
      role="status"
      aria-live="polite"
    >
      <div className="soft-pop flex flex-col items-center justify-center text-center text-slate-300">
        <Loader2 size={58} strokeWidth={1.5} className="animate-spin text-sky-300 drop-shadow-[0_0_12px_rgba(56,189,248,0.25)]" />
        <div className="mt-4 text-xs font-medium text-slate-400">{label}</div>
        <div className="mt-2 flex gap-1" aria-hidden="true">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300 [animation-delay:-0.2s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300 [animation-delay:-0.1s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300" />
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
