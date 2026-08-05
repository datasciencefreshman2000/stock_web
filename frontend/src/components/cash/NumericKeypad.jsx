import { Delete, Minus, Plus, RotateCcw } from 'lucide-react'

function unsignedValue(value) {
  return value.startsWith('-') ? value.slice(1) : value
}

function appendDigit(value, digit, maxDecimals) {
  const sign = value.startsWith('-') ? '-' : ''
  const unsigned = unsignedValue(value)
  if (!unsigned || unsigned === '0') return `${sign}${digit}`
  if (unsigned.includes('.') && unsigned.split('.')[1].length >= maxDecimals) return value
  return `${value}${digit}`
}

function appendDigits(value, digits, maxDecimals) {
  return [...digits].reduce((current, digit) => appendDigit(current, digit, maxDecimals), value)
}

function appendDecimal(value) {
  if (value.includes('.')) return value
  if (value === '-') return '-0.'
  return value ? `${value}.` : '0.'
}

function toggleSign(value) {
  if (value.startsWith('-')) return value.slice(1)
  return value ? `-${value}` : '-'
}

export default function NumericKeypad({
  value = '',
  onChange,
  currency = 'TWD',
  onCurrencyChange,
  allowNegative = false,
  maxDecimals = 2,
  masked = false,
}) {
  function press(key) {
    if (key === 'clear') {
      onChange('')
      return
    }
    if (key === 'backspace') {
      onChange(value.slice(0, -1))
      return
    }
    if (key === 'sign') {
      onChange(toggleSign(value))
      return
    }
    if (key === '.') {
      onChange(appendDecimal(value))
      return
    }
    onChange(appendDigits(value, key, maxDecimals))
  }

  const bottomKeys = allowNegative
    ? [
        { key: 'sign', span: '' },
        { key: '0', span: 'col-span-2' },
        { key: '00', span: '' },
      ]
    : [
        { key: '0', span: 'col-span-2' },
        { key: '00', span: 'col-span-2' },
      ]
  const keys = [
    { key: '7' }, { key: '8' }, { key: '9' }, { key: 'backspace' },
    { key: '4' }, { key: '5' }, { key: '6' }, { key: 'clear' },
    { key: '1' }, { key: '2' }, { key: '3' }, { key: '.' },
    ...bottomKeys,
  ]

  return (
    <div className="rounded-md border border-line bg-panel/60 p-2" aria-label="數字鍵盤">
      <div className="mb-2 grid grid-cols-[minmax(0,1fr)_5rem] gap-2">
        <div className="flex min-h-11 min-w-0 items-center justify-between gap-2 rounded-md border border-line bg-[#0b1020] px-3">
          <span className="shrink-0 text-xs text-slate-500">金額</span>
          <span className="truncate text-xl font-semibold tabular-nums text-white">
            {masked && value ? '••••' : value || '0'}
          </span>
        </div>
        {onCurrencyChange ? (
          <select
            aria-label="幣別"
            className="h-11 min-h-0 w-20 shrink-0 rounded-md border border-line bg-[#0b1020] px-2 py-0 text-xs font-medium text-white"
            value={currency}
            onChange={(event) => onCurrencyChange(event.target.value)}
          >
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        ) : (
          <div className="grid h-11 min-h-0 w-20 place-items-center rounded-md border border-line bg-[#0b1020] text-xs font-medium text-slate-300">
            {currency}
          </div>
        )}
      </div>
      <div className="mb-2 text-right text-[11px] text-slate-500">最多 {maxDecimals} 位小數</div>
      <div className="grid grid-cols-4 gap-2">
        {keys.map(({ key, span = '' }) => {
          const isBackspace = key === 'backspace'
          const isClear = key === 'clear'
          const isSign = key === 'sign'
          const label = isBackspace ? '刪除一位' : isClear ? '重新輸入' : isSign ? '切換正負' : key
          const tone = isBackspace
            ? 'border-rose-400/40 bg-rose-500/15 text-rose-200'
            : isClear
              ? 'border-sky-400/40 bg-sky-500/15 text-sky-100'
              : 'border-line bg-[#0b1020] text-white'
          return (
            <button
              key={key}
              type="button"
              onClick={() => press(key)}
              className={`keypad-key grid min-h-11 place-items-center rounded-md border text-base font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 ${tone} ${span}`}
              aria-label={label}
              title={isBackspace || isClear || isSign ? label : undefined}
            >
              {isBackspace ? <Delete size={18} /> : null}
              {isClear ? <RotateCcw size={17} /> : null}
              {isSign ? (
                <span className="flex items-center" aria-hidden="true">
                  <Plus size={13} />
                  <Minus size={13} />
                </span>
              ) : null}
              {!isBackspace && !isClear && !isSign ? key : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}
