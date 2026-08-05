import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

import NumericKeypad from './NumericKeypad'

export default function MobileNumericInput({
  value = '',
  onChange,
  label,
  subtitle,
  currency = 'TWD',
  onCurrencyChange,
  allowNegative = false,
  maxDecimals = 2,
  masked = false,
  onComplete,
  onDesktopBlur,
  primaryLabel = '完成',
  secondaryLabel,
  statusMessage = '',
  busy = false,
  disabled = false,
  allowZero = true,
  desktopClassName = '',
}) {
  const [open, setOpen] = useState(false)
  const [localError, setLocalError] = useState('')

  useEffect(() => {
    if (!open) return undefined
    const previousOverflow = document.body.style.overflow
    const desktopQuery = window.matchMedia('(min-width: 640px)')
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const closeOnDesktop = (event) => {
      if (event.matches) setOpen(false)
    }
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', closeOnEscape)
    desktopQuery.addEventListener('change', closeOnDesktop)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
      desktopQuery.removeEventListener('change', closeOnDesktop)
    }
  }, [open])

  async function complete() {
    setLocalError('')
    try {
      const completed = await onComplete?.()
      if (completed !== false) setOpen(false)
    } catch (error) {
      setLocalError(error?.message || '操作失敗，請稍後再試')
    }
  }

  const shownValue = masked && value !== '' ? '••••' : value

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        className={`flex min-h-11 w-full items-center justify-end rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm disabled:opacity-50 sm:hidden ${shownValue !== '' ? 'text-white' : 'text-slate-500'}`}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        {shownValue !== '' ? shownValue : '點選輸入金額'}
      </button>
      <input
        aria-label={label}
        className={`hidden w-full rounded-md border border-line bg-[#0b1020] px-3 py-2 text-right text-sm text-white outline-none focus:border-sky-500 sm:block ${desktopClassName}`}
        type={masked ? 'password' : 'number'}
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onDesktopBlur}
        disabled={disabled}
      />
      {open
        ? createPortal(
            <div className="fixed inset-0 z-[70] sm:hidden" role="dialog" aria-modal="true" aria-label={label}>
              <button
                type="button"
                className="keypad-backdrop-enter absolute inset-0 min-h-0 w-full bg-black/70"
                onClick={() => setOpen(false)}
                aria-label="關閉數字鍵盤"
              />
              <div
                className="keypad-sheet-enter absolute inset-x-0 bottom-0 rounded-t-lg border border-line bg-surface p-3 shadow-xl"
                style={{ paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom))' }}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-white">{label}</div>
                    {subtitle ? <div className="truncate text-xs text-slate-500">{subtitle}</div> : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="grid h-10 min-h-0 w-10 shrink-0 place-items-center rounded-md border border-line text-slate-300 active:scale-95"
                    aria-label="關閉數字鍵盤"
                    title="關閉數字鍵盤"
                  >
                    <X size={18} />
                  </button>
                </div>
                <NumericKeypad
                  value={String(value ?? '')}
                  onChange={onChange}
                  currency={currency}
                  onCurrencyChange={onCurrencyChange}
                  allowNegative={allowNegative}
                  maxDecimals={maxDecimals}
                  masked={masked}
                />
                {localError || statusMessage ? (
                  <div className={`mt-2 text-xs ${!localError && statusMessage.startsWith('已') ? 'text-emerald-300' : 'text-rose-300'}`}>
                    {localError || statusMessage}
                  </div>
                ) : null}
                <div className={`mt-3 grid gap-2 ${secondaryLabel ? 'grid-cols-[3fr_1fr]' : 'grid-cols-1'}`}>
                  <button
                    type="button"
                    onClick={complete}
                    disabled={disabled || busy || !Number.isFinite(Number(value)) || (!allowZero && Number(value) <= 0)}
                    className="rounded-md bg-sky-500 px-3 py-3 text-sm font-medium text-white active:scale-[0.98] disabled:opacity-40"
                  >
                    {busy ? '儲存中' : primaryLabel}
                  </button>
                  {secondaryLabel ? (
                    <button
                      type="button"
                      onClick={() => setOpen(false)}
                      disabled={busy}
                      className="rounded-md border border-line bg-panel px-1 py-2 text-[11px] font-medium leading-tight text-slate-200 active:scale-[0.96] disabled:opacity-40"
                    >
                      {secondaryLabel}
                    </button>
                  ) : null}
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
