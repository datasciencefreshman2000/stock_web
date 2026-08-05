import { Delete, RotateCcw } from 'lucide-react'

function appendDigit(value, digit) {
  if (!value || value === '0') return digit
  if (value.includes('.') && value.split('.')[1].length >= 2) return value
  return `${value}${digit}`
}

function appendDecimal(value) {
  if (value.includes('.')) return value
  return value ? `${value}.` : '0.'
}

export default function NumericKeypad({ value, onChange }) {
  function press(key) {
    if (key === 'clear') {
      onChange('')
      return
    }
    if (key === 'backspace') {
      onChange(value.slice(0, -1))
      return
    }
    if (key === '.') {
      onChange(appendDecimal(value))
      return
    }
    onChange(appendDigit(value, key))
  }

  return (
    <div className="rounded-md border border-line bg-panel/60 p-2" aria-label="數字鍵盤">
      <div className="grid grid-cols-4 gap-2">
        {['7', '8', '9', 'backspace', '4', '5', '6', 'clear', '1', '2', '3', '.', '0'].map((key) => {
          const isAction = key === 'backspace' || key === 'clear'
          return (
            <button
              key={key}
              type="button"
              onClick={() => press(key)}
              className={`grid min-h-11 place-items-center rounded-md border text-base font-medium transition active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 ${
                isAction
                  ? 'border-line bg-surface text-slate-300 hover:border-sky-400/70 hover:bg-sky-500/10 hover:text-white'
                  : 'border-line bg-[#0b1020] text-white hover:border-sky-400/70 hover:bg-sky-500/10'
              } ${key === '0' ? 'col-span-2' : ''}`}
              aria-label={key === 'backspace' ? '刪除一位' : key === 'clear' ? '清除金額' : key}
              title={key === 'backspace' ? '刪除一位' : key === 'clear' ? '清除金額' : undefined}
            >
              {key === 'backspace' ? <Delete size={18} /> : null}
              {key === 'clear' ? <RotateCcw size={17} /> : null}
              {!isAction ? key : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}
